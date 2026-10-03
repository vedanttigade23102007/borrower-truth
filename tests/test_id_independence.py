"""No check may depend on how an ID is spelled (fixed 3 Oct 2026: several checks only looked at loan IDs starting "A-"
and credit lines ending "A", this project's own synthetic naming; a real lender's file would have made them see
nothing and still say "ok"). A book with realistic random loan, credit-line and borrower IDs must give the same cases,
compared through the mapping. And a check whose starting list is empty for a borrower that has loans says "not run"."""
import json

import pyarrow.parquet as pq
import pytest

from bt.datagen.generate import main as generate
from bt.pipeline.run import run as pipeline
from rename_ids import rename


@pytest.fixture(scope="module")
def books(tmp_path_factory):
    root = tmp_path_factory.mktemp("ids")
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(root / "orig")])
    maps = rename(str(root / "orig"), str(root / "renamed"))
    return root / "orig", root / "renamed", maps


def _view(cases, to_old=None):
    """What an officer sees per borrower: verdict, findings, and each clue's type, strength and month."""
    to_old = to_old or {}
    return {to_old.get(c["borrower_id"], c["borrower_id"]): (
        c["verdict"], sorted((f["mechanism"], f["confidence"]) for f in c["findings"]),
        sorted((x["type"], round(x["severity"], 3), round(x["confidence"], 3), x["observed_month"]) for x in c["signals"]))
        for c in cases}


@pytest.mark.parametrize("as_of", [11, 23])
def test_realistic_ids_give_the_same_cases(books, as_of):
    orig, renamed, maps = books
    sample = pq.read_table(renamed / "tape.parquet", columns=["asset_id", "facility_id"]).slice(0, 3).to_pylist()
    assert not any(r["asset_id"].startswith(("A-", "X-")) or r["facility_id"].endswith(("A", "B")) for r in sample)
    _, a, _ = pipeline(str(orig), as_of)
    _, b, _ = pipeline(str(renamed), as_of)
    inv = {new: old for old, new in maps["b"].items()}
    va, vb = _view(a), _view(b, inv)
    assert va.keys() == vb.keys()
    differ = {k: (va[k], vb[k]) for k in va if va[k] != vb[k]}
    assert not differ, json.dumps(differ, default=str)[:3000]


def test_a_check_with_an_empty_starting_list_says_not_run(books, tmp_path):
    import shutil
    orig, _, _ = books
    book = tmp_path / "b"
    shutil.copytree(orig, book)
    fac = pq.read_table(book / "facilities.parquet").to_pylist()
    tape = pq.read_table(book / "tape.parquet", columns=["borrower_id"]).column("borrower_id").to_pylist()
    b = sorted(set(tape))[0]
    # the bank's facility records lose this borrower's warehouse line: its loans are no longer on a borrowing-base line
    import pyarrow as pa
    rows = [dict(r, kind="term") if r["borrower_id"] == b else r for r in fac]
    pq.write_table(pa.Table.from_pylist(rows, schema=pq.read_schema(book / "facilities.parquet")), book / "facilities.parquet")
    _, cases, m = pipeline(str(book), 23)
    case = next(c for c in cases if c["borrower_id"] == b)
    assert "not run for this borrower" in case["coverage"]["S2"] and case["coverage"]["S2"].startswith("partial")
    assert "borrowing-base" in case["coverage"]["S2"]
    other = next(c for c in cases if c["borrower_id"] != b and c["borrower_id"] in set(tape))
    assert other["coverage"]["S2"] == "ok"  # looked and found what it found: stays "ok"
    assert m["not_run_for_some_borrowers"]["S2"] >= 1


def test_payments_that_never_name_a_loan_are_not_run_not_a_flood(books, tmp_path):
    import shutil
    import pyarrow as pa
    orig, _, _ = books
    book = tmp_path / "b"
    shutil.copytree(orig, book)
    tape_b = set(pq.read_table(book / "tape.parquet", columns=["borrower_id"]).column("borrower_id").to_pylist())
    b = sorted(tape_b)[0]
    pay = pq.read_table(book / "payments.parquet")
    rows = [dict(r, ref=f"LOCKBOX-{i}") if r["borrower_id"] == b else r for i, r in enumerate(pay.to_pylist())]
    pq.write_table(pa.Table.from_pylist(rows, schema=pay.schema), book / "payments.parquet")
    sigs, cases, _ = pipeline(str(book), 23)
    case = next(c for c in cases if c["borrower_id"] == b)
    assert "the payment checks not run for this borrower" in case["coverage"]["S2"]
    assert not [s for s in sigs if s.entity_id == b and s.type in ("CURRENT_WITHOUT_PAYMENT", "TARGETED_SOURCE_MISMATCH")
                and "no_payment" in " ".join(s.evidence)]
