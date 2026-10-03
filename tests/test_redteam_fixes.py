"""The checks added after the blind red team (2 Oct 2026). Each is a mechanism a credit officer knows; each test plants
the pattern into a small book, and a near miss that must not fire."""
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bt.datagen.generate import main as generate
from bt.pipeline.run import run as pipeline


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    out = tmp_path_factory.mktemp("fixes") / "book"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(out)])
    return out


@pytest.fixture()
def book(base, tmp_path):
    shutil.copytree(base, tmp_path / "b")
    return tmp_path / "b"


def rows(book, t):
    return pq.read_table(book / f"{t}.parquet").to_pylist()


def save(book, t, data):
    pq.write_table(pa.Table.from_pylist(data, schema=pq.read_schema(book / f"{t}.parquet")), book / f"{t}.parquet")


def clues(book, b, typ):
    sigs, _, _ = pipeline(str(book), 23)
    return [s for s in sigs if s.entity_id == b and s.type == typ]


def honest(book, btypes=None):
    import json
    lab = json.load(open(book / "labels.json"))
    bt = {r["borrower_id"]: r["btype"] for r in rows(book, "borrowers")}
    return [b for b, v in sorted(lab.items()) if not v["fraud"] and (btypes is None or bt[b] in btypes)]


def add_payee(book, b, amounts, start, eid="E_NEWCO", formed=4, ops=False):
    ents = rows(book, "entities")
    tmpl = dict(ents[0])
    save(book, "entities", ents + [dict(tmpl, entity_id=eid, name="Quiet Harbor Services LLC", kind="company",
                                        formed_month=formed, has_operations=ops)])
    out = rows(book, "outflows")
    acct = next(r["account_id"] for r in out if r["borrower_id"] == b)
    out += [dict(txn_id=f"OX{eid}{m}", month=m, day=10, borrower_id=b, account_id=acct, payee_id=eid,
                 payee_name="Quiet Harbor Services LLC", amount=float(a), memo="vendor payment")
            for m, a in zip(range(start, 24), amounts)]
    save(book, "outflows", out)


def test_rising_payments_to_an_undisclosed_company_read_as_debt_service(book):
    b = honest(book)[0]
    add_payee(book, b, [1000 * (1 + 0.1 * i) for i in range(16)], 8)
    assert clues(book, b, "UNDISCLOSED_DEBT_SERVICE")


def test_payments_that_rise_and_fall_are_not_debt_service(book):
    b = honest(book)[0]
    add_payee(book, b, [1000, 3000, 900, 2500, 800, 2600, 1000, 3100], 8)
    assert not clues(book, b, "UNDISCLOSED_DEBT_SERVICE")


def test_a_new_shell_taking_a_share_of_spend_is_cash_leakage(book):
    b = honest(book)[0]
    spend = sum(r["amount"] for r in rows(book, "outflows") if r["borrower_id"] == b) / 24
    add_payee(book, b, [0.3 * spend] * 12, 12)
    assert clues(book, b, "NEW_PAYEES_DRAIN_CASH")


def test_leaving_pledgecheck_mid_facility_is_noted(book):
    pc = rows(book, "pledgecheck")
    b = sorted({r["borrower_id"] for r in pc})[0]
    save(book, "pledgecheck", [r for r in pc if not (r["borrower_id"] == b and r["month"] >= 12)])
    assert clues(book, b, "PLEDGECHECK_LEFT")


def test_loan_payments_moving_to_month_end_are_noted(book):
    pay = rows(book, "payments")
    counts = {}
    for r in pay:
        if r["ref"] and r["ref"].startswith("A-"):
            counts[r["borrower_id"]] = counts.get(r["borrower_id"], 0) + 1
    b = max(counts, key=counts.get)
    save(book, "payments", [dict(r, day=26) if r["borrower_id"] == b and r["month"] >= 18 and (r["ref"] or "").startswith("A-")
                            else r for r in pay])
    assert clues(book, b, "MONTH_END_CURES")


