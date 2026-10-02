# Integration: how a bank plugs Borrower Truth in on day one

Written 2 Oct 2026 (plan: `INTEGRATION-PLAN.md`, approved by Vedant). All data in this project is synthetic.

**Read this first.** This project has never been connected to a real bank system. Everything below that describes a bank's side (which system holds what, who owns a feed, how often it arrives) is marked **typical, to confirm with the bank**. It describes how large US banks usually organise this work, not how any particular bank does. Each one is a question for the first meeting, not a fact.

---

## 1. What gets installed, and where

| Part | What it is | Where it runs |
|---|---|---|
| The checks (S1–S7, the combiner) | a Python job, run monthly, plus a streaming worker for same-day payment alerts | inside the bank's network |
| The case service | a Java service with its own database and audit log; holds cases, fix steps and decisions | inside the bank's network |
| The console | the credit officer's screen (Next.js) | inside the bank's network, behind the bank's sign-in |
| The file mapper | a command that turns a borrower's own spreadsheet into the checks' tables (`bt.mapper`) | run by the bank's data team |

- **Borrower data can stay inside the bank, with two settings to get right:**
  - The checks, the case service, the console and the mapper send nothing outside.
  - The optional investigator agent defaults, in this demo, to open models hosted on the Hugging Face router. That sends case evidence outside, which is fine for synthetic data and not for a bank. In a bank it runs with `--backend local`, on the bank's own hardware, or stays off.
  - The optional document module runs its model locally, and is off by default.
  - The public lookups (GLEIF, SEC EDGAR) send a company's name or ID to a public registry. That says which companies the bank is looking at, but no borrower data. Whether that's acceptable is the bank's call (typical, to confirm with the bank).
- **Database:** H2 today. A bank would most likely want Postgres or its own standard database (typical, to confirm with the bank). **Not checked on Postgres:** `REVIEW.md` gap 9 lists the three edits it needs.
- **Size:** measured on one laptop up to 400 synthetic borrowers: 13.2M rows in 4.39 s for one month (`proof/scale.json`). A monthly run is not a capacity problem at that size. A bank's whole book is not measured.

---

## 2. Where each input comes from

The inputs and what each check loses without them are in `DATA-CONTRACT.md`. This table adds where a bank would usually get each one. **Every row is typical, to confirm with the bank.**

| Input | Usually held in | Usually owned by | Arrives |
|---|---|---|---|
| Borrowers, credit lines | the commercial loan system | credit administration | on change |
| Collection-account payments | the deposit system, under cash dominion | treasury and cash management operations | daily |
| Operating-account outflows | the deposit system, only if the bank holds that account | treasury and cash management operations | daily |
| Borrower disclosures | onboarding files and compliance certificates (documents, typed in today) | the credit officer | on change, at least quarterly |
| Financial statements | the borrower's reporting package | the credit officer | quarterly |
| Loan tape, pledged invoices | the borrower's own borrowing-base report, usually a spreadsheet | the borrower sends it; collateral monitoring checks it | monthly |
| Servicer-system records | field-exam access to the borrower's servicing system | field examination | monthly sample |
| Company registry, officers and owners | the KYC platform or a registry data vendor | KYC and onboarding operations | monthly |
| Lien filings, court judgments | a lien and litigation search vendor | collateral monitoring or legal | monthly |
| PledgeCheck results | Setpoint (simulated in this project) | collateral monitoring | monthly |
| GLEIF, SEC filings, ABS-EE | public, free | nobody at the bank; fetched by the job | monthly or as filed |

**The four core inputs** (borrowers, the company registry, payments, disclosures) must arrive before anything runs. See `DATA-CONTRACT.md`, "What works on day one".

**How files arrive.** A monthly drop folder per input, one file per input (typical, to confirm with the bank). Each file goes through the data-quality gate (`bt/pipeline/dq.py`):
- A bad file is quarantined, and the last good copy is used.
- With no last good copy, the run stops with an error rather than produce cases.

---

## 3. Borrower spreadsheets: the file mapper

Borrowers send loan tapes and invoice lists in their own layouts. The bank's data team maps each lender's layout once, then the same mapping runs every month:

