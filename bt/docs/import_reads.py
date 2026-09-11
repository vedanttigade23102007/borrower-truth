"""Import the document batch job's reads (Kaggle output) into each book.

doc_reads.jsonl (from model/kaggle_score) -> <book>/doc_reads.parquet, which S4
reads. Tamper labels are NOT copied: they stay in data/out/docs_score/<book>/,
read only by the metrics below.

    uv run python -m bt.docs.import_reads --reads model/kaggle_score/output/doc_reads.jsonl
"""
from __future__ import annotations

import argparse
import json
import os

import pyarrow as pa
import pyarrow.parquet as pq

BOOKS = {"demo": "data/out/demo", "seed_201": "data/out/eval/seed_201"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reads", default="model/kaggle_score/output/doc_reads.jsonl")
    ap.add_argument("--labels-root", default="data/out/docs_score")
    a = ap.parse_args(argv)
    by_book: dict[str, list[dict]] = {}
    for line in open(a.reads):
        r = json.loads(line)
        by_book.setdefault(r["book"], []).append(dict(
            invoice_id=r["invoice_id"], borrower_id=r["borrower_id"], read_total=r["read"]["total"],
            read_total_first=r["read_total_first"], reread=bool(r["reread"]), reads_agree=bool(r["reads_agree"]),
            record_amount=float(r["record_amount"]), doc_mismatch=bool(r["doc_mismatch"])))
    for book, rows in by_book.items():
        dest = BOOKS[book]
        pq.write_table(pa.Table.from_pylist(rows), os.path.join(dest, "doc_reads.parquet"))
        labels = {json.loads(l)["invoice_id"]: json.loads(l)["tampered"]
                  for l in open(os.path.join(a.labels_root, book, "doc_labels.jsonl"))}
        tp = sum(1 for r in rows if r["doc_mismatch"] and labels[r["invoice_id"]])
        fp = sum(1 for r in rows if r["doc_mismatch"] and not labels[r["invoice_id"]])
        fn = sum(1 for r in rows if not r["doc_mismatch"] and labels[r["invoice_id"]])
        clean = sum(1 for v in labels.values() if not v)
        print(f"{book}: {len(rows)} reads -> {dest}/doc_reads.parquet · tampered caught {tp}/{tp + fn} · "
              f"false flags {fp}/{clean} ({fp / max(clean, 1):.1%})")


if __name__ == "__main__":
    main()
