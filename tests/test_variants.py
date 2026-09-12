"""The two harder variants (nominee shell, round trip) and their honest look-alikes."""
import json

import pytest

from bt.datagen.generate import main as generate
from bt.eval.evaluate import mech_hits
from bt.pipeline.run import run as pipeline


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("variants") / "book"
    generate(["--borrowers", "80", "--scale", "0.4", "--seed", "23", "--out", str(out)])
    labels = json.load(open(out / "labels.json"))
    _, cases, _ = pipeline(str(out), 23)
    return labels, {c["borrower_id"]: c for c in cases}


def types(c):
    return {s["type"] for s in c["signals"]}


def test_nominee_shell_is_linked_by_phone_or_agent_and_caught(book):
    labels, cases = book
    nominees = [b for b, v in labels.items() if v["pattern"] == "nominee_shell"]
    assert nominees
    for b in nominees:
        assert "RELATED_PARTY_INFLOW" in types(cases[b]), b  # S6 linked the nominee shell, so S3 knew who paid
        assert "DISGUISED_RECEIPTS" in mech_hits(cases[b])


def test_round_trip_is_caught_by_the_money_coming_back(book):
    labels, cases = book
    trips = [b for b, v in labels.items() if v["pattern"] == "round_trip"]
    assert trips
    for b in trips:
        assert "CIRCULAR_FLOW" in types(cases[b]), b
        assert cases[b]["verdict"] == "LIKELY_FRAUD"


def test_rewritten_credit_scores_are_caught_and_honest_corrections_are_not(book):
    labels, cases = book
    rewriters = [b for b, v in labels.items() if v["planted"].get("rewritten_scores", 0) >= 5]
    assert rewriters
    assert all("ATTRIBUTE_REWRITE" in types(cases[b]) for b in rewriters)
    honest = [b for b, v in labels.items() if not v["fraud"]]
    assert not [b for b in honest if "ATTRIBUTE_REWRITE" in types(cases[b])]


def test_honest_lookalikes_are_not_flagged(book):
    labels, cases = book
    honest = [b for b, v in labels.items() if not v["fraud"]]
    assert not [b for b in honest if "CIRCULAR_FLOW" in types(cases[b])]  # two-way trade isn't a round trip
    lookalikes = [b for b in honest if {"VIRTUAL_OFFICE", "OWNER_IS_AGENT_ELSEWHERE", "TWO_WAY_TRADE"} & set(labels[b]["benign"])]
    assert lookalikes
    assert not [b for b in lookalikes if cases[b]["verdict"] == "LIKELY_FRAUD"]
