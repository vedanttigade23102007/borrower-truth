"""Corroboration counts only within one claim (audit 14 Oct 2026, gap 2; WHY.md change 30).

A claim is the set of clues in one mechanism that share a counterparty, leaving out the borrower's own company. Clues
about different lenders are different facts and must not corroborate each other. Clues that name no counterparty can't
be placed, so they still join every claim (a known limit).
"""
from bt.combiner.combine import ESCALATE_PRIORITY, build_cases
from bt.common.signal import Signal

OWN = "E_OWN"  # the borrower's own company


def _s(system, typ, sev, conf, related=(), sid="", text=None):
    return Signal(f"{system}-B1-{typ}{sid}", "B1", system, typ, sev, conf, ("ev:1",), text or typ, 10, tuple(related))


def _case(signals):
    return build_cases(signals, {}, {}, ["B1"], own_entities={"B1": OWN})[0]


def _finding(case, mechanism):
    return next(f for f in case["findings"] if f["mechanism"] == mechanism)


def test_a_lien_from_a_different_lender_does_not_corroborate_an_sec_filed_debt():
    # B0014: the SEC filing names lender A; an old, undisclosed lien was filed by lender B
    c = _case([_s("S5", "FILED_DEBT_UNDISCLOSED", 0.85, 0.9, ["E_LENDER_A"]),
               _s("S5", "COMPETING_LIEN", 0.5, 0.8, ["E_LENDER_B", OWN], text="all assets of the debtor")])
    f = _finding(c, "HIDDEN_DEBT")
    assert f["confidence"] == "medium"
    assert f["sources"] == ["sec_filings"]
    assert c["verdict"] == "LIKELY_FRAUD"  # the filing alone is a checkable fact
    assert c["priority"] < ESCALATE_PRIORITY


def test_the_same_lender_in_the_filing_and_a_lien_corroborates():
    c = _case([_s("S5", "FILED_DEBT_UNDISCLOSED", 0.85, 0.9, ["E_LENDER_A"]),
               _s("S5", "COMPETING_LIEN", 0.5, 0.8, ["E_LENDER_A", OWN], text="all assets of the debtor")])
    f = _finding(c, "HIDDEN_DEBT")
    assert f["confidence"] == "high"
    assert f["sources"] == ["sec_filings", "ucc"]
    assert c["priority"] >= ESCALATE_PRIORITY


def test_lien_judgment_and_shell_on_the_same_linked_company_corroborate():
    # B0041: a lien on a shell, a judgment against the same shell, and S6's clues about that shell
    c = _case([_s("S5", "COMPETING_LIEN", 0.5, 0.8, ["E_LENDER", "E_SHELL"], text="all assets of the debtor"),
               _s("S5", "JUDGMENT", 0.6, 0.7, ["E_SHELL"]),
               _s("S6", "SHELL_INDICATORS", 0.6, 0.8, ["E_SHELL"]),
               _s("S6", "RELATED_ENTITY", 0.5, 0.7, ["E_SHELL"])])
    assert _finding(c, "HIDDEN_DEBT")["confidence"] == "high"
    assert _finding(c, "RELATED_SHELLS")["confidence"] == "high"


def test_clues_that_share_one_counterparty_form_one_claim():
    c = _case([_s("S5", "COMPETING_LIEN", 0.5, 0.8, ["E_LENDER_A", "E_SHELL"], text="all assets of the debtor"),
               _s("S5", "JUDGMENT", 0.6, 0.7, ["E_SHELL"])])
    f = _finding(c, "HIDDEN_DEBT")
    assert f["confidence"] == "medium"
    assert f["sources"] == ["courts", "ucc"]


def test_the_borrowers_own_company_never_links_two_clues():
    # a lien by lender A on the borrower's loan collateral, and a judgment against the borrower itself (creditor
    # unknown): both name the borrower's own company, which says nothing about whether they're the same debt
    c = _case([_s("S5", "COMPETING_LIEN", 0.8, 0.8, ["E_LENDER_A", OWN], text="receivables and chattel paper"),
               _s("S5", "JUDGMENT", 0.6, 0.7, [OWN])])
    f = _finding(c, "DOUBLE_PLEDGE")
    assert f["confidence"] == "medium"
    assert f["corroborated_by"] == []
    # the judgment alone stays context (the lone-context rule, unchanged), not a finding it borrowed support for
    assert not [x for x in c["findings"] if x["mechanism"] == "HIDDEN_DEBT"]


def test_borrower_level_clues_still_pool():
    # tape clues name no counterparty: the servicer system and the bank's payments both say bad loans look current
    c = _case([_s("S2", "SOURCE_MISMATCH", 0.9, 0.9), _s("S2", "CURRENT_WITHOUT_PAYMENT", 0.6, 0.7)])
    f = _finding(c, "TAPE_DRESSUP")
    assert f["confidence"] == "high"
    assert f["sources"] == ["payments", "servicer_system"]