@pytest.mark.parametrize("amount_shift, score_shift, fires", [(1.015, 3, True), (1.05, 3, False), (1.0, 25, False)])
def test_the_same_loans_in_a_public_pool_match_within_small_differences(book, amount_shift, score_shift, fires):
    tape = rows(book, "tape")
    b = next(r["borrower_id"] for r in tape if r["make"] and r["facility_id"].endswith("A"))
    mine = [r for r in tape if r["borrower_id"] == b and r["month"] >= 19 and r["make"]]
    loans = sorted({r["asset_id"] for r in mine})[:5]
    pool = rows(book, "public_abs")
    pool += [dict(pool_id=f"SYN-TEST-{b}", issuer_borrower_id=b, month=r["month"], pool_loan_id=f"P-{r['asset_id']}",
                  orig_month=r["orig_month"], orig_amount=round(r["orig_amount"] * amount_shift, 2), rate=r["rate"],
                  term=r["term"], make=r["make"], model=r["model"], model_year=r["model_year"],
                  obligor_state=r["obligor_state"], credit_score=r["credit_score"] + score_shift, dpd_bucket=0)
             for r in mine if r["asset_id"] in loans]
    save(book, "public_abs", pool)
    assert bool(clues(book, b, "PUBLIC_POOL_OVERLAP")) is fires


# after red team round 2 (2 Oct 2026)

@pytest.mark.parametrize("namesake,with_address,expected", [
    (False, False, "JUDGMENT"),  # one company has the name: the judgment is evidence
    (True, False, "JUDGMENT_NAME_SHARED"),  # two do, and the court record has no address: a lead, never evidence
    (True, True, "JUDGMENT"),  # two do, but the court record's address settles it
])
def test_a_judgment_under_a_shared_name_needs_the_court_file(book, namesake, with_address, expected):
    b = honest(book)[0]
    eid = next(r["entity_id"] for r in rows(book, "borrowers") if r["borrower_id"] == b)
    me = next(r for r in rows(book, "entities") if r["entity_id"] == eid)
    if namesake:
        save(book, "entities", rows(book, "entities") + [dict(me, entity_id="E_NAMESAKE", address="1 Elsewhere Rd, Suite 9",
                                                              officer_person_id=None, kind="company")])
    court = rows(book, "court_records") + [dict(case_id="CV-T1", defendant_name=me["name"],
                                                plaintiff="(synthetic) Test Lender LLC", kind="judgment",
                                                amount=5_000_000.0, month=20)]
    if with_address:
        court = [dict(r, defendant_address=me["address"] if r["case_id"] == "CV-T1" else None) for r in court]
        pq.write_table(pa.Table.from_pylist(court), book / "court_records.parquet")
    else:
        save(book, "court_records", court)
    sigs, _, _ = pipeline(str(book), 23)
    got = {s.type for s in sigs if s.entity_id == b and "court:CV-T1" in s.evidence}
    assert got == {expected}


@pytest.mark.parametrize("factor,every,fires", [(1.6, 3, True), (1.005, 1, False)])
def test_invoices_that_start_collecting_short_raise_dilution(book, factor, every, fires):
    b = honest(book, {"receivables_finance"})[0]
    inv = rows(book, "invoices")
    late = sorted({r["invoice_number"] for r in inv if r["borrower_id"] == b and r["issue_month"] >= 6})
    raised = set(late[::every])  # the customer still pays the real amount
    save(book, "invoices", [dict(r, amount=r["amount"] * factor) if r["borrower_id"] == b and r["invoice_number"] in raised
                            else r for r in inv])
    assert bool(clues(book, b, "DILUTION_JUMP")) is fires


