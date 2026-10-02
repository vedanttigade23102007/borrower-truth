"""Combiner: signals -> per-borrower case with a finding, verdict and priority.

Verdicts come from auditable rules, never from a model (design §5). The priority
score is kept, but only to order the queue.

Confidence counts *independent data sources*, not systems. Two clues that come
from different places (say, bank payments and a lien register) corroborate each
other; two clues derived from the same place do not. Signals that other
signals were derived from (DEBT_GAP, RECEIVABLES_QUALITY) never count as
independent corroboration.
"""
from __future__ import annotations

from collections import defaultdict

MECHANISM_OF = {
    "DUPLICATE_ASSET": "DOUBLE_PLEDGE", "PLEDGECHECK_UNIQUENESS_FAIL": "DOUBLE_PLEDGE",
    "PLEDGECHECK_ABSENT": "DOUBLE_PLEDGE",
    "PLEDGECHECK_COMPLETENESS_FAIL": "TAPE_DRESSUP", "PLEDGECHECK_COMPLETENESS_FAIL_RECEIVABLES": "FAKE_INVOICES",
    "CURRENT_WITHOUT_PAYMENT": "TAPE_DRESSUP", "DEFERMENT_WITHOUT_PROGRAM": "TAPE_DRESSUP",
    "IMPOSSIBLE_TRANSITION": "TAPE_DRESSUP", "SOURCE_MISMATCH": "TAPE_DRESSUP",
    "TARGETED_SOURCE_MISMATCH": "TAPE_DRESSUP", "ATTRIBUTE_REWRITE": "TAPE_DRESSUP",
    "ELIGIBILITY_EDGE_CLUSTER": "TAPE_DRESSUP",
    "RELATED_PARTY_INFLOW": "DISGUISED_RECEIPTS", "LENDER_FUNDS_AS_RECEIPTS": "DISGUISED_RECEIPTS",
    "NON_OBLIGOR_PAYER": "DISGUISED_RECEIPTS", "CIRCULAR_FLOW": "DISGUISED_RECEIPTS",
    "ALTERED_INVOICE": "FAKE_INVOICES", "UNPAID_BY_DEBTOR": "FAKE_INVOICES", "IMPLAUSIBLE_AMOUNT": "FAKE_INVOICES",
    "RECEIVABLES_QUALITY": "FAKE_INVOICES", "DOC_DATA_MISMATCH": "FAKE_INVOICES",
    "UNDISCLOSED_SECURED_PARTY": "HIDDEN_DEBT", "COMPETING_LIEN": "HIDDEN_DEBT", "DEBT_GAP": "HIDDEN_DEBT",
    "JUDGMENT": "HIDDEN_DEBT",
    "SHELL_INDICATORS": "RELATED_SHELLS", "RELATED_ENTITY": "RELATED_SHELLS",
    "CASH_REVENUE_GAP": "FIN_MANIPULATION", "COVENANT_EDGE_PATTERN": "FIN_MANIPULATION",
    "RECEIVABLES_OUTPACE_REVENUE": "FAKE_INVOICES",
    # public SEC data (bt/sec)
    "ROLL_RATE_TOO_LOW": "TAPE_DRESSUP", "PUBLIC_POOL_OVERLAP": "DOUBLE_PLEDGE", "POOL_LOANS_PAID_ELSEWHERE": "DOUBLE_PLEDGE",
    "FILED_DEBT_UNDISCLOSED": "HIDDEN_DEBT", "FILED_VS_REPORTED": "FIN_MANIPULATION",
    "DEBT_ACCELERATION_FILED": "HIDDEN_DEBT",
    # who the borrower pays, and when its customers pay (2 Oct 2026, after the blind red team)
    "UNDISCLOSED_DEBT_SERVICE": "HIDDEN_DEBT", "NEW_PAYEES_DRAIN_CASH": "CASH_LEAKAGE",
    "MONTH_END_CURES": "TAPE_DRESSUP", "PLEDGECHECK_LEFT": "DOUBLE_PLEDGE",
    # after red team round 2: dilution against the borrower's own early months; a judgment under a shared name
    "DILUTION_JUMP": "FAKE_INVOICES", "JUDGMENT_NAME_SHARED": "HIDDEN_DEBT", "TIMING_UNCONFIRMED": "TAPE_DRESSUP",
}
SEC_TYPES = {"ROLL_RATE_TOO_LOW", "PUBLIC_POOL_OVERLAP", "POOL_LOANS_PAID_ELSEWHERE", "FILED_DEBT_UNDISCLOSED", "FILED_VS_REPORTED",
             "DEBT_ACCELERATION_FILED"}  # checks that exist because of public SEC data (switch-off test: "SEC")

