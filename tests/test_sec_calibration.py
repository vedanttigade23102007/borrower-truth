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


def test_balance_rise_line_sits_above_every_real_pool(cal):
    # honest servicers do show current, paid, unmodified loans rising now and then; counted over a loan's 24 months on
    # a tape, every real pool must stay below S2's line, with room to spare
    br = cal["balance_rises"]
    assert br["n_pools"] >= 20 and br["book_months"] == 24
    for p in br["pools"]:
        assert p["projected_share"] < s2.ROSE_SHARE, p["trust"]
    assert s2.ROSE_SHARE >= 1.4 * br["max_projected_share"]


def test_a_rising_balance_or_a_never_paying_customer_needs_another_source(cal):
    from bt.combiner import combine
    # real honest pools rise sometimes; a customer paying the borrower directly looks like one that never paid
    assert "BALANCE_ROSE_WHILE_PAID" not in combine.FACT and "CUSTOMER_NEVER_PAID" not in combine.FACT


def test_the_same_contract_key_needs_the_lenders_customer_id(cal):
    from bt.systems import s1_collateral as s1
    # without a customer ID, 1% of real public loans share an origination month and amount with another loan in the
    # same pool; the key must carry the lender's customer ID, and both loans must be counted in the borrowing base
    assert cal["contract_collisions"]["month+amount"]["share"] > 0.005
    assert "obligor_id" in s1.TAPE_DUP_CONTRACT and "eligible_reported" in s1.TAPE_DUP_CONTRACT


def test_real_servicers_never_rewrite_credit_scores(cal):
    assert cal["score_changes"]["loans"] > 500_000 and cal["score_changes"]["changed"] == 0
