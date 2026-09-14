"""Real loan-level auto-loan data from SEC Form ABS-EE (Regulation AB II, Schedule AL Item 3).

Every registered auto-loan securitization files one XML row per loan each month: credit score,
origination date and amount, vehicle, scheduled vs actual payment, days late, charge-off,
repossession. No VIN and no borrower identity (by design of the rule).

This module picks a spread of public auto-loan trusts (subprime and prime lenders), downloads
two consecutive monthly files for each, keeps the fields Borrower Truth needs as parquet, and
deletes the raw XML (100-170 MB each). Raw data stays local (data/cache is gitignored); only
the small measured summaries in data/calibration/ are committed.

    uv run python -m bt.sec.absee select      # show which filings would be pulled
    uv run python -m bt.sec.absee fetch       # download + parse (about 60 files)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import pyarrow as pa
import pyarrow.parquet as pq

from bt.sec import edgar

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "cache", "sec", "absee")
QUARTERS = ("2026/QTR2",)

# issuer family, trust-name pattern, lender tier (by the lender's own positioning), trusts to take
FAMILIES = [
    ("Santander Drive", r"^Santander Drive Auto Receivables Trust 20", "subprime", 2),
    ("Drive Auto (Santander)", r"^Drive Auto Receivables Trust 20", "subprime", 2),
    ("Exeter", r"^Exeter Automobile Receivables Trust 20", "subprime", 2),
    ("Bridgecrest (DriveTime)", r"^Bridgecrest Lending Auto Securitization Trust 20", "subprime", 2),
    ("AmeriCredit (GM Financial)", r"^AmeriCredit Automobile Receivables Trust 20", "subprime", 2),
    ("Carvana non-prime", r"^Carvana Auto Receivables Trust 20\d\d-N", "subprime", 2),
    ("Exeter Select", r"^Exeter Select Automobile Receivables Trust", "near-prime", 1),
    ("CarMax", r"^CarMax Auto Owner Trust 20", "prime", 1),
    ("Carvana prime", r"^Carvana Auto Receivables Trust 20\d\d-P", "prime", 1),
    ("Toyota", r"^Toyota Auto Receivables 20", "prime", 1),
    ("Honda", r"^Honda Auto Receivables 20", "prime", 1),
    ("Ford Credit", r"^Ford Credit Auto Owner Trust 20", "prime", 1),
    ("GM Financial prime", r"^GM Financial Consumer Automobile Receivables Trust 20", "prime", 1),
    ("Ally", r"^Ally Auto Receivables Trust 20", "prime", 1),
    ("Capital One", r"^Capital One Prime Auto Receivables Trust", "prime", 1),
    ("Hyundai", r"^Hyundai Auto Receivables Trust", "prime", 1),
    ("World Omni", r"^World Omni Auto Receivables Trust", "prime", 1),
    ("Nissan", r"^Nissan Auto Receivables 20", "prime", 1),
    ("Fifth Third", r"^Fifth Third Auto Trust", "prime", 1),
    ("Mercedes-Benz", r"^Mercedes-Benz Auto Receivables Trust", "prime", 1),
    ("Volkswagen", r"^Volkswagen Auto Loan Enhanced Trust", "prime", 1),
    ("BMW", r"^BMW Vehicle Owner Trust", "prime", 1),
]
LINE = re.compile(r"^(ABS-EE)\s+(.*?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(edgar/\S+)\s*$")

# parquet column -> (Schedule AL tag, type)
FIELDS = {
    "asset": ("assetNumber", str), "period_end": ("reportingPeriodEndingDate", "ymd"),
    "originator": ("originatorName", str), "orig_ym": ("originationDate", "my"),
    "orig_amt": ("originalLoanAmount", float), "term": ("originalLoanTerm", int),
    "rate": ("originalInterestRatePercentage", float), "make": ("vehicleManufacturerName", str),
    "model": ("vehicleModelName", str), "model_year": ("vehicleModelYear", int),
    "new_used": ("vehicleNewUsedCode", int), "veh_value": ("vehicleValueAmount", float),
    "score_type": ("obligorCreditScoreType", str), "score": ("obligorCreditScore", int),
    "pti": ("paymentToIncomePercentage", float), "state": ("obligorGeographicLocation", str),
    "added": ("assetAddedIndicator", bool), "modified": ("reportingPeriodModificationIndicator", bool),
    "beg_bal": ("reportingPeriodBeginningLoanBalanceAmount", float),
    "end_bal": ("reportingPeriodActualEndBalanceAmount", float),
    "sched": ("reportingPeriodScheduledPaymentAmount", float), "paid": ("totalActualAmountPaid", float),
    "zb_code": ("zeroBalanceCode", str), "zb_date": ("zeroBalanceEffectiveDate", "my"),
    "dpd": ("currentDelinquencyStatus", int), "chargeoff": ("chargedoffPrincipalAmount", float),
    "recovered": ("recoveredAmount", float), "extended": ("paymentExtendedNumber", int),
    "repo": ("repossessedIndicator", bool),
}
TYPES = {int: pa.int32(), float: pa.float64(), bool: pa.bool_(), str: pa.string(), "ymd": pa.string(), "my": pa.string()}
SCHEMA = pa.schema([(k, TYPES[t]) for k, (_, t) in FIELDS.items()] +
                   [("family", pa.string()), ("tier", pa.string()), ("trust", pa.string())])
TAG2COL = {tag: (col, t) for col, (tag, t) in FIELDS.items()}


def _conv(v: str | None, t):
    if v is None or v.strip() == "" or v.strip().lower() in ("none", "null", "n/a"):
        return None
    v = v.strip()
    try:
        if t is int:
            return int(float(v))
        if t is float:
            return float(v)
        if t is bool:
            return v.lower() in ("true", "1", "y")
        if t == "ymd":  # MM-DD-YYYY -> YYYY-MM
            m, _, y = re.split(r"[-/]", v)
            return f"{y}-{int(m):02d}"
        if t == "my":  # MM/YYYY -> YYYY-MM
            parts = re.split(r"[-/]", v)
            return f"{parts[-1]}-{int(parts[0]):02d}"
    except (ValueError, IndexError):
        return None
    return v


def index_lines():
    for q in QUARTERS:
        path = os.path.join(edgar.CACHE, f"form-{q.replace('/QTR', 'Q')}.idx")
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(edgar.get(f"https://www.sec.gov/Archives/edgar/full-index/{q}/form.idx", cache=False))
        for line in open(path, encoding="latin-1"):
            m = LINE.match(line)
            if m:
                yield dict(name=m.group(2).strip(), cik=m.group(3), date=m.group(4), path=m.group(5))


def vintage(name: str) -> tuple:
    m = re.search(r"(20\d\d)[- ]?([A-Z]*)[- ]?(\d*)", name)
    return (int(m.group(1)), m.group(2), int(m.group(3) or 0)) if m else (0, "", 0)


def select():
    by_trust: dict[str, list[dict]] = {}
    for r in index_lines():
        by_trust.setdefault(r["name"], []).append(r)
    plan = []
    for family, pat, tier, k in FAMILIES:
        trusts = sorted((n for n in by_trust if re.search(pat, n, re.I) and len(by_trust[n]) >= 3), key=vintage)
        if not trusts:
            continue
        newest = trusts[-1]
        picks = [newest]
        if k > 1 and len(trusts) > 1:  # an older pool too, so seasoned loans are covered
            target = vintage(newest)[0] - 2
            picks.append(min(trusts[:-1], key=lambda n: (abs(vintage(n)[0] - target), -vintage(n)[0])))
        elif k == 1 and len(trusts) > 1:  # a pool about two years old: through its early months, not run off
            target = vintage(newest)[0] - 2
            picks = [min(trusts, key=lambda n: (abs(vintage(n)[0] - target), -vintage(n)[0]))]
        for t in picks:
            filings = sorted(by_trust[t], key=lambda r: r["date"])[-2:]  # the two latest monthly reports
            for f in filings:
                plan.append(dict(family=family, tier=tier, trust=t, **f))
    return plan


def xml_url(f: dict) -> tuple[str, int]:
    acc = f["path"].rsplit("/", 1)[1].replace(".txt", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{f['cik']}/{acc.replace('-', '')}"
    items = edgar.get_json(base + "/index.json")["directory"]["item"]
    # the asset data is Exhibit 102; Exhibit 103 is a short narrative. Names vary ("narot24aex102_0624-1030.xml")
    xmls = [i for i in items if i["name"].lower().endswith(".xml")
            and not re.search(r"ex(h|hibit)?[-_ ]?103", i["name"], re.I)]
    if not xmls:
        raise FileNotFoundError(f"no asset-data XML in {base}")
    best = max(xmls, key=lambda i: int(i.get("size") or 0))
    return f"{base}/{best['name']}", int(best.get("size") or 0)


def parse(xml_path: str, extra: dict) -> pa.Table:
    cols = {c: [] for c in FIELDS}
    row: dict = {}
    ctx = ET.iterparse(xml_path, events=("start", "end"))
    _, root = next(ctx)
    n = 0
    for ev, el in ctx:
        if ev != "end":
            continue
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "assets":
            for c in FIELDS:
                cols[c].append(row.get(c))
            row = {}
            n += 1
            if n % 2000 == 0:
                root.clear()
        elif tag in TAG2COL:
            c, t = TAG2COL[tag]
            row[c] = _conv(el.text, t)
        el.clear()
    arrays = {c: pa.array(v, type=TYPES[FIELDS[c][1]]) for c, v in cols.items()}
    k = len(cols["asset"])
    for c in ("family", "tier", "trust"):
        arrays[c] = pa.array([extra[c]] * k, type=pa.string())
    return pa.table(arrays, schema=SCHEMA)


def fetch(plan, keep_xml=False):
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "manifest.json")
    man = json.load(open(man_path)) if os.path.exists(man_path) else {}
    for i, f in enumerate(plan, 1):
        acc = f["path"].rsplit("/", 1)[1].replace(".txt", "")
        dest = os.path.join(OUT, f"{acc}.parquet")
        if acc in man and os.path.exists(dest):
            continue
        t0 = time.time()
        url, size = xml_url(f)
        xml = os.path.join(OUT, f"{acc}.xml")
        edgar.download(url, xml)
        t1 = time.time()
        tbl = parse(xml, f)
        pq.write_table(tbl, dest, compression="zstd")
        periods = sorted(set(tbl.column("period_end").to_pylist()) - {None})
        man[acc] = dict(family=f["family"], tier=f["tier"], trust=f["trust"], cik=f["cik"], filed=f["date"],
                        url=url, xml_bytes=os.path.getsize(xml), rows=tbl.num_rows, periods=periods)
        if not keep_xml:
            os.remove(xml)
        json.dump(man, open(man_path, "w"), indent=1)
        print(f"[{i}/{len(plan)}] {f['trust']} filed {f['date']}: {tbl.num_rows:,} loans, period {periods} "
              f"(download {t1 - t0:.0f}s, parse {time.time() - t1:.0f}s)", flush=True)
    return man


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "fetch"])
    ap.add_argument("--keep-xml", action="store_true")
    a = ap.parse_args(argv)
    plan = select()
    if a.cmd == "select":
        for f in plan:
            print(f"{f['tier']:10} {f['family']:28} {f['trust']:55} {f['date']}")
        print(f"{len(plan)} filings, {len({f['trust'] for f in plan})} trusts, {len({f['family'] for f in plan})} lenders")
        return
    fetch(plan, a.keep_xml)


if __name__ == "__main__":
    sys.exit(main())