# where each signal's evidence actually comes from
SOURCE = {
    "DUPLICATE_ASSET": "wf_facilities", "PLEDGECHECK_UNIQUENESS_FAIL": "pledgecheck", "PLEDGECHECK_ABSENT": "pledgecheck",
    "PLEDGECHECK_COMPLETENESS_FAIL": "pledgecheck", "PLEDGECHECK_COMPLETENESS_FAIL_RECEIVABLES": "pledgecheck",
    "CURRENT_WITHOUT_PAYMENT": "payments", "DEFERMENT_WITHOUT_PROGRAM": "tape_flags",
    "IMPOSSIBLE_TRANSITION": "tape_history", "SOURCE_MISMATCH": "servicer_system",
    "TARGETED_SOURCE_MISMATCH": "servicer_system", "ATTRIBUTE_REWRITE": "tape_history",
    "ELIGIBILITY_EDGE_CLUSTER": "tape_flags",
    "RELATED_PARTY_INFLOW": "payments", "LENDER_FUNDS_AS_RECEIPTS": "payments", "NON_OBLIGOR_PAYER": "payments",
    "CIRCULAR_FLOW": "operating_account",
    "ALTERED_INVOICE": "invoices", "UNPAID_BY_DEBTOR": "payments", "IMPLAUSIBLE_AMOUNT": "invoices",
    "DOC_DATA_MISMATCH": "documents",
    "UNDISCLOSED_SECURED_PARTY": "ucc", "COMPETING_LIEN": "ucc", "JUDGMENT": "courts",
    "SHELL_INDICATORS": "registry", "RELATED_ENTITY": "registry",
    "CASH_REVENUE_GAP": "financials_vs_cash", "COVENANT_EDGE_PATTERN": "covenant_certificate",
    "RECEIVABLES_OUTPACE_REVENUE": "financial_statements",
    "DEBT_GAP": "derived", "RECEIVABLES_QUALITY": "derived",
    # the peer yardstick is public, but the evidence is the tape's own history: not an independent source
    "ROLL_RATE_TOO_LOW": "tape_history",
    "PUBLIC_POOL_OVERLAP": "public_abs", "POOL_LOANS_PAID_ELSEWHERE": "payments",
    "FILED_DEBT_UNDISCLOSED": "sec_filings", "FILED_VS_REPORTED": "sec_filings",
    "DEBT_ACCELERATION_FILED": "sec_filings",
    "UNDISCLOSED_DEBT_SERVICE": "operating_account", "NEW_PAYEES_DRAIN_CASH": "operating_account",
    "MONTH_END_CURES": "payments", "PLEDGECHECK_LEFT": "pledgecheck",
    "DILUTION_JUMP": "payments", "JUDGMENT_NAME_SHARED": "courts", "TIMING_UNCONFIRMED": "servicer_system",
}

# checkable facts (not statistical inferences): strong enough to stand alone
FACT = {"DUPLICATE_ASSET", "PLEDGECHECK_UNIQUENESS_FAIL", "ALTERED_INVOICE", "SOURCE_MISMATCH", "TARGETED_SOURCE_MISMATCH",
        "LENDER_FUNDS_AS_RECEIPTS", "RELATED_PARTY_INFLOW", "COMPETING_LIEN", "CIRCULAR_FLOW", "ATTRIBUTE_REWRITE",
        # what the borrower told the SEC contradicts what it told the bank: checkable in the filing itself
        "FILED_DEBT_UNDISCLOSED", "FILED_VS_REPORTED",
        # named loans, matched to the public trust, whose payments no longer reach Wells Fargo: checkable per loan
        "POOL_LOANS_PAID_ELSEWHERE"}

# an undisclosed lien on the loan collateral itself means that collateral is pledged twice
DOUBLE_PLEDGE_HINT = ("receivables and chattel paper",)
# a borrower that leaves the shared collateral registry and, around the same time, starts paying a new company in
# amounts shaped like interest: a second lender is likely financing the same collateral
LEFT_REGISTRY_MONTHS = 3

PLAIN = {
    "DOUBLE_PLEDGE": "the same collateral is pledged to more than one lender",
    "TAPE_DRESSUP": "bad loans are being reported as good ones",
    "DISGUISED_RECEIPTS": "money from lenders or linked companies is arriving dressed up as customer payments",
    "FAKE_INVOICES": "invoices are fake, inflated or altered",
    "HIDDEN_DEBT": "the borrower has debt it has not disclosed",
    "RELATED_SHELLS": "the borrower is connected to undisclosed shell companies",
    "FIN_MANIPULATION": "the reported financial statements don't fit the evidence",
    "CASH_LEAKAGE": "cash is leaving the borrower for new payees that take a large share of its spending",
}

WEIGHT = {"S1": 1.0, "S2": 1.0, "S3": 1.0, "S4": 1.0, "S5": 0.9, "S6": 0.5, "S7": 0.8}
CONTEXT = {"PLEDGECHECK_ABSENT",  # coverage notes shown to the officer; never scored
           "DEBT_ACCELERATION_FILED",  # a lender sped up repayment (8-K Item 2.04): a credit event, not fraud
           "JUDGMENT_NAME_SHARED",  # a judgment that may belong to a namesake: a lead to check, not evidence
           "TIMING_UNCONFIRMED"}  # a cut-off timing difference that can only be confirmed next month
LONE_CONTEXT = ("RELATED_ENTITY", "JUDGMENT")  # alone at low confidence: context, not a finding
MIN_X = 0.25  # severity x confidence needed for a clue to count as corroboration
ESCALATE_PRIORITY = 0.95


