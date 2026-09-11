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
    "PLEDGECHECK_COMPLETENESS_FAIL": "TAPE_DRESSUP", "PLEDGECHECK_COMPLETENESS_FAIL_RECEIVABLES": "FAKE_INVOICES",
    "CURRENT_WITHOUT_PAYMENT": "TAPE_DRESSUP", "DEFERMENT_WITHOUT_PROGRAM": "TAPE_DRESSUP",
    "IMPOSSIBLE_TRANSITION": "TAPE_DRESSUP", "SOURCE_MISMATCH": "TAPE_DRESSUP",
    "RELATED_PARTY_INFLOW": "DISGUISED_RECEIPTS", "LENDER_FUNDS_AS_RECEIPTS": "DISGUISED_RECEIPTS",
    "NON_OBLIGOR_PAYER": "DISGUISED_RECEIPTS",
    "ALTERED_INVOICE": "FAKE_INVOICES", "UNPAID_BY_DEBTOR": "FAKE_INVOICES", "IMPLAUSIBLE_AMOUNT": "FAKE_INVOICES",
    "RECEIVABLES_QUALITY": "FAKE_INVOICES",
    "UNDISCLOSED_SECURED_PARTY": "HIDDEN_DEBT", "COMPETING_LIEN": "HIDDEN_DEBT", "DEBT_GAP": "HIDDEN_DEBT",
    "JUDGMENT": "HIDDEN_DEBT",
    "SHELL_INDICATORS": "RELATED_SHELLS", "RELATED_ENTITY": "RELATED_SHELLS",
    "CASH_REVENUE_GAP": "FIN_MANIPULATION", "COVENANT_EDGE_PATTERN": "FIN_MANIPULATION",
}

# where each signal's evidence actually comes from
SOURCE = {
    "DUPLICATE_ASSET": "wf_facilities", "PLEDGECHECK_UNIQUENESS_FAIL": "pledgecheck",
    "PLEDGECHECK_COMPLETENESS_FAIL": "pledgecheck", "PLEDGECHECK_COMPLETENESS_FAIL_RECEIVABLES": "pledgecheck",
    "CURRENT_WITHOUT_PAYMENT": "payments", "DEFERMENT_WITHOUT_PROGRAM": "tape_flags",
    "IMPOSSIBLE_TRANSITION": "tape_history", "SOURCE_MISMATCH": "servicer_system",
    "RELATED_PARTY_INFLOW": "payments", "LENDER_FUNDS_AS_RECEIPTS": "payments", "NON_OBLIGOR_PAYER": "payments",
    "ALTERED_INVOICE": "invoices", "UNPAID_BY_DEBTOR": "payments", "IMPLAUSIBLE_AMOUNT": "invoices",
    "UNDISCLOSED_SECURED_PARTY": "ucc", "COMPETING_LIEN": "ucc", "JUDGMENT": "courts",
    "SHELL_INDICATORS": "registry", "RELATED_ENTITY": "registry",
    "CASH_REVENUE_GAP": "financials_vs_cash", "COVENANT_EDGE_PATTERN": "covenant_certificate",
    "DEBT_GAP": "derived", "RECEIVABLES_QUALITY": "derived",
}

# checkable facts (not statistical inferences): strong enough to stand alone
FACT = {"DUPLICATE_ASSET", "PLEDGECHECK_UNIQUENESS_FAIL", "ALTERED_INVOICE", "SOURCE_MISMATCH",
        "LENDER_FUNDS_AS_RECEIPTS", "RELATED_PARTY_INFLOW", "COMPETING_LIEN"}

# an undisclosed lien on the loan collateral itself means that collateral is pledged twice
DOUBLE_PLEDGE_HINT = ("receivables and chattel paper",)

PLAIN = {
    "DOUBLE_PLEDGE": "the same collateral is pledged to more than one lender",
    "TAPE_DRESSUP": "bad loans are being reported as good ones",
    "DISGUISED_RECEIPTS": "money from lenders or linked companies is arriving dressed up as customer payments",
    "FAKE_INVOICES": "invoices are fake, inflated or altered",
    "HIDDEN_DEBT": "the borrower has debt it has not disclosed",
    "RELATED_SHELLS": "the borrower is connected to undisclosed shell companies",
    "FIN_MANIPULATION": "the reported financial statements don't fit the evidence",
}

WEIGHT = {"S1": 1.0, "S2": 1.0, "S3": 1.0, "S4": 1.0, "S5": 0.9, "S6": 0.5, "S7": 0.8}
MIN_X = 0.25  # severity x confidence needed for a clue to count as corroboration


def _x(s):
    return s.severity * s.confidence


def assign_mechanisms(sigs) -> dict[str, str]:
    by_id = {s.signal_id: s for s in sigs}
    mech = {}
    for s in sigs:
        if s.type == "COMPETING_LIEN" and any(h in s.explanation for h in DOUBLE_PLEDGE_HINT):
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
        sigs = sorted(by_b.get(b, []), key=lambda s: -_x(s))
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
            if conf == "low" and all(s.type in ("RELATED_ENTITY", "JUDGMENT") for s in ss):
                continue  # a lone affiliate or small judgment is context, not a finding
            findings.append(dict(mechanism=m, confidence=conf, plain=PLAIN[m],
                                 signals=[s.signal_id for s in ss],
                                 corroborated_by=[o.signal_id for o in corroborating],
                                 sources=sorted(sources), systems=sorted({s.system for s in ss}),
                                 first_month=min(s.observed_month for s in ss)))
        order = {"high": 0, "medium": 1, "low": 2}
        findings.sort(key=lambda f: (order[f["confidence"]], f["mechanism"]))
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
                          findings=findings, signals=[s.row() for s in sigs],
                          explanations=explanations.get(b, []), coverage=coverage))
    cases.sort(key=lambda c: -c["priority"])
    return cases
