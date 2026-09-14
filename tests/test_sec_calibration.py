"""Guard rails: every threshold tuned on real SEC data must stay outside the range real honest lenders show.

If someone moves a threshold into the band that real public auto pools occupy, these fail.
Skipped when the calibration file hasn't been built (it needs the ABS-EE pull).
"""
import json
import os

import pytest

from bt.systems import s2_tape_source as s2

CAL = os.path.join(os.path.dirname(__file__), "..", "data", "calibration", "absee_auto.json")
pytestmark = pytest.mark.skipif(not os.path.exists(CAL), reason="no SEC calibration built")


@pytest.fixture(scope="module")
def cal():
    return json.load(open(CAL))


def test_calibration_is_real_and_big_enough(cal):
    assert cal["files"] >= 50 and cal["pairs"] > 500_000
    assert len({p[0] for p in cal["pools"]}) >= 20  # lenders


def test_current_without_payment_line_sits_above_every_real_pool(cal):
    # S2 flags > 3% of current loans unpaid; the worst real pool shows two unpaid months in a row for this share
    assert cal["real_extremes"]["max_current_no_pay_2m_share"] < 0.03


def test_impossible_transition_needs_a_share_above_real_pools(cal):
    assert s2.JUMP_SHARE > cal["real_extremes"]["max_late60_current_no_pay_share"]


def test_roll_rate_line_sits_below_every_real_pool(cal):
    lowest = cal["real_extremes"]["min_roll_forward_rate"]
    assert abs(s2.ROLL_MIN_REAL - lowest) < 0.005
    assert s2.ROLL_MIN_REAL * s2.ROLL_FACTOR < lowest


def test_no_real_pool_trips_the_roll_rate_check(cal):
    for p in cal["pool_behaviour"]:
        if p["late30"] >= s2.ROLL_MIN_N:
            assert p["roll_forward_rate"] >= s2.ROLL_MIN_REAL * s2.ROLL_FACTOR, p["trust"]


def test_score_edge_line_sits_above_every_real_pool(cal):
    assert abs(s2.EDGE_RATIO_REAL - cal["real_extremes"]["max_edge_ratio_600"]) < 0.01
    for e in cal["edge_600"]:
        if e["a1"] + e["a2"] >= s2.EDGE_MIN:
            assert e["ratio"] < s2.EDGE_RATIO_REAL * s2.EDGE_FACTOR, e["trust"]


def test_real_servicers_never_rewrite_credit_scores(cal):
    assert cal["score_changes"]["loans"] > 500_000 and cal["score_changes"]["changed"] == 0
