"""Shared context for the seven systems.

`Ctx` exposes every input as a DuckDB view cut off at `as_of` (a month index),
so the same code runs "live" (as_of = latest month) and in the 24-month replay
used to measure how early each fraud is caught. Systems only ever see what
existed at `as_of`, never the future and never labels.json.
"""
from __future__ import annotations

import hashlib
import os

import duckdb
import pyarrow.parquet as pq

from bt.common import network
from bt.common.signal import Signal

# Columns for tables that can legitimately be empty in a small book.
EMPTY_SCHEMAS = {
    "court_records": "case_id VARCHAR, defendant_name VARCHAR, plaintiff VARCHAR, kind VARCHAR, amount DOUBLE, month BIGINT",
    "pledgecheck": "borrower_id VARCHAR, facility_id VARCHAR, month BIGINT, enrolled BOOLEAN, uniqueness VARCHAR, "
                   "data_integrity VARCHAR, completeness VARCHAR, single_record VARCHAR",
    "invoices": "borrower_id VARCHAR, invoice_id VARCHAR, facility_id VARCHAR, pledged_month BIGINT, invoice_number VARCHAR, "
                "po_number VARCHAR, debtor_id VARCHAR, debtor_name VARCHAR, issue_month BIGINT, issue_day BIGINT, "
                "due_days BIGINT, amount DOUBLE, description VARCHAR",
    "tape": "month SMALLINT, facility_id VARCHAR, borrower_id VARCHAR, asset_id VARCHAR, vin VARCHAR, obligor_id VARCHAR, "
            "balance DOUBLE, dpd_bucket_reported TINYINT, deferred_flag TINYINT, eligible_reported BOOLEAN",
    "source_truth": "month SMALLINT, borrower_id VARCHAR, asset_id VARCHAR, dpd_bucket_true TINYINT, balance_true DOUBLE",
    "outflows": "txn_id VARCHAR, month SMALLINT, day TINYINT, borrower_id VARCHAR, account_id VARCHAR, payee_id VARCHAR, "
                "payee_name VARCHAR, amount DOUBLE, memo VARCHAR",
    # public SEC data (generator v3): loan-level reports of the borrower's own public securitizations (no VIN)
    "public_abs": "pool_id VARCHAR, issuer_borrower_id VARCHAR, month SMALLINT, pool_loan_id VARCHAR, orig_month SMALLINT, "
                  "orig_amount DOUBLE, rate DOUBLE, term SMALLINT, make VARCHAR, model VARCHAR, model_year SMALLINT, "
                  "obligor_state VARCHAR, credit_score SMALLINT, dpd_bucket TINYINT",
    # what the borrower (or its parent) filed with the SEC: 10-K debt notes and Exhibit 21, 8-K items, XBRL revenue
    "sec_filings": "borrower_id VARCHAR, form VARCHAR, filed_month BIGINT, item VARCHAR, counterparty_entity_id VARCHAR, "
                   "counterparty_name VARCHAR, amount DOUBLE, quarter BIGINT, note VARCHAR",
    # not delivered: the check that needs it doesn't run (bt.pipeline.contract); the empty table only keeps queries valid
    "gleif": "lei VARCHAR, entity_id VARCHAR, legal_name VARCHAR, parent_entity_id VARCHAR",
    "ucc_filings": "filing_id VARCHAR, state VARCHAR, debtor_name VARCHAR, debtor_address VARCHAR, secured_party_name VARCHAR, "
                   "collateral_desc VARCHAR, filed_month BIGINT",
    "financials": "borrower_id VARCHAR, quarter BIGINT, revenue_reported DOUBLE, receivables_reported DOUBLE, cash_reported DOUBLE, "
                  "debt_reported DOUBLE, covenant_metric_reported DOUBLE, covenant_threshold DOUBLE",
    "persons": "person_id VARCHAR, name VARCHAR",
    "facilities": "facility_id VARCHAR, borrower_id VARCHAR, lender_entity_id VARCHAR, kind VARCHAR, limit DOUBLE, advance_rate DOUBLE",
}

# view name -> (file, time filter using {a} = as_of)
VIEWS = {
    "borrowers": ("borrowers", None),
    "facilities": ("facilities", None),
    "persons": ("persons", None),
    "gleif": ("gleif", None),
    "entities": ("entities", "formed_month <= {a}"),
    "disclosures": ("disclosures", "start_month <= {a}"),
    "ucc": ("ucc_filings", "filed_month <= {a}"),
    "courts": ("court_records", "month <= {a}"),
    "financials": ("financials", "quarter * 3 + 2 <= {a}"),
    "pledgecheck": ("pledgecheck", "month <= {a}"),
    "tape": ("tape", "month <= {a}"),
    "source_truth": ("source_truth", "month <= {a}"),
    "payments": ("payments", "month <= {a}"),
    "outflows": ("outflows", "month <= {a}"),  # the borrower's operating account at WF (older books: empty)
    "invoices": ("invoices", "pledged_month <= {a}"),
    "public_abs": ("public_abs", "month <= {a}"),  # older books: empty
    "sec_filings": ("sec_filings", "filed_month <= {a}"),  # older books: empty
}

