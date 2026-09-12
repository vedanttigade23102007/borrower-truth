"""Every number deterministic, every decision replayable (design §5, AUDIT)."""
import pyarrow.parquet as pq
import pytest

from bt.datagen.generate import main as generate
from bt.pipeline import record
from bt.pipeline.replay import replay
from bt.pipeline.run import main as cli
from bt.pipeline.run import run as pipeline


@pytest.fixture()
def book(tmp_path):
    out = tmp_path / "book"
    generate(["--borrowers", "40", "--scale", "0.3", "--seed", "17", "--out", str(out)])
    return out


def test_same_inputs_same_decisions(book):
    _, a, _ = pipeline(str(book), 23)
    _, b, _ = pipeline(str(book), 23)
    assert [record.result_digest(c) for c in a] == [record.result_digest(c) for c in b]
    assert [c["decision"]["decision_id"] for c in a] == [c["decision"]["decision_id"] for c in b]


def test_recorded_run_replays_identically(book):
    cli(["--data", str(book), "--out", str(book / "run")])
    rep = replay(str(book), str(book / "run"))
    assert rep["replayed"] == 40 and rep["identical"] == 40 and not rep["different"]
    assert rep["inputs_changed"] == [] and rep["rules_changed"] is False


def test_replay_names_the_input_that_changed(book):
    cli(["--data", str(book), "--out", str(book / "run")])
    t = pq.read_table(book / "ucc_filings.parquet")
    pq.write_table(t.slice(0, t.num_rows - 3), book / "ucc_filings.parquet")  # someone edits an input
    rep = replay(str(book), str(book / "run"))
    assert "ucc_filings" in rep["inputs_changed"]
