"""Fine-tune a small document model to read invoices, then prove it.

RUNS ON KAGGLE (free GPU), NOT on the 8 GB Mac. Push with:
    kaggle kernels push -p model/kaggle
Untested until it runs there. Pick/confirm model IDs at run time; newer models may exist.

What it does
1. Loads the synthetic invoice images (Kaggle dataset `borrower-truth-invoices`,
   built by bt.docs.render_invoices; split by borrower, so test layouts are unseen).
2. Fine-tunes Donut (OCR-free, ~200M params; it reads receipts well after fine-tuning,
   CORD is its standard benchmark) to output JSON: invoice_number, po_number,
   bill_to, invoice_date, total.
3. Evaluates on the held-out test split:
   - per-field exact-match accuracy, fine-tuned vs the base checkpoint
   - tamper detection: the extracted total vs the borrower's data record; a
     mismatch >1% is flagged. Reports precision and recall on the planted tampered docs.
4. Saves metrics.json and the model; pushes the model to the Hugging Face Hub as
   a PRIVATE repo if an HF_TOKEN Kaggle secret exists.
Everything is synthetic; the model card says so.
"""
import json
import os
import random
import re
import time

import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderConfig, VisionEncoderDecoderModel

BASE = "naver-clova-ix/donut-base"
def _find_data_root(base="/kaggle/input"):
    # Kaggle's mount layout has changed over time; find the folder holding train/metadata.jsonl
    for root, _dirs, files in os.walk(base):
        if "metadata.jsonl" in files and os.path.basename(root) == "train":
            return os.path.dirname(root)
    raise FileNotFoundError(f"no train/metadata.jsonl under {base}")


DATA = _find_data_root()
print("data root:", DATA)
OUT = "/kaggle/working"
FIELDS = ["invoice_number", "po_number", "bill_to", "invoice_date", "total"]
TASK = "<s_invoice>"
IMG_SIZE = (1280, 960)  # (height, width): smaller than Donut's default so a 16 GB T4/P100 fits
EPOCHS, LR, MAX_LEN = 5, 3e-5, 128
device = "cuda" if torch.cuda.is_available() else "cpu"
random.seed(0)
torch.manual_seed(0)


def load(split):
    rows = [json.loads(l) for l in open(f"{DATA}/{split}/metadata.jsonl")]
    for r in rows:
        r["path"] = f"{DATA}/{split}/{r['file_name']}"
        r["gt"] = json.loads(r["ground_truth"])["gt_parse"]
    return rows


def to_tokens(gt):
    return "".join(f"<s_{k}>{gt[k]}</s_{k}>" for k in FIELDS) + "</s>"


def parse(seq):
    out = {}
    for k in FIELDS:
        m = re.search(f"<s_{k}>(.*?)</s_{k}>", seq)
        out[k] = m.group(1).strip() if m else ""
    return out


processor = DonutProcessor.from_pretrained(BASE)
processor.image_processor.size = {"height": IMG_SIZE[0], "width": IMG_SIZE[1]}
processor.image_processor.do_align_long_axis = False
new_tokens = [TASK] + [f"<s_{k}>" for k in FIELDS] + [f"</s_{k}>" for k in FIELDS]
processor.tokenizer.add_special_tokens({"additional_special_tokens": new_tokens})


def make_model():
    # image size must be in the config BEFORE loading (Donut's documented fine-tuning setup)
    cfg = VisionEncoderDecoderConfig.from_pretrained(BASE)
    cfg.encoder.image_size = list(IMG_SIZE)
    cfg.decoder.max_length = MAX_LEN
    m = VisionEncoderDecoderModel.from_pretrained(BASE, config=cfg)
    m.decoder.resize_token_embeddings(len(processor.tokenizer))
    m.config.pad_token_id = processor.tokenizer.pad_token_id
    m.config.decoder_start_token_id = processor.tokenizer.convert_tokens_to_ids(TASK)
    return m.to(device)


def pixel(path):
    return processor(Image.open(path).convert("RGB"), return_tensors="pt").pixel_values


