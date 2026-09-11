"""Render synthetic invoice documents for training and testing the document model.

EVERYTHING IS SYNTHETIC; every page is stamped "SYNTHETIC — DEMO ONLY".

Why: the fine-tuned model reads invoice images into fields (number, PO, bill-to,
date, total). S4 then cross-checks the document against the borrower's data. A
realistic fraud is a document and a data record that disagree, so a share of the
fake invoices are rendered *tampered*: the page total differs from the record.

Splits are by borrower, so no borrower's layout leaks from train into test.
Outputs Donut-style metadata (ground truth as JSON) usable by most document
models.

    uv run --extra docs python -m bt.docs.render_invoices --data data/out/demo --n 1500
"""
from __future__ import annotations

import argparse
import json
import os
import random

import duckdb
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1000, 1300
MONTH0 = (2024, 10)  # month index 0 of the synthetic timeline


def date_str(month: int, day: int, style: int) -> str:
    y, m = MONTH0[0] + (MONTH0[1] - 1 + month) // 12, (MONTH0[1] - 1 + month) % 12 + 1
    return [f"{y}-{m:02d}-{day:02d}", f"{m:02d}/{day:02d}/{y}", f"{day:02d} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} {y}"][style]


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def render(row: dict, seller: str, printed_total: float, layout: int, rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_big, f_mid, f_small = font(34), font(22), font(17)
    x0 = 60 if layout != 1 else 90
    d.text((x0, 50), seller, fill="black", font=f_big)
    d.text((x0, 95), "123 Commerce St · synthetic address", fill="#444", font=f_small)
    title_x = W - 300 if layout == 0 else x0
    title_y = 50 if layout == 0 else 150
    d.text((title_x, title_y), "INVOICE", fill="#1d3d8f", font=f_big)
    y = 220
    fields = [("Invoice No.", row["invoice_number"]), ("PO Number", row["po_number"]),
              ("Invoice Date", date_str(row["issue_month"], row["issue_day"], layout)),
              ("Terms", f"Net {row['due_days']}")]
    if layout == 2:
        fields = fields[::-1]
    for k, v in fields:
        d.text((x0, y), f"{k}:", fill="#333", font=f_mid)
        d.text((x0 + 230, y), str(v), fill="black", font=f_mid)
        y += 38
    y += 20
    d.text((x0, y), "Bill To:", fill="#333", font=f_mid)
    d.text((x0 + 230, y), row["debtor_name"], fill="black", font=f_mid)
    y += 70
    d.line((x0, y, W - 60, y), fill="#999", width=2)
    y += 15
    d.text((x0, y), "Description", font=f_mid, fill="#333")
    d.text((W - 260, y), "Amount", font=f_mid, fill="#333")
    y += 45
    # split the printed total into 1-3 line items that sum exactly
    n = rng.randint(1, 3)
    cents = int(round(printed_total * 100))
    # the goods line carries 75-95% of the total; freight/handling share the rest
    parts = [cents]
    if n > 1:
        main_part = int(cents * rng.uniform(0.75, 0.95))
        rest = cents - main_part
        extra = [rest] if n == 2 else [int(rest * rng.uniform(0.3, 0.7))]
        if n == 3:
            extra.append(rest - extra[0])
        parts = [main_part] + extra
    for i, p in enumerate(parts):
        desc = row["description"] if i == 0 else f"freight and handling {i}"
        d.text((x0, y), desc[:48], font=f_small, fill="black")
        d.text((W - 260, y), f"${p / 100:,.2f}", font=f_small, fill="black")
        y += 36
    y += 30
    d.line((W - 420, y, W - 60, y), fill="#999", width=2)
    y += 15
    d.text((W - 420, y), "TOTAL DUE", font=f_mid, fill="black")
    d.text((W - 260, y), f"${printed_total:,.2f}", font=f_mid, fill="black")
    d.text((x0, H - 70), "SYNTHETIC - DEMO ONLY - not a real invoice", font=f_small, fill="#b00")
    # scan-like noise
    img = img.rotate(rng.uniform(-1.2, 1.2), expand=False, fillcolor="white")
    if rng.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.8)))
    return img


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/out/demo")
    ap.add_argument("--out", default="data/out/docs")
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--tamper-rate", type=float, default=0.3, help="share of fake/duplicate invoices rendered tampered")
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    con = duckdb.connect()
    p = lambda t: f"read_parquet('{os.path.join(a.data, t)}.parquet')"
    labels = json.load(open(os.path.join(a.data, "labels.json")))
    rows = con.execute(f"""
        SELECT i.*, e.name AS seller FROM {p('invoices')} i
        JOIN {p('borrowers')} b USING (borrower_id) JOIN {p('entities')} e ON e.entity_id = b.entity_id
        ORDER BY hash(invoice_id || '{a.seed}') LIMIT {a.n}""").fetchall()
    cols = [c[0] for c in con.description]
    borrowers = sorted({r[cols.index("borrower_id")] for r in rows})
    rng.shuffle(borrowers)
    split_of = {b: ("test" if i % 5 == 0 else "val" if i % 5 == 1 else "train") for i, b in enumerate(borrowers)}
    fake_b = {b for b, v in labels.items() if "FAKE_INVOICES" in v["mechanisms"]}
    for s in ("train", "val", "test"):
        os.makedirs(os.path.join(a.out, s), exist_ok=True)
    meta = {s: open(os.path.join(a.out, s, "metadata.jsonl"), "w") for s in ("train", "val", "test")}
    counts = {"train": 0, "val": 0, "test": 0, "tampered": 0}
    for r in rows:
        row = dict(zip(cols, r))
        split = split_of[row["borrower_id"]]
        tampered = row["borrower_id"] in fake_b and rng.random() < a.tamper_rate
        printed = round(row["amount"] * (rng.uniform(1.3, 4.0) if tampered else 1.0), 2)
        img = render(row, row["seller"], printed, rng.randint(0, 2), rng)
        fname = f"{row['invoice_id']}.png"
        img.save(os.path.join(a.out, split, fname), optimize=True)
        gt = {"invoice_number": row["invoice_number"], "po_number": row["po_number"], "bill_to": row["debtor_name"],
              "invoice_date": date_str(row["issue_month"], row["issue_day"], 0), "total": f"{printed:.2f}"}
        meta[split].write(json.dumps({"file_name": fname, "ground_truth": json.dumps({"gt_parse": gt}),
                                      "record_amount": round(row["amount"], 2), "tampered": tampered,
                                      "borrower_id": row["borrower_id"]}) + "\n")
        counts[split] += 1
        counts["tampered"] += tampered
    for f in meta.values():
        f.close()
    json.dump(dict(counts, SYNTHETIC="All documents are synthetic."), open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    print(counts)


if __name__ == "__main__":
    main()
