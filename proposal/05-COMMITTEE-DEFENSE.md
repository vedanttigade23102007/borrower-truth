# Committee defense: the hard questions, answered

## Metrics
- **"The 99% catch rate comes from synthetic test books. Why should we believe any of it?"**
  - The frauds are planted, so the catch rate proves coverage of the documented tricks, not a real-world rate. I say that first.
  - What is real: the five loan-tape checks were tested against 2.2M real loan records from 28 public pools, and none of those honest pools trips them. One design flagged 3 of them, so it was dropped.
  - What isn't yet: the other checks (collateral, cash, invoices, liens, relationships, financials) can't be tested on public data. The pilot tests them on the bank's own data.
  - The pilot exists to measure the real number.
- **"What does it cost my officers?"**
  - In the test, 29 of every 100 honest borrowers were sent to "worth a look". That is the real workload, and it is reported rather than hidden.
  - The top tenth of the queue was 60 of 60 real frauds, so working top-down spends time well.
  - The pilot measures officer-hours against a ceiling set up front.
- **"How much earlier?"**
  - A median of 90 days before a quarterly audit on the synthetic test (a design result).
  - The business case shows the break-even: moving one ~$8M exposure forward by 3 months pays for the pilot at a 3% monthly erosion assumption.

## Alternatives
- **"Why not just buy something?"**
  - Each vendor covers one or two of the seven places: Setpoint (collateral across lenders), Quantexa (relationships), lien-search vendors (liens). This layer uses them.
  - Setpoint's results already feed S1.
- **"Why not more field exams?"**
  - Sampling found 38% of planted frauds.
  - Use exams where this tool points, not instead of it.
- **"Why build it at all after an isolated incident?"**
  - The same tricks appeared at several lenders in 2025–26 (DOJ and SEC allegations).
  - A monthly run replaces a manual sweep after the fact.

## Failure scenarios
| If this happens | What contains it |
|---|---|
| Officers drown in alerts | Verdicts need independent sources; single statistical hints are "worth a look" only. A review-load ceiling is a kill criterion. |
| A feed arrives late or broken | Quarantine and last-good copy; each case says which checks didn't run. |
| A borrower learns the rules | Seven places at once, plus servicer pulls aimed by cash and by suspicious cures. Rules are private. |
| The LLM makes something up | It never decides. Code drops any memo line that cites nothing, invents a number, or contradicts the records. |
| A letter damages a relationship or tips off a borrower | Letters ask and never accuse. Compliance and Legal approve the templates. An officer approves each one. |
| A regulator challenges a decision | Every verdict replays from fingerprinted inputs, rules and code. |
| Key-person risk | Documented design, tests, a run-book, and a hand-over as part of phase 2. |