@torch.no_grad()
def predict(model, rows):
    model.eval()
    preds = []
    start = torch.tensor([[processor.tokenizer.convert_tokens_to_ids(TASK)]], device=device)
    for r in rows:
        out = model.generate(pixel(r["path"]).to(device), decoder_input_ids=start, max_length=MAX_LEN,
                             pad_token_id=processor.tokenizer.pad_token_id, eos_token_id=processor.tokenizer.eos_token_id,
                             num_beams=1, bad_words_ids=[[processor.tokenizer.unk_token_id]])
        preds.append(parse(processor.batch_decode(out)[0]))
    return preds


def evaluate(name, model, rows):
    t0 = time.time()
    preds = predict(model, rows)
    secs = time.time() - t0
    acc = {k: sum(p[k] == r["gt"][k] for p, r in zip(preds, rows)) / len(rows) for k in FIELDS}
    tp = fp = fn = 0
    for p, r in zip(preds, rows):
        try:
            got = float(p["total"].replace(",", ""))
            flag = abs(got - r["record_amount"]) > 0.01 * max(r["record_amount"], 1)
        except ValueError:
            flag = True  # unreadable total -> send to a human (fallback), counted as a flag
        tp += flag and r["tampered"]
        fp += flag and not r["tampered"]
        fn += (not flag) and r["tampered"]
    res = dict(model=name, field_accuracy=acc, all_fields_correct=sum(all(p[k] == r["gt"][k] for k in FIELDS)
                                                                        for p, r in zip(preds, rows)) / len(rows),
               tamper_precision=tp / max(tp + fp, 1), tamper_recall=tp / max(tp + fn, 1),
               docs_per_minute=round(60 * len(rows) / secs, 1), n=len(rows))
    print(json.dumps(res, indent=1))
    return res, preds


train, val, test = load("train"), load("val"), load("test")
results = {}
base_model = make_model()
results["base"], _ = evaluate("donut-base (not fine-tuned)", base_model, test[:100])
del base_model
torch.cuda.empty_cache()

model = make_model()
model.gradient_checkpointing_enable()
opt = torch.optim.AdamW(model.parameters(), lr=LR)
scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
for epoch in range(EPOCHS):
    model.train()
    random.shuffle(train)
    total = 0.0
    for r in train:
        labels = processor.tokenizer(to_tokens(r["gt"]), add_special_tokens=False, max_length=MAX_LEN,
                                     truncation=True, return_tensors="pt").input_ids.to(device)
        labels[labels == processor.tokenizer.pad_token_id] = -100
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            loss = model(pixel_values=pixel(r["path"]).to(device), labels=labels).loss
        opt.zero_grad()
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        total += loss.item()
    val_res, _ = evaluate(f"epoch {epoch + 1} (val)", model, val[:60])
    print(f"epoch {epoch + 1}: train loss {total / len(train):.4f}")

results["fine_tuned"], preds = evaluate("donut fine-tuned (test, unseen borrowers)", model, test)
json.dump(results, open(f"{OUT}/metrics.json", "w"), indent=1)
json.dump([dict(file=r["file_name"], truth=r["gt"], pred=p, tampered=r["tampered"]) for r, p in zip(test, preds)][:50],
          open(f"{OUT}/sample_predictions.json", "w"), indent=1)
model.save_pretrained(f"{OUT}/invoice-reader")
processor.save_pretrained(f"{OUT}/invoice-reader")

try:
    from kaggle_secrets import UserSecretsClient
    token = UserSecretsClient().get_secret("HF_TOKEN")
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    repo = api.create_repo("borrower-truth-invoice-reader", private=True, exist_ok=True).repo_id
    open(f"{OUT}/invoice-reader/README.md", "w").write(
        "# Borrower Truth invoice reader (synthetic demo)\n\nDonut fine-tuned on SYNTHETIC invoices only. "
        f"Metrics: see metrics.json.\n\n```json\n{json.dumps(results, indent=1)}\n```\n")
    api.upload_folder(folder_path=f"{OUT}/invoice-reader", repo_id=repo)
    print("pushed to", repo)
except Exception as e:
    print("HF push skipped:", e)
