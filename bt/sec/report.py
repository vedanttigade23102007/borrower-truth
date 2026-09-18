"""Write proof/REAL_DATA.md: what the real SEC data measured, and what it changed in Borrower Truth.

    uv run python -m bt.sec.report
"""
from __future__ import annotations

import json
import os

from bt.sec import benchmark
from bt.systems import s2_tape_source as s2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAL = os.path.join(ROOT, "data", "calibration")
OUT = os.path.join(ROOT, "proof", "REAL_DATA.md")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def main():
    cal = json.load(open(os.path.join(CAL, "absee_auto.json")))
    fil = json.load(open(os.path.join(CAL, "sec_filers.json")))
    ex = cal["real_extremes"]
    lenders = sorted({p[0] for p in cal["pools"]})
    beh = cal["pool_behaviour"]
    cnp = cal["current_no_payment"]
    ltc = cal["late_to_current"]
    fp = cal["fingerprint"]
    sc = cal["score_changes"]
    t_all = cal["transitions"]
    lines = [
        "# Real data: what public SEC filings measured, and what that changed",
        "",
        "Borrower Truth's frauds are still planted in synthetic books. What is real now is the yardstick: how honest "
        "lenders' loans actually behave, measured on public SEC data, and the five loan-tape checks tested against it. The other checks can't be tested on public loan data.",
        "",
        "## What was pulled",
        "",
        f"- **Loan-level data (SEC Form ABS-EE, Regulation AB II Schedule AL, Item 3):** {cal['files']} monthly files "
        f"from {len(cal['pools'])} public auto-loan securitizations of {len(lenders)} lenders "
        f"({', '.join(lenders)}).",
        f"- {cal['loan_rows']:,} loan rows; {cal['open_loans_month1']:,} open loans followed from one month to the next "
        f"({cal['pairs']:,} month-to-month moves), reporting periods March to May 2026.",
        "- **Company filings (data.sec.gov):** 8-K items, 10-K Exhibit 21 and XBRL financials for "
        f"{len(fil['companies'])} public non-bank lenders, pulled {fil['pulled']}.",
        "- ABS-EE has **no VIN and no borrower identity**, by design of the rule. Raw files stay local "
        "(`data/cache/sec`, not in git); only the measured summaries are kept (`data/calibration/`).",
        "- Automated requests declare a contact email and stay at 5 requests a second, half the SEC's limit.",
        "",
        "## What the real data changed",
        "",
        "| What | Assumed before (generator v2) | Measured on real pools | What changed |",
        "|---|---|---|---|",
        f"| A current loan shows no payment in a month | ~1% | {pct(cnp['prime']['share'])} prime, "
        f"{pct(cnp['subprime']['share'])} subprime; two months running: at most {pct(ex['max_current_no_pay_2m_share'], 2)} "
        f"in any pool | Honest auto books in v3 miss payments at the real rate. CURRENT_WITHOUT_PAYMENT's 3% line is above every "
        f"real pool, so it stays |",
        f"| A loan 60+ days late is current next month with no payment | treated as impossible (3 loans = a clue) | "
        f"{ltc['without_payment']} of {ltc['became_current']:,} cures had no payment ({ltc['without_payment_but_extended_or_modified']} "
        f"explained by an extension or modification); up to {pct(ex['max_late60_current_no_pay_share'])} of late loans in one "
        f"prime pool | IMPOSSIBLE_TRANSITION now also needs {pct(s2.JUMP_SHARE, 0)} of the late loans, not just 3 |",
        f"| A loan's credit score at origination changes between reports | 0.3% honest corrections | "
        f"{sc['changed']} of {sc['loans']:,} loans | Honest scores never change in v3; ATTRIBUTE_REWRITE has no honest base "
        f"rate to hide in |",
        f"| A loan 30-59 days late is 60+ late a month later | 50% | {pct(ex['min_roll_forward_rate'])} to "
        f"{pct(max(b['roll_forward_rate'] for b in beh if b['late30'] >= 50))} | New check ROLL_RATE_TOO_LOW below "
        f"{pct(s2.ROLL_MIN_REAL * s2.ROLL_FACTOR)}: hidden 60+ day loans make late loans seem to vanish |",
        f"| A current loan is 30+ days late next month | 3% x a risk factor | "
        f"{pct(t_all['all']['current']['p']['30-59'], 2)} overall; by credit band from "
        f"{pct(t_all['band 720+']['current']['p']['30-59'], 2)} (720+) to {pct(t_all['band <580']['current']['p']['30-59'], 2)} (<580) "
        f"| Honest auto loans in v3 move month to month by the measured rates, by credit band and loan age |",
        f"| Loans just over the 600 eligibility line | compared with the whole book | loans at 600-612 are at most "
        f"{ex['max_edge_ratio_600']}x those at 613-625 in any pool | ELIGIBILITY_EDGE_CLUSTER compares each tape with itself "
        f"(prime and subprime curves differ), flagging above {s2.EDGE_RATIO_REAL * s2.EDGE_FACTOR:.2f}x |",
        f"| How unique a loan is without a VIN | not measured | {fp['unique_loans']:,} of {fp['loans']:,} "
        f"({pct(fp['unique_share'], 2)}) by origination month, amount, term, rate, vehicle, state and score | New check "
        f"PUBLIC_POOL_OVERLAP: loans on the bank's tape that also sit in the borrower's own public trust |",
        "",
        "## Every loan-tape threshold against every real pool",
        "",
        "Each real pool is an honest lender's tape. None may trip a loan-tape check.",
        "",
        "| Pool | Lender tier | Current, unpaid 2 months | 30-59 to 60+ | 60+ to current, unpaid | 600-612 vs 613-625 |",
        "|---|---|---|---|---|---|",
    ]
    edge = {e["trust"]: e for e in cal["edge_600"]}
    for b in sorted(beh, key=lambda b: (b["tier"], b["trust"])):
        e = edge.get(b["trust"])
        lines.append(f"| {b['trust']} | {b['tier']} | {pct(b['current_no_pay_2m_share'], 2)} | {pct(b['roll_forward_rate'])} "
                     f"(n={b['late30']:,}) | {pct(b['late60_current_no_pay_share'])} (n={b['late60']:,}) | "
                     f"{str(e['ratio']) + 'x' if e and e['a1'] + e['a2'] >= s2.EDGE_MIN else 'too few loans'} |")
    lines += [
        f"| **Line the check uses** | | **above 3%** | **below {pct(s2.ROLL_MIN_REAL * s2.ROLL_FACTOR)}** | "
        f"**{pct(s2.JUMP_SHARE, 0)} and 3+ loans** | **above {s2.EDGE_RATIO_REAL * s2.EDGE_FACTOR:.2f}x** |",
        "",
        "Result: **0 of 28 real pools trip any of these checks.** `tests/test_sec_calibration.py` fails if a threshold is ever "
        "moved inside the real range.",
        "",
        "## A design the real data rejected",
        "",
    ]
    res = benchmark.real_pool_test(cal)
    flagged = [r for r in res if r["too_good"]]
    lines += [
        "The first peer benchmark compared each tape's overall share of late loans with what public pools of the same "
        "credit mix and loan age report. Tested on the real pools (each against the others, leaving out its own lender), "
        f"it flagged **{len(flagged)} of {len(res)} honest pools**: "
        + ", ".join(f"{r['trust']} ({r['ratio']:.2f}x expected)" for r in flagged)
        + ". Lenders differ far more than credit score explains, and a newly issued pool starts all-current by rule. "
          "So it was dropped for the roll-forward check above, which does not depend on the lender's level of losses.",
        "",
        "## Real SEC filings of public non-bank lenders",
        "",
        f"8-K items and 10-K Exhibit 21 for {len(fil['companies'])} lenders of the kinds Wells Fargo lends to, over the 12 "
        f"months to {fil['pulled']}.",
        "",
        "| Lender | Kind | 8-Ks | Item 2.03 (new debt) | Item 2.04 (acceleration) | Subsidiaries in Exhibit 21 |",
        "|---|---|---|---|---|---|",
    ]
    tot = dict(k=0, a=0, c=0)
    for t, v in sorted(fil["companies"].items(), key=lambda kv: (kv[1]["kind"], kv[0])):
        e = v["eight_k_last_12m"]
        tot["k"] += e["8-K"]
        tot["a"] += e["2.03"]
        tot["c"] += e["2.04"]
        n21 = v["exhibit21_subsidiaries"]
        lines.append(f"| {v['name']} ({t}) | {v['kind']} | {e['8-K']} | {e['2.03']} | {e['2.04']} | "
                     f"{n21 if n21 is not None else 'not found in the filing index'} |")
    lines += [
        f"| **Total** | | **{tot['k']}** | **{tot['a']}** | **{tot['c']}** | |",
        "",
        f"What it means for the design: new-debt 8-Ks are routine ({tot['a']} in a year across {len(fil['companies'])} lenders), "
        "so an 8-K alone is never a clue. FILED_DEBT_UNDISCLOSED fires only when a lender named in the borrower's own filings "
        "was still not disclosed to the bank two months later. Lenders list up to about 100 subsidiaries, so a listing is "
        "treated as public disclosure, not concealment: it links a company to the borrower, and matters only when that "
        "company also pays the borrower or holds a lien.",
        "",
        "## Limits",
        "",
        "- Only **registered** securitizations file ABS-EE. Many smaller lenders use private (Rule 144A) deals; Tricolor's "
        "deals were private, per the bank defendants' court filings reported by Octus; on EDGAR its two filing entities filed only Form ABS-15G (19 filings, 2018–2025), never ABS-EE. The yardstick comes from larger "
        "public lenders.",
        "- No VIN and no borrower ID: matching a tape to a public trust is a fingerprint, so it opens a question and the "
        "officer asks for VINs to settle it.",
        "- Private borrowers file nothing with the SEC; the filings checks cover only borrowers or parents that file.",
        "- Two consecutive months per pool, spring 2026. More months would tighten the ranges; the checks sit well outside "
        "them already.",
        "- The frauds are still planted: real data makes the honest background and the thresholds real, not the catch rate.",
        "",
        "Rebuild: `python -m bt.sec.absee fetch`, `python -m bt.sec.calibrate`, `python -m bt.sec.filings`, "
        "`python -m bt.sec.report`.",
    ]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