def _x(s):
    return s.severity * s.confidence


def assign_mechanisms(sigs) -> dict[str, str]:
    by_id = {s.signal_id: s for s in sigs}
    left = [s.observed_month for s in sigs if s.type == "PLEDGECHECK_LEFT"]
    mech = {}
    for s in sigs:
        if s.type == "COMPETING_LIEN" and any(h in s.explanation for h in DOUBLE_PLEDGE_HINT):
            mech[s.signal_id] = "DOUBLE_PLEDGE"
        elif s.type == "UNDISCLOSED_DEBT_SERVICE" and any(abs(s.observed_month - m) <= LEFT_REGISTRY_MONTHS for m in left):
            mech[s.signal_id] = "DOUBLE_PLEDGE"
        elif SOURCE[s.type] != "derived":
            mech[s.signal_id] = MECHANISM_OF[s.type]
    for s in sigs:  # derived signals inherit the mechanism of what they were derived from
        if SOURCE[s.type] == "derived":
            parents = [mech[e[7:]] for e in s.evidence if e.startswith("signal:") and e[7:] in mech]
            mech[s.signal_id] = max(set(parents), key=parents.count) if parents else MECHANISM_OF[s.type]
    return mech


def build_cases(signals, coverage: dict, explanations: dict, borrowers: list[str]) -> list[dict]:
    by_b = defaultdict(list)
    for s in signals:
        by_b[s.entity_id].append(s)
    cases = []
    for b in borrowers:
        all_sigs = sorted(by_b.get(b, []), key=lambda s: -_x(s))
        notes = [s for s in all_sigs if s.type in CONTEXT]
        sigs = [s for s in all_sigs if s.type not in CONTEXT]
        per_sys = defaultdict(float)
        for s in sigs:
            per_sys[s.system] = max(per_sys[s.system], _x(s))
        p_clean = 1.0
        for sysname, x in per_sys.items():
            p_clean *= 1 - WEIGHT[sysname] * x
        strong_systems = [k for k, x in per_sys.items() if x >= 0.3]
        priority = min(1.0, (1 - p_clean) + 0.08 * max(0, len(strong_systems) - 1))

        mech_of = assign_mechanisms(sigs)
        groups = defaultdict(list)
        for s in sigs:
            groups[mech_of[s.signal_id]].append(s)

        findings = []
        for m, ss in groups.items():
            sources = {SOURCE[s.type] for s in ss if _x(s) >= MIN_X and SOURCE[s.type] != "derived"}
            # chaining: a clue elsewhere that points at the same linked company corroborates this finding
            linked = {e for s in ss for e in s.related_entities}
            corroborating = [o for o in sigs if mech_of[o.signal_id] != m and linked & set(o.related_entities)
                             and _x(o) >= MIN_X and SOURCE[o.type] != "derived"]
            sources |= {SOURCE[o.type] for o in corroborating}
            has_fact = any(s.type in FACT and _x(s) >= 0.5 for s in ss)
            best = max(_x(s) for s in ss)
            if (has_fact and len(sources) >= 2) or len(sources) >= 3:
                conf = "high"
            elif has_fact or len(sources) >= 2:
                conf = "medium"
            elif best >= 0.3:
                conf = "low"
            else:
                continue
            if conf == "low" and all(s.type in LONE_CONTEXT for s in ss):
                continue  # a lone affiliate or small judgment is context, not a finding
            findings.append(dict(mechanism=m, confidence=conf, plain=PLAIN[m],
                                 signals=[s.signal_id for s in ss],
                                 corroborated_by=[o.signal_id for o in corroborating],
                                 sources=sorted(sources), systems=sorted({s.system for s in ss}),
                                 first_month=min(s.observed_month for s in ss)))
        order = {"high": 0, "medium": 1, "low": 2}
        findings.sort(key=lambda f: (order[f["confidence"]], f["mechanism"]))
        # hard escalation: a checkable fact confirmed by an independent source jumps the queue
        if any(f["confidence"] == "high" and any(s.type in FACT and _x(s) >= 0.5 for s in groups[f["mechanism"]])
               for f in findings):
            priority = max(priority, ESCALATE_PRIORITY)
        actionable = [f for f in findings if f["confidence"] in ("high", "medium")]
        if actionable:
            verdict = "LIKELY_FRAUD"
        elif findings:
            verdict = "NEEDS_MORE_EVIDENCE"
        elif explanations.get(b):
            verdict = "EXPLAINED"
        else:
            verdict = "NO_ISSUE"
        headline = (f"Likely: {actionable[0]['plain']}" if actionable else
                    f"Worth a look: {findings[0]['plain']}" if findings else
                    "Checks fired, but disclosures explain them" if verdict == "EXPLAINED" else "No issues found")
        cases.append(dict(borrower_id=b, verdict=verdict, headline=headline, priority=round(priority, 3),
                          findings=findings, signals=[s.row() for s in sigs + notes],
                          explanations=explanations.get(b, []), coverage=coverage))
    cases.sort(key=lambda c: -c["priority"])
    return cases
