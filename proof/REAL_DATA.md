# Real data: what public SEC filings measured, and what that changed

Borrower Truth's frauds are still planted in synthetic books. What is real now is the yardstick: how honest lenders' loans actually behave, measured on public SEC data, and the five loan-tape checks tested against it. The other checks can't be tested on public loan data.

## What was pulled

- **Loan-level data (SEC Form ABS-EE, Regulation AB II Schedule AL, Item 3):** 56 monthly files from 28 public auto-loan securitizations of 22 lenders (Ally, AmeriCredit (GM Financial), BMW, Bridgecrest (DriveTime), Capital One, CarMax, Carvana non-prime, Carvana prime, Drive Auto (Santander), Exeter, Exeter Select, Fifth Third, Ford Credit, GM Financial prime, Honda, Hyundai, Mercedes-Benz, Nissan, Santander Drive, Toyota, Volkswagen, World Omni).
- 2,231,256 loan rows; 809,924 open loans followed from one month to the next (809,624 month-to-month moves), reporting periods March to May 2026.
- **Company filings (data.sec.gov):** 8-K items, 10-K Exhibit 21 and XBRL financials for 24 public non-bank lenders, pulled 2026-09-14.
- ABS-EE has **no VIN and no borrower identity**, by design of the rule. Raw files stay local (`data/cache/sec`, not in git); only the measured summaries are kept (`data/calibration/`).
- Automated requests declare a contact email and stay at 5 requests a second, half the SEC's limit.

## What the real data changed

| What | Assumed before (generator v2) | Measured on real pools | What changed |
|---|---|---|---|
| A current loan shows no payment in a month | ~1% | 5.5% prime, 9.9% subprime; two months running: at most 1.96% in any pool | Honest auto books in v3 miss payments at the real rate. CURRENT_WITHOUT_PAYMENT's 3% line is above every real pool, so it stays |
| A loan 60+ days late is current next month with no payment | treated as impossible (3 loans = a clue) | 97 of 2,657 cures had no payment (56 explained by an extension or modification); up to 12.2% of late loans in one prime pool | IMPOSSIBLE_TRANSITION now also needs 20% of the late loans, not just 3 |
| A loan's credit score at origination changes between reports | 0.3% honest corrections | 0 of 774,975 loans | Honest scores never change in v3; ATTRIBUTE_REWRITE has no honest base rate to hide in |
| A loan 30-59 days late is 60+ late a month later | 50% | 13.9% to 53.2% | New check ROLL_RATE_TOO_LOW below 7.0%: hidden 60+ day loans make late loans seem to vanish |
| A current loan is 30+ days late next month | 3% x a risk factor | 2.78% overall; by credit band from 0.34% (720+) to 7.17% (<580) | Honest auto loans in v3 move month to month by the measured rates, by credit band and loan age |
| Loans just over the 600 eligibility line | compared with the whole book | loans at 600-612 are at most 1.181x those at 613-625 in any pool | ELIGIBILITY_EDGE_CLUSTER compares each tape with itself (prime and subprime curves differ), flagging above 1.77x |
| How unique a loan is without a VIN | not measured | 787,835 of 787,944 (99.99%) by origination month, amount, term, rate, vehicle, state and score | New check PUBLIC_POOL_OVERLAP: loans on the bank's tape that also sit in the borrower's own public trust |

## Every loan-tape threshold against every real pool

Each real pool is an honest lender's tape. None may trip a loan-tape check.