@pytest.mark.parametrize("in_servicer", [False, True])
def test_the_largest_new_loans_are_pulled_from_the_servicer(book, in_servicer):
    tape = rows(book, "tape")
    b = next(x for x in honest(book, {"auto_finance"}) if any(r["borrower_id"] == x and r["month"] == 15 for r in tape))
    mine = [r for r in tape if r["borrower_id"] == b and r["month"] == 15]
    big = 10 * max(r["balance"] for r in mine)
    new = [dict(mine[0], asset_id=f"A-{b}-NEW{i}", vin=f"SYNNEW{b}{i}", obligor_id=f"O-{b}-NEW{i}", month=m,
                balance=big * (1 - 0.02 * (m - 16)), dpd_bucket_reported=0, deferred_flag=0, eligible_reported=True)
           for i in range(3) for m in range(16, 24)]
    save(book, "tape", tape + new)
    pay = rows(book, "payments")
    p0 = next(r for r in pay if r["borrower_id"] == b and r["ref"].startswith("A-"))
    save(book, "payments", pay + [dict(p0, txn_id=f"TNEW{r['asset_id'][-1]}{r['month']}", month=r["month"],
                                       ref=r["asset_id"], amount=round(r["balance"] * 0.03, 2)) for r in new])
    if in_servicer:
        save(book, "source_truth", rows(book, "source_truth") + [
            dict(month=r["month"], borrower_id=b, asset_id=r["asset_id"], dpd_bucket_true=0, balance_true=r["balance"])
            for r in new])
    pulled = [s for s in clues(book, b, "TARGETED_SOURCE_MISMATCH") if any("largest_new" in e for e in s.evidence)]
    assert bool(pulled) is not in_servicer


def _pull(book, month):
    import duckdb
    from bt.systems.s2_tape_source import SAMPLE, SAMPLE_SIZE, draw_key
    con = duckdb.connect()
    for t in ("tape", "source_truth", "facilities"):  # the pull looks at loans on borrowing-base (warehouse) lines
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{book / (t + '.parquet')}'")
    return {(r[0], r[1]) for r in con.execute(SAMPLE.replace("@KEY@", draw_key(con)), [month, SAMPLE_SIZE]).fetchall()}


def _roll(book, b, loans, m, tape_next=None, true_next=None):
    """The servicer rolls these loans from 30-59 to 60-89 days late at month m; the tape stays at 30-59."""
    want = {(a, mm): v for a in loans for mm, v in ((m - 1, 1), (m, 1))}
    tape = [dict(r, dpd_bucket_reported=want[(r["asset_id"], r["month"])], eligible_reported=True)
            if (r["asset_id"], r["month"]) in want else r for r in rows(book, "tape")]
    truth = {(a, m - 1): 1 for a in loans} | {(a, m): 2 for a in loans}
    if tape_next is not None:  # what the tape says the month after
        tape = [dict(r, dpd_bucket_reported=tape_next, eligible_reported=tape_next <= 1)
                if r["asset_id"] in loans and r["month"] == m + 1 else r for r in tape]
        truth |= {(a, m + 1): true_next for a in loans}
    save(book, "tape", tape)
    save(book, "source_truth", [dict(r, dpd_bucket_true=truth[(r["asset_id"], r["month"])])
                                if (r["asset_id"], r["month"]) in truth else r for r in rows(book, "source_truth")])


def _big_honest_auto(book):
    tape = rows(book, "tape")
    n = {b: sum(1 for r in tape if r["borrower_id"] == b and r["month"] == 23 and r["eligible_reported"])
         for b in honest(book, {"auto_finance"})}
    return max(n, key=n.get)


@pytest.mark.parametrize("k,flagged", [(2, False), (3, True)])
def test_loans_that_just_rolled_are_a_timing_difference_unless_many_at_once(book, k, flagged):
    b = _big_honest_auto(book)
    loans = sorted(a for bb, a in _pull(book, 23) if bb == b)[:k]
    _roll(book, b, loans, 23)
    assert bool(clues(book, b, "SOURCE_MISMATCH")) is flagged
    assert bool(clues(book, b, "TIMING_UNCONFIRMED")) is not flagged


