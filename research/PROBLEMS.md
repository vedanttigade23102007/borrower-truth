# PROBLEMS — whole-company scan, scored

Six candidate problems, one or more per area of Wells Fargo, scored 0–2 on seven tests (max 14).
Every fact cited is in `VERIFY.md` (ID in brackets). Scores are judgement — the reasons are written next to them so they can be argued with.

| Test | 0 | 1 | 2 |
|---|---|---|---|
| Real | rumour | news / call transcript | WF's own filing or a regulator/court document |
| Still open | solved | partly | clearly unsolved today |
| Costs money | none visible | indirect | direct losses or blocked growth, in the hundreds of millions+ |
| Buildable | needs WF's private data | synthetic only, weakly realistic | public data + realistic synthetic |
| Provable | can't measure | soft measures | planted-case catch rates vs a baseline |
| Fits the job | unrelated | partly | Python/SQL/Java data engineering, the posted skills [J1] |
| Big enough | one cause | two or three | many causes → genuinely needs several connected systems |

## Scores

| # | Problem | Area | Real | Open | Money | Build | Prove | Job | Big | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|
| A | **Fraud by borrowers in loans to non-bank financial firms** | Commercial / CIB | 2 | 2 | 2 | 1 | 2 | 2 | 2 | **13** |
| E | AML data completeness (OCC agreement Art. X) | Risk & compliance | 2 | 2 | 1 | 2 | 2 | 2 | 1 | **12** |
| B | Growth-time fraud in new cards and auto loans | Consumer | 1 | 1 | 2 | 1 | 2 | 2 | 2 | **11** |
| D | Fair-access account-closure decision audit | Risk & compliance | 2 | 2 | 0 | 1 | 1 | 1 | 1 | **8** |
| C | Wealth unit cost + vendor outages | Wealth | 1 | 1 | 1 | 0 | 1 | 2 | 1 | **7** |
| F | Banker workload as investment banking grows | CIB | 2 | 1 | 1 | 1 | 1 | 1 | 0 | **7** |

## Why A wins — and why it is not a landslide

**A — 13/14.**
- **Real (2):** it's WF's largest commercial loan category, at $208.8B and 20% of all loans [W1, W3]. It grew 9% in six months [W2]. The Q1 2026 10-Q attributes higher charge-offs to "a single fraud-related loss" [W5], and the call places it in this category [C5].
- **Open (2):**
  - Management sent teams to trace client cash flows by hand after the loss [C4].
  - Frauds with the same pattern keep landing: Tricolor [T1–T8], First Brands [F1–F5], MFS (2026), where WF's exposure was ~£143M [M2, secondary].
- **Money (2):** Tricolor's lenders were owed >$900M [T8]. First Brands had >$9B liabilities against $12M cash [F2].
- **Build (1, not 2):** borrower tapes, bank-account flows and invoices are private. Public registries cover ownership [D1], liens (per-state) and courts [D2]. The rest must be realistic synthetic data. This is the honest weak spot.
- **Prove (2):** plant each documented fraud mechanism in a synthetic book, then measure catch rate per system against a sample-audit baseline.
- **Big (2):** the documented mechanisms are six distinct causes (see the cause map in `design/SYSTEM-DESIGN.md`).

**E — 12/14, the close runner-up.** The primary evidence is as strong [W10, W17] and it's easier to build. It loses on money (no penalty attached yet) and size: it's essentially one cause, data completeness, which contradicts the multi-system brief. It also has established vendors: lineage and data-observability tools.

**B — 11.** Real problem, but the evidence is only the call transcript [C1], and the space is crowded with mature fraud vendors.

**D, C, F — 7–8.** D is politically charged with little money attached. C needs private vendor data. F is a productivity wish rather than a loss.

## What changed during verification (recorded so it isn't re-argued)
1. **Setpoint PledgeCheck (WF-backed, S1) covers more than we first said.** Besides uniqueness it checks VIN/address consistency and matches actual collections to reported data [S3]. The design must **not** claim to beat it at collateral-pool checks. It ingests its result instead.
2. **The gap PledgeCheck leaves is borrower-level, not pool-level.** First Brands' documented tricks sat outside the pool: related "James Entities" carrying hidden debt [F3], loan proceeds disguised as customer receipts [F4], manipulated financials [F5], fake invoices sold to factors [F1]. Loan money dressed as customer cash would *pass* a collections-match check, because the cash really arrives.
3. **The "$2.7B fake receivables" First Brands figure is not in the DOJ release.** It is dropped. We use DOJ's own numbers [F2].
