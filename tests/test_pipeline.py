import json

import pytest

from bt.combiner.combine import build_cases
from bt.common.signal import Signal
from bt.datagen.generate import main as generate
from bt.pipeline.run import run


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("book")
    generate(["--borrowers", "40", "--scale", "0.2", "--seed", "3", "--out", str(out)])
    return str(out)


def test_all_systems_run_and_every_borrower_gets_a_case(book):
    _, cases, metrics = run(book, 23)
    assert all(metrics[s]["status"] == "ok" for s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"))
    assert len(cases) == len(json.load(open(f"{book}/labels.json")))


@pytest.mark.parametrize("dead", ["S4", "S6"])
def test_a_crashed_system_never_stops_the_run(book, dead):
    _, cases, metrics = run(book, 23, {dead})
    assert metrics[dead]["status"] == "unavailable"
    assert cases and all(c["coverage"][dead] == "unavailable" for c in cases)
    assert metrics["S7"]["status"] == "ok"  # downstream still runs, in degraded mode


def test_replay_never_sees_the_future(book):
    signals, _, _ = run(book, 5)
    assert all(s.observed_month <= 5 for s in signals)


def _s(system, typ, sev, conf, related=()):
    return Signal(f"{system}-B1-{typ}", "B1", system, typ, sev, conf, ("ev:1",), typ, 10, tuple(related))


def _verdict(signals):
    return build_cases(signals, {}, {}, ["B1"])[0]


def test_one_weak_clue_is_not_enough():
    assert _verdict([_s("S7", "COVENANT_EDGE_PATTERN", 0.5, 0.6)])["verdict"] == "NEEDS_MORE_EVIDENCE"


def test_two_independent_sources_corroborate():
    c = _verdict([_s("S7", "CASH_REVENUE_GAP", 0.7, 0.75), _s("S7", "COVENANT_EDGE_PATTERN", 0.5, 0.6)])
    assert c["verdict"] == "LIKELY_FRAUD"


def test_a_checkable_fact_stands_alone():
    assert _verdict([_s("S4", "ALTERED_INVOICE", 0.9, 0.95)])["verdict"] == "LIKELY_FRAUD"


def test_shell_is_corroborated_through_a_shared_entity():
    c = _verdict([_s("S6", "SHELL_INDICATORS", 0.6, 0.8, ["E9"]),
                  _s("S3", "RELATED_PARTY_INFLOW", 0.8, 0.85, ["E9"])])
    shells = [f for f in c["findings"] if f["mechanism"] == "RELATED_SHELLS"][0]
    assert shells["confidence"] in ("medium", "high") and "payments" in shells["sources"]