@pytest.mark.parametrize("caught_up", [True, False])
def test_a_timing_difference_must_catch_up_the_next_month(book, caught_up):
    b = _big_honest_auto(book)
    later = {a for bb, a in _pull(book, 23) if bb == b}
    loans = sorted(a for bb, a in _pull(book, 22) if bb == b and a not in later)[:2]
    assert len(loans) == 2  # pulled last month, not this month: only the follow-up can see them
    _roll(book, b, loans, 22, tape_next=2 if caught_up else 1, true_next=3)
    got = clues(book, b, "SOURCE_MISMATCH")
    assert bool(got) is not caught_up
    assert caught_up or "still hasn't caught up" in got[0].explanation


# after red team round 3 (Vedant, 3 Oct 2026): checked against the bank's own cash records, and kept in view while the
# collateral is still pledged

def _paid_loans(book, b, month):
    pay = {(r["ref"], r["month"]) for r in rows(book, "payments") if r["borrower_id"] == b}
    tape = rows(book, "tape")
    later = {r["asset_id"] for r in tape if r["borrower_id"] == b and r["month"] == 23}
    return sorted(r["asset_id"] for r in tape if r["borrower_id"] == b and r["month"] == month and
                  r["dpd_bucket_reported"] == 0 and r["asset_id"] in later and (r["asset_id"], month) in pay)


@pytest.mark.parametrize("share,deferred,fires", [(0.09, False, True), (0.09, True, False), (0.05, False, False)])
def test_paying_loans_whose_balances_rise_are_caught(book, share, deferred, fires):
    import math
    from bt.systems.s2_tape_source import ROSE_SHARE
    b = _big_honest_auto(book)
    on_tape = len({r["asset_id"] for r in rows(book, "tape") if r["borrower_id"] == b and r["month"] == 23})
    k = math.ceil(share * on_tape)
    loans = set(_paid_loans(book, b, 8)[:k])
    assert len(loans) == k and (k / on_tape >= ROSE_SHARE) is (share > ROSE_SHARE)
    save(book, "tape", [dict(r, balance=r["balance"] * 1.10, deferred_flag=int(deferred and r["month"] == 8))
                        if r["asset_id"] in loans and r["month"] >= 8 else r for r in rows(book, "tape")])
    # month 8, seen at month 24: still pledged. Under the line calibrated on real pools (5%), it stays quiet
    assert bool(clues(book, b, "BALANCE_ROSE_WHILE_PAID")) is fires


@pytest.mark.parametrize("same_contract,fires", [(True, True), (False, False)])
def test_the_same_vehicle_or_contract_twice_in_one_facility(book, same_contract, fires):
    b = _big_honest_auto(book)
    tape = rows(book, "tape")
    src = sorted({r["asset_id"] for r in tape if r["borrower_id"] == b and r["month"] == 23})[:2]
    extra = []
    for r in tape:
        if r["asset_id"] in src and r["month"] >= 20:
            x = dict(r, asset_id=r["asset_id"] + "-P", balance=r["balance"] * 0.3)
            if not same_contract:  # the same customer's second, different loan: another car, other terms
                x.update(vin=r["vin"] + "Z", orig_amount=r["orig_amount"] + 1000.0)
            extra.append(x)
    save(book, "tape", tape + extra)
    got = [s for s in clues(book, b, "DUPLICATE_ASSET") if "same_facility" in s.evidence]
    assert bool(got) is fires


@pytest.mark.parametrize("old_loan", ["closed", "written_down"])
def test_a_repossessed_car_resold_under_a_new_loan_is_one_pledge(book, old_loan):
    b = _big_honest_auto(book)
    tape = rows(book, "tape")
    src = sorted({r["asset_id"] for r in tape if r["borrower_id"] == b and r["month"] == 23})[:2]
    new = []
    for r in tape:
        if r["asset_id"] in src and r["month"] >= 20:  # the same car, resold to a new customer under a new loan
            new.append(dict(r, asset_id=r["asset_id"] + "-R", obligor_id=r["obligor_id"] + "-NEW",
                            orig_month=20, orig_amount=r["orig_amount"] * 0.6, balance=r["orig_amount"] * 0.6))
    if old_loan == "closed":  # the old loan leaves the tape when the car is repossessed
        tape = [r for r in tape if not (r["asset_id"] in src and r["month"] >= 20)]
    else:  # or stays, written down to nothing and ineligible
        tape = [dict(r, balance=0.0, eligible_reported=False, dpd_bucket_reported=3)
                if r["asset_id"] in src and r["month"] >= 20 else r for r in tape]
    save(book, "tape", tape + new)
    assert not [s for s in clues(book, b, "DUPLICATE_ASSET") if "same_facility" in s.evidence]


