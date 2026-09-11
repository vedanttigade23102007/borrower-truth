"""Data-quality gate: quarantine bad input files and fall back to the last good copy.

Design §12: "Bad borrower file (schema or quality failure): quarantined; an alert
goes out; the last good data is kept." Before every run each input file is
checked (readable, required columns, key columns filled, month range, sane
amounts). A file that passes becomes the new last-good copy. A file that fails
is quarantined: the run uses the last-good copy if one exists (otherwise an
empty table), and every case reports it.
"""
from __future__ import annotations

import os
import shutil

import duckdb
import pyarrow.parquet as pq

REQUIRED = {
    "borrowers": ["borrower_id", "entity_id", "name", "btype"],
    "entities": ["entity_id", "name", "kind", "officer_person_id", "address", "formed_month", "has_operations"],
    "tape": ["month", "facility_id", "borrower_id", "asset_id", "vin", "obligor_id", "balance",
             "dpd_bucket_reported", "deferred_flag", "eligible_reported"],
    "source_truth": ["month", "borrower_id", "asset_id", "dpd_bucket_true"],
    "payments": ["txn_id", "month", "borrower_id", "payer_id", "payer_name", "amount", "ref"],
    "invoices": ["invoice_id", "borrower_id", "facility_id", "pledged_month", "invoice_number", "debtor_id",
                 "debtor_name", "issue_month", "due_days", "amount"],
    "ucc_filings": ["filing_id", "debtor_name", "secured_party_name", "collateral_desc", "filed_month"],
    "financials": ["borrower_id", "quarter", "revenue_reported", "covenant_metric_reported", "covenant_threshold"],
    "disclosures": ["borrower_id", "kind", "start_month"],
}
KEYS = {"tape": ["borrower_id", "asset_id", "month"], "payments": ["borrower_id", "amount", "month"],
        "invoices": ["borrower_id", "invoice_number", "amount"], "borrowers": ["borrower_id", "entity_id"]}
MONTHLY = {"tape": "month", "source_truth": "month", "payments": "month", "invoices": "pledged_month"}
CORE = {"borrowers", "entities", "payments"}  # must have rows
MAX_NULL_SHARE = 0.01
LAST_GOOD = ".last_good"


def check(path: str, table: str) -> list[str]:
    if not os.path.exists(path):
        return [] if table not in CORE else ["file missing"]
    try:
        cols = set(pq.read_schema(path).names)
    except Exception as e:
        return [f"unreadable: {type(e).__name__}"]
    issues = [f"missing column {c}" for c in REQUIRED.get(table, []) if c not in cols]
    if issues:
        return issues
    con = duckdb.connect()
    src = f"read_parquet('{path}')"
    n = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    if n == 0:
        return ["no rows"] if table in CORE else []
    for c in KEYS.get(table, []):
        nulls = con.execute(f"SELECT count(*) FILTER (WHERE {c} IS NULL) FROM {src}").fetchone()[0]
        if nulls / n > MAX_NULL_SHARE:
            issues.append(f"{nulls / n:.1%} of {c} is empty")
    if table in MONTHLY:
        lo, hi = con.execute(f"SELECT min({MONTHLY[table]}), max({MONTHLY[table]}) FROM {src}").fetchone()
        if lo is not None and (lo < 0 or hi > 23):
            issues.append(f"{MONTHLY[table]} outside 0..23 ({lo}..{hi})")
    if table == "payments":
        neg = con.execute(f"SELECT count(*) FILTER (WHERE amount < 0) FROM {src}").fetchone()[0]
        if neg:
            issues.append(f"{neg} negative payment amounts")
    return issues


def stage(data_dir: str) -> tuple[dict[str, str], dict]:
    """Returns (overrides: file name -> path to use instead, report)."""
    good_dir = os.path.join(data_dir, LAST_GOOD)
    os.makedirs(good_dir, exist_ok=True)
    overrides, report = {}, {"quarantined": {}, "checked": 0}
    for table in REQUIRED:
        path = os.path.join(data_dir, f"{table}.parquet")
        good = os.path.join(good_dir, f"{table}.parquet")
        issues = check(path, table)
        report["checked"] += 1
        if not issues:
            if os.path.exists(path) and (not os.path.exists(good) or os.path.getmtime(path) > os.path.getmtime(good)):
                shutil.copy2(path, good)
            continue
        fallback = "last good copy" if os.path.exists(good) else "empty table"
        overrides[table] = good if os.path.exists(good) else ""
        report["quarantined"][table] = dict(issues=issues, using=fallback)
    return overrides, report
