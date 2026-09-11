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
from bt.pipeline import dq
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
