# EVIDENCE: source index

Every source was downloaded (or, for two DOJ pages behind a bot check, captured through a normal browser visit) and stored in `research/sources/` as `.raw` + `.txt`. `research/verify.py` matches all 57 deck claims against these files: **57/57 matched, 42 primary, 15 secondary**. Added after Vedant's review: the WF stack (intern posting = primary; the Kafka/Airflow ads = search snippets, because the pages no longer load), the Fargo architecture and Agentspace (VentureBeat, CIO Dive), Kaggle and ZeroGPU free GPUs, the CORD/FUNSD datasets (FUNSD licence to confirm), and OCC Bulletin 2011-12. The claim table is `research/VERIFY.md`.

| Source key | What it is | Tier | Supports |
|---|---|---|---|
| `wf-10q-2026q2` | Wells Fargo 10-Q, quarter ended 30 Jun 2026 | primary | NDFI $208.8B / 20% / +9%, collateral controls, headcount, assets, efficiency, legal note, OCC agreement, fair access, WIM, IB fees |
| `wf-10q-2026q1` | Wells Fargo 10-Q, quarter ended 31 Mar 2026 | primary | "single fraud-related loss" |
| `wf-10k-2025` | Wells Fargo 10-K for 2025 | primary | asset cap removed 3 Jun 2025; Head of AI |
| `wf-newsroom-fed-order-terminated` | WF newsroom, 5 Mar 2026 | primary | Fed 2018 consent order terminated |
| `occ-formal-agreement-2024-72` | OCC formal agreement, 12 Sep 2024 | primary | AML articles, Article XII |
| `sec-tricolor-2026-77` | SEC press release 2026-77 | primary | Tricolor double pledging, "appear current", $1.9B ABS |
| `doj-tricolor` | DOJ SDNY release 25-271, 17 Dec 2025 | primary | $2.2B pledged vs $1.4B real; collateral manipulation; "pull this up on your screen"; >$900M owed |
| `doj-first-brands` | DOJ SDNY release 26-012, 29 Jan 2026 | primary | fake/inflated invoices, double/triple pledging, falsified financials, James Entities, disguised receipts, $5B/$12M/$9B |
| `setpoint-pledgecheck` | Setpoint release, 29 Oct 2025 | primary | backed by Citi and Wells Fargo; four checks (uniqueness, data integrity, completeness, single record); borrower-uploaded tapes |
| `gleif-level2`, `courtlistener-api` | data providers' own pages | primary | free ownership data; court records API |
| `wf-job-tech-intern-2027` | WF careers posting | primary | role, eligibility, skills |
| `fool-wf-2026q1-call` | Q1 2026 earnings call transcript (Motley Fool) | secondary | card +~60%, "isolated incident", 23 quarters of cuts, "follow the money trail", loss in real estate finance category |
| `cnbc-mfs` | CNBC, 18 May 2026, citing FT/insolvency documents | secondary | WF exposure to MFS ~£143M |
| `yahoo-collateral-checkers` | Bloomberg via Yahoo | secondary | Guidehouse +80% demand; cash reconciliations |

**Dropped during verification:**
- First Brands "$2.7B fake receivables": not in the DOJ release.
- "PledgeCheck can't see whether tapes lie": contradicted by Setpoint's own list of checks.
- ABS-EE "no VIN" is used only as a data-design note, tagged secondary.

**Legal line:** all Tricolor and First Brands facts are allegations. WF has not named its Q1 2026 fraud-loss borrower, and nothing here suggests who it was.
