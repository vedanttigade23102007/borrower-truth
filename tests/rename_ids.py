"""Give a book realistic, random loan, credit-line and borrower IDs, the same way through every table.

The synthetic generator names things its own way (B0001, F0001A, A-B0001-000123). A bank's lender files won't, and
no check may depend on how an ID is spelled. Used by tests/test_id_independence.py and the mapper round trip.
"""
import json
import os
import random

import pyarrow as pa
import pyarrow.parquet as pq

# table -> {column: which ID it holds}
COLUMNS = {
    "borrowers": {"borrower_id": "b"},
    "facilities": {"facility_id": "f", "borrower_id": "b"},
    "tape": {"borrower_id": "b", "facility_id": "f", "asset_id": "a"},
    "source_truth": {"borrower_id": "b", "asset_id": "a"},
    "payments": {"borrower_id": "b", "account_id": "acct", "ref": "a?"},
    "outflows": {"borrower_id": "b", "account_id": "acct"},
    "invoices": {"borrower_id": "b", "facility_id": "f"},
    "pledgecheck": {"borrower_id": "b", "facility_id": "f"},
    "disclosures": {"borrower_id": "b"},
    "financials": {"borrower_id": "b"},
    "sec_filings": {"borrower_id": "b"},
    "public_abs": {"issuer_borrower_id": "b"},
}


def rename(src: str, dst: str, seed: int = 7) -> dict:
    """Copy the book in `src` to `dst` with new IDs. Returns {kind: {old: new}}."""
    rng = random.Random(seed)
    used: set = set()

    def fresh(make):
        while True:
            x = make()
            if x not in used:
                used.add(x)
                return x

    maps: dict = {"b": {}, "f": {}, "a": {}, "acct": {}}
    make = {"b": lambda: f"{rng.randrange(10**6, 10**7)}",                     # a customer number
            "f": lambda: f"LN{rng.randrange(10**5, 10**6)}",                    # a credit-line number, no kind in it
            "a": lambda: f"{rng.randrange(10**9):010d}",                        # a loan number, leading zeros kept
            "acct": lambda: f"{rng.randrange(10**11, 10**12)}"}                 # a deposit account number

    def new(kind, old):
        if old is None:
            return None
        m = maps[kind]
        if old not in m:
            m[old] = fresh(make[kind])
        return m[old]

    os.makedirs(dst, exist_ok=True)
    tables = {f[:-8]: pq.read_table(os.path.join(src, f)) for f in sorted(os.listdir(src)) if f.endswith(".parquet")}
    # loans first, so a payment's reference is renamed only when it names a loan (invoice numbers stay as they are)
    for t in ("tape", "source_truth"):
        for x in tables[t].column("asset_id").to_pylist():
            new("a", x)
    for name, tbl in tables.items():
        cols = COLUMNS.get(name, {})
        for col, kind in cols.items():
            if col not in tbl.schema.names:
                continue
            vals = tbl.column(col).to_pylist()
            if kind == "a?":
                vals = [maps["a"].get(v, v) for v in vals]
            else:
                vals = [new(kind, v) for v in vals]
            tbl = tbl.set_column(tbl.schema.get_field_index(col), col, pa.array(vals, type=tbl.schema.field(col).type))
        pq.write_table(tbl, os.path.join(dst, f"{name}.parquet"))
    for f in os.listdir(src):
        if f.endswith(".json"):
            j = json.load(open(os.path.join(src, f)))
            if f == "labels.json":
                j = {maps["b"].get(k, k): v for k, v in j.items()}
            json.dump(j, open(os.path.join(dst, f), "w"))
    return maps

