import json

import duckdb
import pytest

from bt.common.signal import Signal
from bt.datagen.generate import FRAUD_MECHS, main


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("book")
    main(["--borrowers", "60", "--scale", "0.2", "--seed", "11", "--out", str(out)])
    return out


def test_every_mechanism_is_planted(book):
    labels = json.load(open(book / "labels.json"))
    assert len(labels) == 60
    planted = {m for v in labels.values() for m in v["mechanisms"]}
    assert planted == set(FRAUD_MECHS)


def test_labels_never_leak_into_data_tables(book):
    con = duckdb.connect()
    for f in book.glob("*.parquet"):
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{f}'").fetchall()}
        assert not cols & {"fraud", "mechanisms", "pattern", "planted", "benign"}, f.name


def test_vins_are_marked_synthetic(book):
    con = duckdb.connect()
    bad = con.execute(f"SELECT count(*) FROM '{book / 'tape.parquet'}' WHERE vin NOT LIKE 'SYN%'").fetchone()[0]
    assert bad == 0


def test_dressed_up_loans_exist_where_planted(book):
    labels = json.load(open(book / "labels.json"))
    dressed = [b for b, v in labels.items() if "TAPE_DRESSUP" in v["mechanisms"]]
    assert dressed
    assert any(labels[b]["planted"].get("dressed_asset_months", 0) > 0 for b in dressed)


def test_signal_without_evidence_is_rejected():
    with pytest.raises(ValueError):
        Signal("x", "B0001", "S1", "T", 0.5, 0.5, (), "no evidence", 3)
