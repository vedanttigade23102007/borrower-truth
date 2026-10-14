# Business case and requirements (BRD): Borrower Truth

*Prepared the way a bank proposal would be: problem, solution, requirements, resources, timeline, money, alternatives. It fits any bank that lends to non-bank lenders; Wells Fargo is the worked example. Public facts are cited; every other number is labelled as a planning assumption for the bank to replace with its own.*

## 1. Problem
- **The exposure is large, and it sits with the biggest banks.** Bank loans to nondepository financial institutions reached $1.32 trillion in the third quarter of 2025, 10.0% of all bank loans; banks with assets over $100 billion hold about 86% (FDIC, *Banking Issues in Focus* no. 1, Feb 2026, pp. 2–3).
- **The worked example.** Lending to non-bank financial firms is Wells Fargo's largest commercial loan category: $208.8B, 20% of all loans (10-Q, 30 Jun 2026).
- **The risk has already materialised.** In Q1 2026, net charge-offs rose "driven by a single fraud-related loss" (10-Q). Management said it then reviewed the portfolio, sending teams to clients to review their procedures and collateral (Q1 2026 earnings call, secondary). That was a manual, one-off sweep.
- **The frauds hide in several places at once.** In the 2025–26 cases (Tricolor, First Brands; allegations in DOJ and SEC documents) one borrower used several tricks at once. They hid in the loan file, the servicer's system, cash receipts, invoices, lien filings, company records and financial statements. The controls described publicly (field exams, collateral checks such as PledgeCheck) each look in one place, often a sample at a time. The bank's own control set would be mapped in phase 0.

## 2. Proposed solution
A layer that joins seven checks (one per documented trick) into one case per borrower: the finding, the evidence, a suggested fix, and drafted paperwork that a credit officer approves.
- It **uses** the tools the bank already has (Setpoint PledgeCheck results feed S1; simulated in the prototype) rather than replacing them.
- Verdicts come from auditable rules, not a model.
- Its six loan-tape checks are tested against real public loan data (2.23M SEC ABS-EE records). The other checks' thresholds are still set on synthetic books.
- It is a second pair of eyes next to covenants and field exams, not a fix for fraud.
- An open-model agent drafts investigation notes, and never decides.

## 3. Scope
- **In:** the NDFI (non-bank financial) portfolio, starting with one sub-portfolio (auto-finance warehouse facilities) in a read-only, shadow-mode pilot.
- **Out, for now:** automated actions of any kind, customer-facing changes, and other portfolios.

## 4. Requirements
**Functional**
1. Ingest monthly loan tapes, collection-account activity, operating-account activity, UCC and court records, borrower disclosures, financial packages, and PledgeCheck results.
2. Produce one case per borrower with a verdict (likely fraud / worth a look / explained / no issue), the evidence chain, and the source of every clue.
3. Suggest playbook actions and draft letters. Nothing is sent without an officer's approval, and every approval is audited.
4. Route likely-fraud cases to the financial-crimes unit for a suspicious-activity decision (see the control matrix).
5. Replay any past decision from its fingerprinted inputs, rules and code.

**Non-functional**
- Must run inside the bank's environment on open-weight models, so no borrower data leaves the bank.
- A failed feed or check never stops a run: the case says what is missing.
- Monthly run for the full portfolio in minutes. Measured: 13.2M rows in 4.4 s on one laptop; each borrower is independent, so the work splits across machines.
- Bank SSO and entitlements, and encryption at rest (not built in the prototype; see the control matrix).

## 5. Resources (planning assumptions)
| Role | Pilot (4 months) |
|---|---|
| Software engineers (Python, SQL, Java) | 3 × 4 = 12 FTE-months |
| Data engineer (feeds, access) | 1 × 4 = 4 FTE-months |
| Credit-risk SME from the NDFI business (part-time) | 0.5 × 4 = 2 FTE-months |
| Model-risk validator (part-time) | 0.25 × 4 = 1 FTE-month |
| **Total** | **about 19 FTE-months** |
| Compute | negligible: one machine runs the whole book in seconds |
| Data | UCC/lien and court-record feeds: vendor quotes needed (the bank may already license them) |