# The credit lines advanced against a borrowing base (warehouse lines), from the bank's own facility records. The tape
# checks look at the loans pledged to these lines, whatever the lender calls its loans and lines: no check may depend on
# how an ID is spelled (until 3 Oct 2026 several did, on this project's own synthetic naming).
WAREHOUSE = "facility_id IN (SELECT facility_id FROM facilities WHERE kind = 'warehouse')"

# per borrower: loan rows on any line, on warehouse lines, on this month's tape; payments, and how many name one of its
# loan numbers. A check whose starting list is empty for a borrower that has loans reports "not run", never "ok"
LOAN_SCOPE = """
WITH f AS (SELECT facility_id FROM facilities WHERE kind = 'warehouse'),
t AS (SELECT tape.borrower_id, count(*) AS rows_any, count(f.facility_id) AS rows_wh,
             count(f.facility_id) FILTER (WHERE tape.month = ?) AS rows_now
      FROM tape LEFT JOIN f USING (facility_id) GROUP BY 1),
ids AS (SELECT DISTINCT borrower_id, asset_id FROM tape),
p AS (SELECT p.borrower_id, count(*) AS pays, count(ids.asset_id) AS pays_loans
      FROM payments p LEFT JOIN ids ON ids.borrower_id = p.borrower_id AND ids.asset_id = p.ref GROUP BY 1)
SELECT t.borrower_id, t.rows_any, t.rows_wh, t.rows_now, coalesce(p.pays, 0) AS pays, coalesce(p.pays_loans, 0) AS pays_loans
FROM t LEFT JOIN p USING (borrower_id) ORDER BY 1
"""

NORM_MACRO = ("CREATE OR REPLACE MACRO norm(s) AS "
              "trim(regexp_replace(regexp_replace(upper(s), '[^A-Z0-9 ]', '', 'g'), ' +', ' ', 'g'))")


class Ctx:
    def __init__(self, data_dir: str, as_of: int = 23, con: duckdb.DuckDBPyConnection | None = None,
                 materialize: bool = False, overrides: dict[str, str] | None = None):
        self.data_dir = os.path.abspath(data_dir)
        self.as_of = int(as_of)
        # data-quality gate: file name -> replacement path ("" = quarantined, no fallback -> empty table)
        self.overrides = overrides or {}
        self.con = con or duckdb.connect(config=network.duckdb_config())
        self.shared: dict = {}
        self.explanations: dict[str, list[str]] = {}
        self.con.execute(NORM_MACRO)
        for view, (fname, where) in VIEWS.items():
            src = self._source(fname)
            sql = src if where is None else f"SELECT * FROM ({src}) WHERE {where.format(a=self.as_of)}"
            kind = "TABLE" if materialize else "VIEW"
            self.con.execute(f"CREATE OR REPLACE {kind} {view} AS {sql}")

    def _source(self, fname: str) -> str:
        p = self.overrides.get(fname, os.path.join(self.data_dir, f"{fname}.parquet"))
        if p and os.path.exists(p) and len(pq.read_schema(p)) > 0:
            return f"SELECT * FROM read_parquet('{p}')"
        if fname in EMPTY_SCHEMAS:
            cols = ", ".join(f"CAST(NULL AS {c.split()[1]}) AS \"{c.split()[0]}\"" for c in EMPTY_SCHEMAS[fname].split(", "))
            return f"SELECT {cols} WHERE false"
        raise FileNotFoundError(f"{fname}: a core input was not delivered and there is no last good copy, so the run stops")

    def rows(self, sql: str, params=None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def explain(self, borrower_id: str, text: str):
        self.explanations.setdefault(borrower_id, []).append(text)

    def not_run(self, system: str, borrower: str, check: str, why: str):
        """A check's starting list came back empty for a borrower that has items of the kind it checks: "not run" for
        that borrower, never a silent "ok", and the check skips it rather than invent clues from the gap. A check that
        looked and found nothing meeting its condition is not this: it stays "ok"."""
        self.shared.setdefault("not_run", {}).setdefault(borrower, {}).setdefault(system, []).append((check, why))

    def skipped(self, system: str, borrower: str, check: str) -> bool:
        return any(c == check for c, _ in self.shared.get("not_run", {}).get(borrower, {}).get(system, []))

    def loan_scope(self) -> dict:
        if "loan_scope" not in self.shared:
            self.shared["loan_scope"] = {r["borrower_id"]: r for r in self.rows(LOAN_SCOPE, [self.as_of])}
        return self.shared["loan_scope"]


def sig(system: str, borrower: str, typ: str, severity: float, confidence: float, evidence, explanation: str,
        month: int, related=()) -> Signal:
    ev = tuple(str(e) for e in evidence)
    h = hashlib.md5("|".join((system, borrower, typ, *ev)).encode()).hexdigest()[:8]
    return Signal(f"{system}-{borrower}-{typ}-{h}", borrower, system, typ,
                  round(min(max(severity, 0.0), 1.0), 3), round(min(max(confidence, 0.0), 1.0), 3),
                  ev, explanation, int(month), tuple(related))
