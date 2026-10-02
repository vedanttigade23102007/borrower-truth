"""File mapper commands (INTEGRATION.md, section 3). All data in this project is synthetic.

    uv run python -m bt.mapper inspect FILE [--sheet NAME]
    uv run python -m bt.mapper suggest FILE --table tape --borrower B0012 --header-row 3 --first-month 2024-01 \
        [--sheet NAME] [--set facility_id=F0012A ...] --out mappings/B0012-tape.json
    uv run python -m bt.mapper confirm mappings/B0012-tape.json --by "First Last"
    uv run python -m bt.mapper map FILE --mapping mappings/B0012-tape.json --staging staging \
        --total 2024-03=12345678.90 [--total ...] [--totals totals.json] --report reports/B0012-2024-03.md
    uv run python -m bt.mapper assemble --staging staging --table tape --out data/in
"""
from __future__ import annotations

import argparse
import json
import sys

from bt.mapper import convert, readfile, run


def _pairs(items) -> dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not _:
            sys.exit(f"expected KEY=VALUE, got '{it}'")
        out[k.strip()] = v.strip()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bt.mapper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="list the sheets and show the first rows, numbered, to pick the header row")
    p.add_argument("file"), p.add_argument("--sheet"), p.add_argument("--rows", type=int, default=12)
    p = sub.add_parser("suggest", help="draft a mapping for one lender's layout")
    p.add_argument("file"), p.add_argument("--table", required=True), p.add_argument("--borrower", required=True)
    p.add_argument("--header-row", type=int, required=True), p.add_argument("--first-month", required=True)
    p.add_argument("--sheet"), p.add_argument("--set", action="append", help="a fixed value: COLUMN=VALUE")
    p.add_argument("--out", required=True)
    p = sub.add_parser("confirm", help="a named person confirms a mapping")
    p.add_argument("mapping"), p.add_argument("--by", required=True)
    p = sub.add_parser("map", help="map one file, check it, write it and its report")
    p.add_argument("file"), p.add_argument("--mapping", required=True), p.add_argument("--staging", required=True)
    p.add_argument("--total", action="append", help="certificate total: YYYY-MM=AMOUNT")
    p.add_argument("--totals", help="a JSON file of certificate totals by YYYY-MM")
    p.add_argument("--report", required=True)
    p = sub.add_parser("assemble", help="combine the mapped files of one table into the table the checks read")
    p.add_argument("--staging", required=True), p.add_argument("--table", required=True), p.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "inspect":
        print("sheets:", ", ".join(readfile.sheets(a.file)))
        for i, r in enumerate(readfile.rows(a.file, a.sheet)[:a.rows], start=1):
            print(f"{i:>4} | " + " | ".join(convert.text(c)[:18] for c in r))
        return 0
    if a.cmd == "suggest":
        m = run.draft(a.file, a.table, a.borrower, a.header_row, a.first_month, a.sheet, _pairs(a.set))
        run.save(m, a.out)
        for k, v in m["columns"].items():
            print(f"  {k:22s} <- {v['source']:40s} score {v['score']}")
        if m["needs_a_person"]:
            print("needs a person (map a column by editing the file, or fix a value with --set):",
                  ", ".join(m["needs_a_person"]))
        print("formats guessed:", json.dumps(m["formats"]), "| not used:", ", ".join(m["not_used"]) or "-")
        print(f"draft written to {a.out}. Nothing runs until a person confirms it.")
        return 0
    if a.cmd == "confirm":
        try:
            m = run.confirm(run.load(a.mapping), a.by)
        except run.Stop as e:
            print("not confirmed:", e)
            return 1
        run.save(m, a.mapping)
        print(f"confirmed by {m['confirmed_by']} on {m['confirmed_on']}")
        return 0
    if a.cmd == "map":
        totals = {k: float(v.replace(",", "").replace("$", "")) for k, v in _pairs(a.total).items()}
        if a.totals:
            totals.update({k: float(v) for k, v in json.load(open(a.totals)).items()})
        res = run.map_file(a.file, run.load(a.mapping), a.staging, totals or None, a.report)
        print(("written: " + res["output"]) if res["written"] else ("STOPPED: " + "; ".join(res["stops"])))
        print(f"report: {a.report}")
        return 0 if res["written"] else 1
    if a.cmd == "assemble":
        n = run.assemble(a.staging, a.table, a.out)
        print(f"{a.table}: {n:,} rows written to {a.out}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
