"""Fallback behaviour promised in design §12: bad files are quarantined, public data
serves a stale cache when the source is down, and runs always complete."""
import json
import os
import urllib.error

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bt.adapters import gleif
from bt.datagen.generate import main as generate
from bt.pipeline import contract, dq
from bt.pipeline.run import run as pipeline


@pytest.fixture()
def book(tmp_path):
    out = tmp_path / "book"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(out)])
    return out


def _break_tape(book):
    t = pq.read_table(book / "tape.parquet").drop(["vin"])  # schema failure
    pq.write_table(t, book / "tape.parquet")
    os.utime(book / "tape.parquet")


def test_bad_file_uses_last_good_copy(book):
    _, cases_ok, m_ok = pipeline(str(book), 23)  # first run records last-good copies
    assert not m_ok["data_quality"]["quarantined"]
    _break_tape(book)
    _, cases, m = pipeline(str(book), 23)
    q = m["data_quality"]["quarantined"]
    assert "tape" in q and q["tape"]["using"] == "last good copy"
    assert m["S1"]["status"] == "ok" and m["S2"]["status"] == "ok"
    assert cases[0]["coverage"]["data"].startswith("quarantined")
    # same answers as before the file broke, because the last good copy was used
    assert sorted((c["borrower_id"], c["verdict"]) for c in cases) == sorted((c["borrower_id"], c["verdict"]) for c in cases_ok)


def test_bad_file_without_last_good_degrades_not_crashes(book):
    _break_tape(book)
    _, cases, m = pipeline(str(book), 23)
    assert m["data_quality"]["quarantined"]["tape"]["using"] == "empty table"
    assert len(cases) == 30  # the run still completes


@pytest.mark.parametrize("missing, system, status", [
    ("tape", "S2", "not run"), ("source_truth", "S2", "partial"), ("pledgecheck", "S1", "partial"),
    ("outflows", "S3", "partial"), ("invoices", "S4", "not run"), ("ucc_filings", "S5", "partial"),
    ("gleif", "S6", "not run"), ("financials", "S7", "not run")])
def test_a_missing_input_is_never_a_clean_result(book, missing, system, status):
    """The data contract: an input that never arrived shows on every case, it doesn't read as "nothing found"."""
    os.remove(book / f"{missing}.parquet")
    _, cases, m = pipeline(str(book), 23)
    assert m[system]["status"] == status
    assert all(c["coverage"][system].startswith(status + ": ") and "not delivered" in c["coverage"][system] for c in cases)
    assert contract.INPUTS[missing] in m["data_quality"]["not_delivered"]


def test_missing_inputs_invent_no_clues(book):
    # read as empty tables, these made every pulled loan look "gone" and every borrower "not enrolled"
    _, cases_ok, _ = pipeline(str(book), 23)
    os.remove(book / "source_truth.parquet")
    os.remove(book / "pledgecheck.parquet")
    sigs, cases, _ = pipeline(str(book), 23)
    types = {s.type for s in sigs}
    assert not types & {"SOURCE_MISMATCH", "TARGETED_SOURCE_MISMATCH", "PLEDGECHECK_ABSENT"}
    flagged = lambda cs: {c["borrower_id"] for c in cs if c["verdict"] == "LIKELY_FRAUD"}  # noqa: E731
    assert flagged(cases) <= flagged(cases_ok)  # less coverage can lose a fraud, never invent one


def test_a_delivered_empty_file_is_not_missing(book):
    t = pq.read_table(book / "tape.parquet")
    pq.write_table(t.slice(0, 0), book / "tape.parquet")  # delivered, nothing in it
    _, _, m = pipeline(str(book), 23)
    assert m["S2"]["status"] == "ok" and not m["data_quality"]["not_delivered"]


def test_a_missing_core_input_stops_the_run(book):
    os.remove(book / "disclosures.parquet")  # with no disclosures every lien would look undisclosed
    with pytest.raises(FileNotFoundError, match="core input"):
        pipeline(str(book), 23)


def test_the_document_module_is_off_by_default(book):
    import pyarrow as pa
    inv = pq.read_table(book / "invoices.parquet").slice(0, 3).to_pylist()
    reads = [dict(invoice_id=r["invoice_id"], borrower_id=r["borrower_id"], doc_mismatch=True, reads_agree=True) for r in inv]
    pq.write_table(pa.Table.from_pylist(reads), book / "doc_reads.parquet")
    sigs, cases, m = pipeline(str(book), 23)
    assert m["document_model"] == "off" and "documents" not in cases[0]["coverage"]
    assert not any(s.type == "DOC_DATA_MISMATCH" for s in sigs)  # the reads are there, but the module is off
    sigs, cases, m = pipeline(str(book), 23, document_model=True)
    assert m["document_model"] == "on" and cases[0]["coverage"]["documents"].startswith("ok")
    assert any(s.type == "DOC_DATA_MISMATCH" for s in sigs)
    assert m["manifest"]["document_model"] is True and "doc_reads" in m["manifest"]["inputs"]


def test_command_line_runs_end_to_end(book, capsys):
    """The CLI (what demo.sh and Airflow call) must complete and print its summary."""
    from bt.pipeline.run import main as cli
    cli(["--data", str(book), "--out", str(book / "run")])
    out = capsys.readouterr().out
    assert "as_of month 23" in out and "data      ok" in out
    assert (book / "run" / "cases.json").exists()


def test_dq_flags_negative_payments(book):
    t = pq.read_table(book / "payments.parquet")
    amounts = t.column("amount").to_pylist()
    amounts[0] = -5.0
    pq.write_table(t.set_column(t.schema.get_field_index("amount"), "amount", pa.array(amounts)), book / "payments.parquet")
    assert any("negative" in i for i in dq.check(str(book / "payments.parquet"), "payments"))


def test_gleif_serves_stale_cache_when_down(tmp_path, monkeypatch):
    monkeypatch.setattr(gleif, "CACHE_DIR", str(tmp_path))
    url = f"{gleif.API}/lei-records?x=1"
    path = tmp_path / (gleif.hashlib.sha1(url.encode()).hexdigest() + ".json")
    json.dump({"url": url, "fetched_at": 0, "body": {"data": []}}, open(path, "w"))  # old cache entry

    def down(*a, **k):
        raise urllib.error.URLError("simulated outage")

    monkeypatch.setattr(gleif.urllib.request, "urlopen", down)
    body, stale, fetched = gleif._get(url)
    assert stale is True and fetched == 0 and body == {"data": []}


def test_gleif_down_with_no_cache_raises_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(gleif, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(gleif.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down")))
    with pytest.raises(gleif.GleifUnavailable):
        gleif._get(f"{gleif.API}/lei-records?x=2")
