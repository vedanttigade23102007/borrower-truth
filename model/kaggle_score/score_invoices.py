"""Batch job: read the documents on file with the fine-tuned invoice reader.

RUNS ON KAGGLE (free T4). It is the "document service" S4 depends on: it writes
one read per document (doc_reads.jsonl). S4 compares each read total with the
borrower's data record.

Second look: if the first (greedy) read disagrees with the record, or can't be
parsed, the document is read again with beam search before it is flagged. Most
false flags in the first evaluation were single-digit slips; this measures how
many a second look removes.

Inputs, found by walking /kaggle/input:
- the model folder (config.json + model.safetensors), attached from the training kernel's output
- one folder per book with metadata.jsonl (+ doc_labels.jsonl, read ONLY for metrics)
"""
import json
import os
import re
import time

import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

FIELDS = ["invoice_number", "po_number", "bill_to", "invoice_date", "total"]
TASK = "<s_invoice>"
MAX_LEN = 128
OUT = "/kaggle/working"
device = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", device, torch.cuda.get_device_name(0) if device == "cuda" else "")


def find_model(base="/kaggle/input"):
    for root, _d, files in os.walk(base):
        if "config.json" in files and "model.safetensors" in files:
            return root
    raise FileNotFoundError("model folder not found under /kaggle/input")


def find_books(base="/kaggle/input"):
    return sorted(root for root, _d, files in os.walk(base) if "metadata.jsonl" in files and "doc_labels.jsonl" in files)


def parse(seq):
    out = {}
    for k in FIELDS:
        m = re.search(f"<s_{k}>(.*?)</s_{k}>", seq)
        out[k] = m.group(1).strip() if m else ""
    return out


def to_float(s):
    try:
        return float(s.replace(",", "").replace("$", ""))
    except (ValueError, AttributeError):
        return None


model_dir = find_model()
print("model:", model_dir)
processor = DonutProcessor.from_pretrained(model_dir)
model = VisionEncoderDecoderModel.from_pretrained(model_dir).to(device).eval()
start_id = processor.tokenizer.convert_tokens_to_ids(TASK)


@torch.no_grad()
def read(path, beams):
    px = processor(Image.open(path).convert("RGB"), return_tensors="pt").pixel_values.to(device)
    with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
        out = model.generate(px, decoder_input_ids=torch.tensor([[start_id]], device=device), max_length=MAX_LEN,
                             pad_token_id=processor.tokenizer.pad_token_id, eos_token_id=processor.tokenizer.eos_token_id,
                             num_beams=beams, bad_words_ids=[[processor.tokenizer.unk_token_id]])
    return parse(processor.batch_decode(out)[0])


def mismatch(total, record):
    v = to_float(total)
    return v is None or abs(v - record) > 0.01 * max(record, 1.0)


metrics = {}
with open(f"{OUT}/doc_reads.jsonl", "w") as outf:
    for book_dir in find_books():
        book = os.path.basename(book_dir)
        docs = [json.loads(l) for l in open(f"{book_dir}/metadata.jsonl")]
        labels = {json.loads(l)["invoice_id"]: json.loads(l) for l in open(f"{book_dir}/doc_labels.jsonl")}
        t0 = time.time()
        first_flags = final_flags = rereads = 0
        tp1 = fp1 = tp2 = fp2 = fn1 = fn2 = 0
        for d in docs:
            r1 = read(f"{book_dir}/{d['file_name']}", beams=1)
            m1 = mismatch(r1["total"], d["record_amount"])
            r2, m2 = r1, m1
            if m1:  # second look before flagging
                rereads += 1
                r2 = read(f"{book_dir}/{d['file_name']}", beams=4)
                m2 = mismatch(r2["total"], d["record_amount"])
            outf.write(json.dumps({"book": book, "invoice_id": d["invoice_id"], "borrower_id": d["borrower_id"],
                                   "read": r2, "read_total_first": r1["total"], "reread": m1,
                                   "reads_agree": r1["total"] == r2["total"], "record_amount": d["record_amount"],
                                   "doc_mismatch": m2}) + "\n")
            tam = labels[d["invoice_id"]]["tampered"]
            tp1 += m1 and tam
            fp1 += m1 and not tam
            fn1 += (not m1) and tam
            tp2 += m2 and tam
            fp2 += m2 and not tam
            fn2 += (not m2) and tam
        secs = time.time() - t0
        clean = sum(1 for d in docs if not labels[d["invoice_id"]]["tampered"])
        metrics[book] = dict(documents=len(docs), tampered=tp1 + fn1, rereads=rereads,
                             first_pass=dict(caught=tp1, false_flags=fp1, false_flag_rate=round(fp1 / max(clean, 1), 4)),
                             with_second_look=dict(caught=tp2, false_flags=fp2, false_flag_rate=round(fp2 / max(clean, 1), 4)),
                             docs_per_minute=round(60 * len(docs) / secs, 1))
        print(book, json.dumps(metrics[book]))

json.dump(metrics, open(f"{OUT}/score_metrics.json", "w"), indent=1)
print("done")