def _new_debtor_invoices(book, b, n, month=6, amount=None, debtor=None):
    inv = rows(book, "invoices")
    mine = [r for r in inv if r["borrower_id"] == b]
    t = mine[0]
    return [dict(t, invoice_id=f"INVT{k}", invoice_number=f"T-{b}-{k}", po_number=f"PO-T{k}",
                 debtor_id=debtor or "E_NEVERPAYS", debtor_name="Quiet Orders LLC" if debtor is None else t["debtor_name"],
                 pledged_month=month, issue_month=month, issue_day=5, due_days=30,
                 amount=amount or t["amount"]) for k in range(n)]


@pytest.mark.parametrize("pays_one,fires", [(False, True), (True, False)])
def test_a_customer_that_has_never_paid_anything(book, pays_one, fires):
    b = honest(book, {"receivables_finance"})[0]
    new = _new_debtor_invoices(book, b, 4)
    save(book, "invoices", rows(book, "invoices") + new)
    if pays_one:
        pay = rows(book, "payments")
        p0 = next(r for r in pay if r["borrower_id"] == b)
        save(book, "payments", pay + [dict(p0, txn_id="TPAID1", month=8, payer_id="E_NEVERPAYS",
                                            payer_name="Quiet Orders LLC", amount=new[0]["amount"], ref=new[0]["invoice_number"])])
    assert bool(clues(book, b, "CUSTOMER_NEVER_PAID")) is fires


@pytest.mark.parametrize("paid_in_full,fires", [(False, True), (True, False)])
def test_an_unpaid_oversized_invoice_stays_in_view(book, paid_in_full, fires):
    import statistics
    b = honest(book, {"receivables_finance"})[0]
    inv, pay = rows(book, "invoices"), rows(book, "payments")
    paid_refs = {r["ref"] for r in pay}
    by_debtor = {}
    for r in inv:
        if r["borrower_id"] == b and r["invoice_number"] in paid_refs:
            by_debtor.setdefault(r["debtor_id"], []).append(r["amount"])
    debtor = max(by_debtor, key=lambda d: len(by_debtor[d]))
    big = 10 * statistics.median(by_debtor[debtor])
    new = _new_debtor_invoices(book, b, 2, month=6, amount=big, debtor=debtor)  # pledged month 7: past any 9-month window
    save(book, "invoices", inv + new)
    if paid_in_full:
        p0 = next(r for r in pay if r["borrower_id"] == b)
        save(book, "payments", pay + [dict(p0, txn_id=f"TFULL{k}", month=8, payer_id=debtor, amount=big,
                                            ref=x["invoice_number"]) for k, x in enumerate(new)])
    assert bool(clues(book, b, "IMPLAUSIBLE_AMOUNT")) is fires


@pytest.mark.parametrize("factor,fires", [(1.30, True), (1.02, False)])
def test_one_months_short_paid_invoices_stay_in_view(book, factor, fires):
    inv = rows(book, "invoices")
    cand = honest(book, {"receivables_finance"})
    b = max(cand, key=lambda x: sum(1 for r in inv if r["borrower_id"] == x and r["issue_month"] == 6))
    assert sum(1 for r in inv if r["borrower_id"] == b and r["issue_month"] == 6) >= 20
    save(book, "invoices", [dict(r, amount=r["amount"] * factor) if r["borrower_id"] == b and r["issue_month"] == 6
                            else r for r in inv])  # the customers still pay the real amounts
    assert bool(clues(book, b, "DILUTION_JUMP")) is fires