At a planning rate of $25K–$50K per fully loaded FTE-month, the pilot costs about **$0.5M–$1.0M**. The midpoint, $0.7M, is used below.

## 6. Timeline
| Phase | Weeks | Output | Gate |
|---|---|---|---|
| 0. Sponsor and set-up | 0–4 | sponsor named; data access approved; model-risk tiering; InfoSec and third-party reviews started | Steering committee: approve the pilot |
| 1. Shadow pilot | 5–16 | weekly cases on one sub-portfolio, reviewed by credit officers next to business as usual; thresholds re-checked on bank data | Success and kill criteria (`04-PILOT-PLAN.md`) |
| 2. Validation | 17–28 | independent model validation; run-book; SAR-routing procedure; legal-reviewed letters | Committee: go / no-go for production |
| 3. Production | 29+ | whole NDFI portfolio; integrated with case management and the financial-crimes unit | Ongoing monitoring |

## 7. The money: a break-even model, not a promise
The bank's own loss data will replace these inputs. What can be said honestly now is **how big a single case must be for the pilot to pay for itself**.

- *Loss avoided on one fraud* ≈ E × r × Δt
  - **E** = the bank's exposure to that borrower
  - **r** = the share of that exposure that becomes unrecoverable for each month the fraud keeps running (new advances against bad collateral, cash leaving, collateral decaying)
  - **Δt** = the months earlier the fraud is caught
- *Break-even exposure* E\* = pilot cost ÷ (r × Δt)

| Break-even exposure E\* (pilot cost $0.7M) | caught 1 month earlier | 3 months earlier | 6 months earlier |
|---|---|---|---|
| r = 1% a month | $70.0M | $23.3M | $11.7M |
| r = 3% a month | $23.3M | $7.8M | $3.9M |
| r = 5% a month | $14.0M | $4.7M | $2.3M |

**How to read it:** if the tool moves the bank's response forward by three months on **one** exposure of about $8M, the pilot has paid for itself (at r = 3%).
- On the latest synthetic test (`proof/REPORT_seeds1201-1205.md`) the median was 3 months (90 days) earlier than a quarterly audit. That is a design result, not a measured real-world lead.
- For scale: at Tricolor's bankruptcy its largest lenders were owed more than $900M in total (DOJ, allegations).

**Benefits outside the formula:**
- Field exams go where the evidence is, not to a random sample.
- One audit trail for every decision, ready for examiners.
- Faster, better-documented input to suspicious-activity decisions.
- The manual sweep after a loss becomes a monthly run.

## 8. Alternatives considered
| Option | For | Against | Verdict |
|---|---|---|---|
| Do nothing (quarterly field exams, one-off sweeps after a loss) | no new cost | the audit caught 37% of planted frauds in the latest test; sweeps happen after the loss | not recommended |
| More field exams | proven, understood | sample-based and slow; cost scales with headcount | keep, but aim them with this tool |
| Extend Setpoint PledgeCheck | Wells Fargo already backs it; it sees other lenders' facilities | covers collateral uniqueness and collections, not shells, hidden debt or who paid | keep: already an input to S1 |
| Buy an entity-resolution platform (e.g. Quantexa) | strong relationship matching at scale | one of the seven places; a platform project in its own right | a candidate to feed S6 later |
| **Pilot the layer on top (this proposal)** | joins what each tool sees about one borrower; rules-based and replayable; open models inside the bank | unproven on real bank data; needs feeds and control reviews | **recommended: a 90-day shadow pilot** |

## 9. Dependencies and assumptions
- Credit agreements give the bank the right to request tapes and servicer-system access. Legal to confirm per facility.
- Collection accounts at Wells Fargo, and operating-account visibility where the borrower banks with Wells Fargo.
- Lien and court data licenses.
- A named executive sponsor and a business owner in the NDFI credit team.
