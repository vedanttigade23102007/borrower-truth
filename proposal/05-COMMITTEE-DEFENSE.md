# Committee defense: the hard questions, answered

Numbers come from `proof/`. The latest fresh run is `proof/REPORT_seeds1201-1205.md`; every fresh run and red-team round is in the README.

## Metrics
- **"The 99% catch rate comes from synthetic test books. Why should we believe any of it?"**
  - The frauds are planted, so the catch rate proves coverage of the documented tricks, not a real-world rate. I say that first.
  - It isn't one lucky run. 13 fresh sets were each scored once. Two of them failed the bar (701–705 and 801–805, one honest borrower flagged each), and both are published. Across all 13: 2 of 4,771 honest borrowers flagged at month 24, and 6 in any month.
  - What is real: the six loan-tape checks were tested against 2.23M real loan records from 28 public pools, and none of those honest pools trips them. One design flagged 3 of them, so it was dropped.
  - Others have shown the method on real loans: comparing what was reported with independent records found misreporting in about one in ten mortgages (Piskorski, Seru and Witkin, 2015) and in around 48% on broader indicators (Griffin and Maturana, 2016).
  - What isn't yet: the other checks (collateral, cash, invoices, liens, relationships, financials) can't be tested on public data. The pilot tests them on the bank's own data.
- **"What does it cost my officers?"**
  - On the latest fresh run, 28.9 of every 100 honest borrowers were sent to "worth a look". That is the real workload, and it is reported rather than hidden.
  - The top tenth of the queue was 60 of 60 real frauds, so working top-down spends time well.
  - The pilot measures officer-hours against a ceiling set up front.
- **"How much earlier?"**
  - A median of 90 days before a quarterly audit on the synthetic test (a design result).
  - The business case shows the break-even: moving one ~$8M exposure forward by 3 months pays for the pilot at a 3% monthly erosion assumption.

## Alternatives
- **"Why not just buy something?"**
  - Each vendor covers one or two of the seven places: Setpoint (collateral across lenders), Quantexa (relationships), lien-search vendors (liens). This layer uses them.
  - Setpoint's results feed S1 (simulated in the prototype).
- **"Why not more field exams?"**
  - On the latest fresh run, a quarterly sample audit caught 37% of planted frauds (92 of 250).
  - Use exams where this tool points, not instead of them. It is a second pair of eyes next to covenants and field exams, not a replacement.
- **"Why build it at all after an isolated incident?"**
  - The same tricks appeared at several lenders in 2025–26 (SEC and DOJ allegations).
  - A monthly run replaces a manual sweep after the fact.

## The five things it does not solve (honest answers)
1. **"Our problem is incentives and culture, not tools."**
   - **True, and no tool fixes that.**
   - What it does: puts the evidence in front of the officer, and every decision carries a real name. Clearing a "worth a look" check needs a written reason, and a second person checks a sample of clears.
   - Whether the bank acts on what it sees, and the pressure to keep a large client, stay with the bank.
2. **"We don't have the data you need."**
   - Partly true.
   - What it does: a check missing an input says "not run" or "partial", so a missing file never looks clean. The data contract says what each check needs and what is lost without it.
   - What stays outside: other lenders' books, operating accounts at other banks, and private deals with no public data. In the blind red team, a borrower that controls all of its own records passed (round 3).
3. **"We don't have the officers to work another queue."**
   - What it does: ranks the queue, so the highest-priority tenth was all real frauds in the tests.
   - What stays outside: about 29 in every 100 honest borrowers still need a person's look. The pilot measures that against a ceiling, and a review load the team can't absorb is a kill criterion. Reducing it is on the after-outreach list.
4. **"We can't demand that data from borrowers; a competitor would ask for less."**
   - What it does: it works with what credit agreements usually give a lender already: tapes, audit rights, the collection account. Letters ask and never accuse.
   - What stays outside: whether a bank can demand servicer access or ownership data. Legal confirms it per facility, and the bank decides how hard to push a borrower that a competing lender would ask less of.
5. **"Fraud evolves. You'll always be one trick behind."**
   - True for any tool.
   - What it does: the rules are versioned and replayable, they were red-teamed three times, and every fix is scored once on fresh books.
   - What stays outside: a trick nobody has documented. The blind round 3 caught none of its 60 attacks at month 24; after the fixes, 18 were caught and 42 sent to review, but that re-score isn't blind.

## Failure scenarios
| If this happens | What contains it |
|---|---|
| Officers drown in alerts | "Likely fraud" needs one checkable fact or two independent sources about the same claim; a single weak clue is "worth a look" only. A review-load ceiling is a kill criterion. |
| A feed arrives late or broken | Quarantine and last-good copy; each case says which checks didn't run. |
| A borrower learns the rules | It can get past them. In the blind red team round 3, an attacker who controlled the borrower's own records had 0 of 60 attacks caught and 32 missed. The next step anchors on the bank's own cash records, and the rules stay private, but that is a limit, not a defence. |
| The LLM makes something up | It never decides. Code drops any memo line that cites nothing or invents a number. It can still misread a record: read by hand on 14–15 Oct, 33 of 47 demo memos had a false line, so a memo is a draft a person reads, and the rules decide. |
| A letter damages a relationship or tips off a borrower | Letters ask and never accuse. Compliance and Legal approve the templates. An officer approves each one. |
| A regulator challenges a decision | Every verdict replays from fingerprinted inputs, rules and code. |
| Key-person risk | Documented design, tests, a run-book, and a hand-over as part of phase 2. |