| Pool | Lender tier | Current, unpaid 2 months | 30-59 to 60+ | 60+ to current, unpaid | 600-612 vs 613-625 |
|---|---|---|---|---|---|
| Exeter Select Automobile Receivables Trust 2025-1 | near-prime | 1.22% | 38.0% (n=473) | 0.0% (n=373) | 0.612x |
| ALLY AUTO RECEIVABLES TRUST 2024-1 | prime | 0.95% | 16.3% (n=455) | 5.2% (n=230) | 1.054x |
| BMW Vehicle Owner Trust 2023-A | prime | 0.50% | 25.8% (n=167) | 0.0% (n=75) | 0.554x |
| Capital One Prime Auto Receivables Trust 2023-1 | prime | 0.13% | 20.0% (n=85) | 0.0% (n=46) | too few loans |
| CarMax Auto Owner Trust 2024-1 | prime | 1.15% | 29.8% (n=981) | 0.0% (n=775) | 0.797x |
| Carvana Auto Receivables Trust 2024-P2 | prime | 0.78% | 23.1% (n=221) | 0.0% (n=140) | 0.884x |
| Fifth Third Auto Trust 2023-1 | prime | 0.75% | 21.8% (n=252) | 0.0% (n=118) | too few loans |
| Ford Credit Auto Owner Trust 2024-A | prime | 0.95% | 13.9% (n=230) | 4.5% (n=66) | 0.847x |
| GM Financial Consumer Automobile Receivables Trust 2024-1 | prime | 0.56% | 19.3% (n=285) | 0.0% (n=97) | 0.656x |
| Honda Auto Receivables 2024-1 Owner Trust | prime | 0.51% | 21.4% (n=337) | 0.0% (n=107) | 0.498x |
| Hyundai Auto Receivables Trust 2024-A | prime | 0.75% | 17.0% (n=435) | 8.6% (n=117) | 0.418x |
| Mercedes-Benz Auto Receivables Trust 2024-1 | prime | 0.62% | 26.5% (n=170) | 0.0% (n=64) | too few loans |
| Nissan Auto Receivables 2024-A Owner Trust | prime | 0.32% | 17.5% (n=177) | 0.0% (n=45) | too few loans |
| Toyota Auto Receivables 2024-A Owner Trust | prime | 0.65% | 22.3% (n=354) | 0.0% (n=148) | 0.0x |
| Volkswagen Auto Loan Enhanced Trust 2023-1 | prime | 0.82% | 19.1% (n=257) | 0.0% (n=64) | 0.371x |
| World Omni Auto Receivables Trust 2024-A | prime | 0.38% | 22.7% (n=295) | 12.2% (n=115) | too few loans |
| AmeriCredit Automobile Receivables Trust 2022-1 | subprime | 1.53% | 18.2% (n=1,552) | 0.2% (n=591) | 0.739x |
| AmeriCredit Automobile Receivables Trust 2024-1 | subprime | 1.42% | 20.7% (n=3,647) | 0.1% (n=1,652) | 0.787x |
| Bridgecrest Lending Auto Securitization Trust 2024-1 | subprime | 0.56% | 32.5% (n=1,439) | 0.0% (n=1,938) | 1.131x |
| Bridgecrest Lending Auto Securitization Trust 2026-2 | subprime | 0.21% | 35.1% (n=424) | 0.0% (n=276) | 1.164x |
| Carvana Auto Receivables Trust 2021-N1 | subprime | 1.67% | 26.2% (n=527) | 0.0% (n=722) | 1.156x |
| Carvana Auto Receivables Trust 2021-N4 | subprime | 1.33% | 27.3% (n=671) | 0.0% (n=899) | 1.105x |
| DRIVE AUTO RECEIVABLES TRUST 2025-2 | subprime | 1.25% | 26.0% (n=6,230) | 0.0% (n=3,686) | 1.129x |
| Drive Auto Receivables Trust 2024-1 | subprime | 1.15% | 25.6% (n=4,145) | 0.0% (n=2,817) | 1.181x |
| Exeter Automobile Receivables Trust 2024-1 | subprime | 1.96% | 36.2% (n=1,987) | 0.0% (n=1,590) | 0.993x |
| Exeter Automobile Receivables Trust 2026-2 | subprime | 0.55% | 53.2% (n=1,328) | 0.0% (n=333) | 1.044x |
| Santander Drive Auto Receivables Trust 2024-1 | subprime | 0.94% | 25.0% (n=3,420) | 0.0% (n=2,429) | 1.023x |
| Santander Drive Auto Receivables Trust 2026-1 | subprime | 0.39% | 33.4% (n=4,071) | 0.0% (n=1,311) | 1.056x |
| **Line the check uses** | | **above 3%** | **below 7.0%** | **20% and 3+ loans** | **above 1.77x** |

Result: **0 of 28 real pools trip any of these checks.** `tests/test_sec_calibration.py` fails if a threshold is ever moved inside the real range.

## A design the real data rejected

The first peer benchmark compared each tape's overall share of late loans with what public pools of the same credit mix and loan age report. Tested on the real pools (each against the others, leaving out its own lender), it flagged **3 of 28 honest pools**: Bridgecrest Lending Auto Securitization Trust 2026-2 (0.19x expected), Carvana Auto Receivables Trust 2024-P2 (0.37x expected), Ford Credit Auto Owner Trust 2024-A (0.27x expected). Lenders differ far more than credit score explains, and a newly issued pool starts all-current by rule. So it was dropped for the roll-forward check above, which does not depend on the lender's level of losses.

