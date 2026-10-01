"""The red-team harness's own judgements (RED-TEAM-PLAN.md): which changes a borrower controls, and the leak scan."""
import shutil

import pyarrow.parquet as pq
import pytest

from bt.datagen.generate import main as generate
from bt.eval import redteam


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("rt") / "book"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(out)])
    return out


def edit(book, table, fn):
    rows = pq.read_table(book / f"{table}.parquet").to_pylist()
    rows = fn(rows)
    pq.write_table(pq.read_table(book / f"{table}.parquet").from_pylist(rows, schema=pq.read_schema(book / f"{table}.parquet")),
                   book / f"{table}.parquet")


def fresh(book, tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    shutil.copytree(book, before)
    shutil.copytree(book, after)
    return before, after


def test_a_borrowers_own_reports_are_its_to_change(book, tmp_path):
    before, after = fresh(book, tmp_path)
    b = pq.read_table(before / "tape.parquet").column("borrower_id")[0].as_py()
    edit(after, "tape", lambda rows: [dict(r, dpd_bucket_reported=0) if r["borrower_id"] == b else r for r in rows])
    assert redteam.lever_violations(str(before), str(after), b) == ([], False)


def test_what_a_borrower_doesnt_control_is_refused(book, tmp_path):
    before, after = fresh(book, tmp_path)
    b = pq.read_table(before / "tape.parquet").column("borrower_id")[0].as_py()
    edit(after, "ucc_filings", lambda rows: rows[1:])                                   # someone else's lien filing
    edit(after, "payments", lambda rows: [dict(r, amount=r["amount"] + 1) if i == 0 else r for i, r in enumerate(rows)])
    edit(after, "tape", lambda rows: [dict(r, balance=1.0) if r["borrower_id"] != b else r for r in rows])
    problems, _ = redteam.lever_violations(str(before), str(after), b)
    text = " ".join(problems)
    assert "ucc_filings" in text and "payments" in text and "other borrowers" in text


def test_the_servicer_lever_is_flagged(book, tmp_path):
    before, after = fresh(book, tmp_path)
    b = pq.read_table(before / "source_truth.parquet").column("borrower_id")[0].as_py()
    edit(after, "source_truth", lambda rows: [dict(r, dpd_bucket_true=0) if r["borrower_id"] == b else r for r in rows])
    assert redteam.lever_violations(str(before), str(after), b) == ([], True)


def test_the_leak_scan_finds_our_internal_names(tmp_path):
    (tmp_path / "README.md").write_text("Use TARGETED_SOURCE_MISMATCH to dodge S2, says Borrower Truth.")
    terms = {h["term"] for h in redteam.scan(str(tmp_path))["hits"]}
    assert {"TARGETED_SOURCE_MISMATCH", "S2", "Borrower Truth"} <= terms