1. **Read.** CSV or Excel (.xlsx), values only, never formulas. Macro workbooks (.xlsm) and oversized files are refused.
2. **Pick, once per lender.** A person picks the sheet and the header row.
3. **Suggest.** The mapper matches the lender's column names to ours, and a person confirms the match once per lender. Nothing is applied silently.
4. **Remember.** The confirmed mapping is saved as a small file for that lender. If the lender renames or drops a column later, the mapper stops and asks.
5. **Convert:** dates to reporting months, days late to late buckets, "Y/N" to yes/no, "$1,234.56" to a number. Total rows are dropped.
6. **Check before writing:**
   - every required column is mapped
   - unconvertible cells stop the run above 1%, and every one is listed
   - no loan appears twice in a month
   - values are in range
   - **the mapped balances add up to the borrower's borrowing-base certificate total, within $1**
7. **Report.** A mapping report for a person to sign.

The other inputs come from bank systems and vendors with fixed layouts. Those are mapped once per bank, as part of the pilot.

---

## 4. Matching identities

The bank knows its borrowers by its own customer numbers, and the checks use their own IDs. A crosswalk links the two, once per borrower:
- bank customer number ↔ `borrower_id`
- the borrower's legal entity in the registry ↔ `entity_id`

Where the bank's KYC record already holds a registry ID or an LEI, the link is direct (typical, to confirm with the bank). Where it doesn't, it's matched by legal name and address and confirmed by a person.

## 5. The calendar

The checks count in reporting months. A real deployment counts from each facility's first month on the bank's books: month 1 is the first borrowing-base report after onboarding.
- Real dates in borrower files become reporting months in the mapper.
- **Code change needed:** the data-quality gate still assumes this project's 24 synthetic months. That becomes the run's own calendar, and every recorded decision must replay identically afterwards.

---

## 6. The first 90 days

| When | What happens | What it proves |
|---|---|---|
| Week 1 | Core inputs and the registry for a pilot group of borrowers; one run on last month's data | the feeds work and the cases make sense to an officer |
| Month 1 | Each pilot borrower's tape or invoice file mapped and signed off | the mapper handles real layouts |
| Months 1–3 | **Shadow mode:** the checks run every month next to the existing field exams and borrowing-base reviews. No case drives a decision. Each case is compared with what the examiners found | whether the cases find real problems, and how many honest borrowers they send to review on real data |
| After month 3 | If the shadow results hold up, officers work the queue. The audit log, four-eyes letters and second checks are on from the first live case | — |

The pilot group: about 10 borrowers with the most complete data (typical, to confirm with the bank). Shadow mode is what makes the synthetic numbers real numbers: until then, every figure in `proof/` is a measurement on synthetic books.

---

## 7. Who does what

**Every row is typical, to confirm with the bank.**

| Who | Owns |
|---|---|
| The data team | the feeds, the drop folders, the file mapper, the crosswalk |
| Credit officers | the cases: clearing, escalating, approving fix steps |
| A second person (reviewer or credit manager) | four-eyes letters and second checks on clears |
| Model risk | review of the checks. They are documented rules, not a statistical model. The optional document module and investigator agent are models, off by default; turning one on brings it into model-risk review |
| IT security | access, sign-in, the audit log's retention |
| Field examination | servicer-system access, and comparing shadow-mode cases with their own findings |

---

## 8. Security and access

- **Sign-in:** the console has none of its own. It sits behind the bank's sign-in, which decides who can see which borrowers and who counts as a second person. **Not built here** (`WHY.md` changes 5 and 6).
- **Writes:** the case service accepts writes only with a shared key today. A bank would replace that with its own service identity (typical, to confirm with the bank).
- **Audit log:** append-only. No update or delete path exists, and a test checks that.
- **Borrower files are untrusted:** the mapper reads values only and refuses macro workbooks and oversized files.

---

## 9. What has not been tested

- **A real bank system.** Never connected to one.
- **Real borrower data.** All borrower data is synthetic. The real data used so far is public: SEC ABS-EE loan records and SEC filings.
- **Postgres:** not checked.
- **The bank's sign-in:** not built.
- **Scale beyond one laptop run:** not measured.
- **Real borrower spreadsheets:** not seen. The mapper is tested on synthetic files written in a lender-like layout, and on the field names real lenders use in SEC ABS-EE reports.
