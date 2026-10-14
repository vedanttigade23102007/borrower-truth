# Day-one integration: plan

**Status: approved by Vedant on 2 Oct 2026 (Excel allowed, values only; a command first). Built: `INTEGRATION.md`, `bt/mapper`, the calendar change. What changed from this plan, and why, is change 21 in the decision log (kept private).** Written 2 Oct 2026, after the fresh run on seeds 901–905 passed.

## Why this step

After "what does it catch?", a bank's next question is "what do my people do on Monday?". Today the honest answer is: deliver 17 files in our own layout, with months numbered 0 to 23. No bank has that. Two pieces close the gap:

1. **`INTEGRATION.md`**: how a bank plugs it in on day one. It covers what runs where, which bank system feeds each input, the order to switch things on, and what stays with people.
2. **A file mapper.** It takes a lender's own spreadsheet (its loan tape or invoice list, in its own column names and formats), maps it onto our tables with checks, and writes a report a person signs off.

## Part 1: `INTEGRATION.md` (a document, no code)

1. **What gets installed, and where.**
   - The parts:
     - the checks (a Python job, monthly, plus daily payment alerts)
     - the case service (Java)
     - the console
   - Everything runs inside the bank's network, and no data leaves it.
   - Database: H2 today. A bank would likely use Postgres, which is **not checked** (the buyer review, kept private, lists the three edits as gap 9).
2. **Where each input comes from in a bank.** One table: input → the bank system or vendor that holds it → who owns the feed. For example:
   - payments → the deposit system
   - company registry and owners → the KYC platform
   - loan tapes and invoices → each borrower's borrowing-base report, through the mapper
   - liens and judgments → a lien-search vendor
3. **Matching identities.** The bank's customer numbers are linked to our borrower and company IDs, once per borrower.
4. **The calendar.** Real dates become reporting months, counted from the facility's first month.
5. **The first 90 days.**
   - **Week 1:** core inputs plus the registry, run once on last month.
   - **Month 1:** map each pilot borrower's own files.
   - **Months 1–3:** shadow mode next to the existing field exams. The cases are compared with what the examiners find, and no case drives a decision.
   - **After that:** the officers work the queue.
6. **Who does what:**
   - the data team owns the feeds
   - credit officers own the cases
   - model risk reviews documented rules (not a model; the document module stays off)
   - IT security owns access and the audit log
7. **What hasn't been tested:**
   - It has never been connected to a real bank system.
   - All data is synthetic, except the public SEC data.
   - Postgres is not checked.
   - Scale has been measured once: 13.2M rows in 4.39 s on one laptop (`proof/scale.json`).

## Part 2: the file mapper

**What it does, step by step:**
1. **Reads the lender's file.** CSV works with what's installed. Excel (.xlsx) needs a library that isn't installed (decision 1).
2. **Suggests a mapping.** It matches the lender's column headers to ours by name, using a list of the names lenders actually use and the fuzzy matcher the checks already use. Examples:
   - "Days Past Due", "DPD" and "Delinquency Status" → days late
   - "Current Principal Balance" and "UPB" → balance

   Each column shows how sure the match is, and a person confirms it. Nothing is applied silently.
3. **Saves the confirmed mapping**, one small file per lender. Next month's file maps the same way. If the lender renames or drops a column, the mapper stops and asks rather than guessing.
4. **Converts values:**
   - dates → reporting month
   - days late → our late buckets (current, 30–59, 60–89, 90+)
   - "Y/N" or "Eligible/Ineligible" → yes/no
   - "$12,345.67" → a number
   - IDs are kept as text, so leading zeros survive
5. **Checks, before anything is written:**
   - every column the data-quality gate requires is mapped
   - cells that didn't convert: stop above 1% and list the rows
   - no loan appears twice in the same month
   - values in range: balance ≥ 0, credit score 300–850, days late ≥ 0
   - **the control total:** the mapped balances add up to the total on the borrower's borrowing-base certificate, which a person types in. This is the standard tie-out: within $1, or stop.
   - loans that appear or vanish since last month's file are reported (this doesn't block)
6. **Writes our tables, plus a mapping report** a person signs. The report covers:
   - what was mapped and what was dropped
   - every rejected row and why
   - the control-total tie-out
7. **Then the existing data-quality gate runs**, unchanged.

**Scope of the first version:** the spreadsheets borrowers send, which are the loan tape, the pledged invoices and the servicer extract (same shape as the tape). The other inputs come from bank systems or vendors with fixed layouts. Those are mapped once per bank, and `INTEGRATION.md` lists them.

**One code change it needs:** the data-quality gate assumes months 0 to 23, which is true only of our synthetic books. That range becomes the run's own calendar. On our books the results must not change: every recorded decision must replay identically.

## How it gets tested

- **Round trip on synthetic data.** A dev book's tape and invoices get written out as a "lender spreadsheet" with:
  - different column names
  - real dates
  - days late instead of buckets
  - "$1,234.56" text
  - Y/N flags
  - extra columns
  - 5 broken rows

  Mapped back, the checks must produce the same cases as the original book, and the report must list the 5 broken rows.
- **A real lender layout.** SEC ABS-EE is the loan-level format real auto lenders report in (22 lenders in our data). I'd map a sample of those real records using the mapper's suggestions alone, and report how many columns it got right without help. Caveat: real data, but a public-reporting format, not a borrowing-base spreadsheet.
- **Layout change.** Next month's file with a renamed column must stop with a clear message.
- **One test per check**, each with a near miss.

## What it won't do

- Read PDFs or scans (that's the document module, off by default).
- Guess silently. Every new layout needs a person to confirm the mapping once.
- Repair bad data. It rejects, reports, and the borrower resends.

## Decisions for Vedant

1. **Excel.** I recommend CSV now and .xlsx after your OK to install `openpyxl`, which would be logged in `~/Systemtools/TOOLS.md`. Most borrowing-base reports arrive as Excel, so a pilot needs it.
2. **Where it runs.** I recommend a command the bank's data team runs. An upload page in the console can come later: putting borrower files through a web page adds a security review.

## Order of work, after approval

1. `INTEGRATION.md`.
2. Mapper: read, suggest, confirm, mapping file.
3. Conversions, checks, the report.
4. The calendar change in the data-quality gate, with the replay check.
5. Tests, the round trip, the ABS-EE trial.
6. Then the document pass.
