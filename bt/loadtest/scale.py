"""Scale test: how does run time grow with data size?

Generates books of increasing size, runs all seven systems once, and records
rows, seconds and rows/second per tier. Bank-scale capacity is then an
extrapolation from this curve, with the arithmetic shown, not a claim.

Uses DuckDB views over Parquet (no in-memory copy) and a memory cap with
spill-to-disk, so it runs on an 8 GB laptop.

    uv run python -m bt.loadtest.scale --tiers 120:1 240:2 400:3
"""
from __future__ import annotations

import argparse
import json
import os
import time

import duckdb

from bt.datagen.generate import main as generate
from bt.pipeline.run import run as pipeline


def rows_in(data):
    con = duckdb.connect()
    total = 0
    for t in ("tape", "source_truth", "payments", "invoices", "outflows"):
        f = os.path.join(data, f"{t}.parquet")
        if os.path.exists(f):
            total += con.execute(f"SELECT count(*) FROM read_parquet('{f}')").fetchone()[0]
    return total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", nargs="+", default=["120:1", "240:2", "400:3"], help="borrowers:scale")
    ap.add_argument("--root", default="data/out/scale")
    ap.add_argument("--out", default="proof/scale.json")
    a = ap.parse_args(argv)
    results = []
    for tier in a.tiers:
        nb, sc = tier.split(":")
        data = os.path.join(a.root, f"b{nb}_s{sc}")
        if not os.path.exists(os.path.join(data, "labels.json")):
            t0 = time.time()
            generate(["--borrowers", nb, "--scale", sc, "--seed", "900", "--out", data])
            gen_s = time.time() - t0
        else:
            gen_s = None
        rows = rows_in(data)
        t0 = time.time()
        _, cases, metrics = pipeline(data, 23, materialize=False)
        secs = time.time() - t0
        per_system = {k: v["seconds"] for k, v in metrics.items() if isinstance(v, dict) and "seconds" in v}
        r = dict(borrowers=int(nb), scale=float(sc), rows=rows, seconds=round(secs, 2),
                 rows_per_second=int(rows / secs), per_system=per_system, generate_seconds=gen_s)
        results.append(r)
        print(f"{nb:>5} borrowers x{sc}: {rows:>12,} rows  {secs:7.2f}s  {r['rows_per_second']:>10,} rows/s")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(results, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