## Real SEC filings of public non-bank lenders

8-K items and 10-K Exhibit 21 for 24 lenders of the kinds Wells Fargo lends to, over the 12 months to 2026-09-14.

| Lender | Kind | 8-Ks | Item 2.03 (new debt) | Item 2.04 (acceleration) | Subsidiaries in Exhibit 21 |
|---|---|---|---|---|---|
| Credit Acceptance (CACC) | auto finance | 21 | 5 | 0 | 62 |
| Consumer Portfolio Services (CPSS) | auto finance | 21 | 7 | 0 | 9 |
| CarMax (KMX) | auto finance | 12 | 1 | 0 | 5 |
| Ares Capital (ARCC) | business development company | 15 | 8 | 0 | 43 |
| Blackstone Secured Lending (BXSL) | business development company | 11 | 1 | 0 | not found in the filing index |
| FS KKR Capital (FSK) | business development company | 27 | 2 | 0 | 24 |
| Golub Capital BDC (GBDC) | business development company | 19 | 3 | 0 | 11 |
| Hercules Capital (HTGC) | business development company | 10 | 2 | 0 | 27 |
| Main Street Capital (MAIN) | business development company | 24 | 3 | 0 | not found in the filing index |
| Blue Owl Capital Corp (OBDC) | business development company | 16 | 2 | 0 | 52 |
| Prospect Capital (PSEC) | business development company | 10 | 1 | 0 | not found in the filing index |
| Affirm Holdings (AFRM) | consumer finance | 8 | 0 | 0 | not found in the filing index |
| Atlanticus Holdings (ATLC) | consumer finance | 2 | 0 | 0 | not found in the filing index |
| Enova International (ENVA) | consumer finance | 18 | 6 | 0 | 101 |
| Navient (NAVI) | consumer finance | 10 | 1 | 0 | 6 |
| OneMain Holdings (OMF) | consumer finance | 10 | 3 | 0 | 94 |
| Oportun Financial (OPRT) | consumer finance | 16 | 2 | 0 | not found in the filing index |
| Regional Management (RM) | consumer finance | 11 | 1 | 0 | 45 |
| Upstart Holdings (UPST) | consumer finance | 9 | 0 | 0 | 3 |
| World Acceptance (WRLD) | consumer finance | 14 | 1 | 0 | 26 |
| loanDepot (LDI) | mortgage | 11 | 3 | 0 | not found in the filing index |
| PennyMac Financial Services (PFSI) | mortgage | 8 | 0 | 0 | 7 |
| Rocket Companies (RKT) | mortgage | 16 | 5 | 0 | 4 |
| UWM Holdings (UWMC) | mortgage | 18 | 1 | 0 | not found in the filing index |
| **Total** | | **337** | **58** | **0** | |

What it means for the design: new-debt 8-Ks are routine (58 in a year across 24 lenders), so an 8-K alone is never a clue. FILED_DEBT_UNDISCLOSED fires only when a lender named in the borrower's own filings was still not disclosed to the bank two months later. Lenders list up to about 100 subsidiaries, so a listing is treated as public disclosure, not concealment: it links a company to the borrower, and matters only when that company also pays the borrower or holds a lien.

## Limits

- Only **registered** securitizations file ABS-EE. Many smaller lenders use private (Rule 144A) deals; Tricolor's deals were private, per the bank defendants' court filings reported by Octus; on EDGAR its two filing entities filed only Form ABS-15G (19 filings, 2018–2025), never ABS-EE. The yardstick comes from larger public lenders.
- No VIN and no borrower ID: matching a tape to a public trust is a fingerprint, so it opens a question and the officer asks for VINs to settle it.
- Private borrowers file nothing with the SEC; the filings checks cover only borrowers or parents that file.
- Two consecutive months per pool, spring 2026. More months would tighten the ranges; the checks sit well outside them already.
- The frauds are still planted: real data makes the honest background and the thresholds real, not the catch rate.

Rebuild: `python -m bt.sec.absee fetch`, `python -m bt.sec.calibrate`, `python -m bt.sec.filings`, `python -m bt.sec.report`.
