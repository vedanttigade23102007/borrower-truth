"""The data contract in code (DATA-CONTRACT.md): which inputs each check needs, and what a missing one costs.

A file that never arrived is not a file with nothing in it. Read as an empty table, a missing input made checks report
"ok" while seeing nothing, or worse, see things that weren't there. On dev book 7: no loan tape lost 13 of 50 frauds
and turned 2,030 payments into "unknown payer" clues; no servicer records flagged 47 honest borrowers, because every
loan pulled from the servicer system looked "gone". All with every check marked "ok".

So: a check whose needed input wasn't delivered doesn't run. A check missing an optional input runs without the
clues that input decides, and drops the ones an empty table would make up. Every case says which.
A delivered file with no rows is fine: it means there is nothing to report.
"""
from __future__ import annotations

import os

import pyarrow.parquet as pq

# input file -> what it is, in the officer's words
INPUTS = {
    "borrowers": "borrower list",
    "facilities": "credit lines",
    "entities": "company registry",
    "persons": "officers and owners",
    "gleif": "LEI register (GLEIF)",
    "disclosures": "borrower disclosures",
    "ucc_filings": "lien filings",
    "court_records": "court judgments",
    "financials": "financial statements",
    "pledgecheck": "PledgeCheck results",
    "tape": "loan tape",
    "source_truth": "servicer-system records",
    "payments": "collection-account payments",
    "outflows": "operating-account outflows",
    "invoices": "pledged invoices",
    "public_abs": "public securitization reports (SEC ABS-EE)",
    "sec_filings": "SEC filings",
}

# without these the run can't be trusted at all (bt.pipeline.dq quarantines them; last good copy or the run stops):
# with no disclosures, every lien and every linked company would look undisclosed
CORE = ("borrowers", "entities", "payments", "disclosures")

# check -> inputs it can't run without
NEEDS = {
    "S2": ("tape",),
    "S3": ("tape", "invoices"),  # who counts as a customer: without them every payer looks unknown
    "S4": ("invoices",),
    "S6": ("gleif",),  # without it every company looks unregistered, so shell scores go up
    "S7": ("financials",),
}

# check -> optional input -> (what isn't checked without it, clue types an empty table would make up)
OPTIONAL = {
    "S1": {
        "pledgecheck": ("pledges of the same collateral at other lenders", ("PLEDGECHECK_ABSENT",)),  # it would call every borrower "not enrolled"
        "tape": ("duplicate vehicles and public-pool overlap", ()),
        "invoices": ("duplicate invoices", ()),
        "public_abs": ("public-pool overlap", ()),
    },
    "S2": {"source_truth": ("servicer-system pulls", ("SOURCE_MISMATCH", "TARGETED_SOURCE_MISMATCH"))},
    "S3": {"outflows": ("round trips and who the borrower pays (undisclosed debt service, cash leakage)", ())},
    "S5": {"ucc_filings": ("liens", ()), "court_records": ("court judgments", ()),
           "sec_filings": ("debt named in SEC filings", ())},
    "S6": {"sec_filings": ("subsidiaries listed in SEC filings", ())},
    "S7": {"sec_filings": ("revenue reported to the SEC", ())},
}


def not_delivered(data_dir: str, overrides: dict[str, str]) -> set[str]:
    """Inputs with no usable file: never delivered, or quarantined with no last good copy."""
    out = set()
    for f in INPUTS:
        p = overrides.get(f, os.path.join(data_dir, f"{f}.parquet"))
        if not (p and os.path.exists(p) and len(pq.read_schema(p)) > 0):
            out.add(f)
    return out


def blocked(system: str, missing: set[str]) -> str | None:
    """Why the check can't run, or None."""
    lost = [INPUTS[f] for f in NEEDS.get(system, ()) if f in missing]
    return f"{' and '.join(lost)} not delivered" if lost else None


def partial(system: str, missing: set[str]) -> tuple[str | None, set[str]]:
    """(what wasn't checked, clue types to drop) for the optional inputs that are missing."""
    notes, drop = [], set()
    for f, (what, types) in OPTIONAL.get(system, {}).items():
        if f in missing:
            notes.append(f"{what} not checked ({INPUTS[f]} not delivered)")
            drop |= set(types)
    return ("; ".join(notes) if notes else None), drop
