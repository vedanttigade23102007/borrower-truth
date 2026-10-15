# Borrower Truth

**Seven connected checks that answer one question for a lender: *is this borrower's picture of itself true?***

Fraud monitoring for banks that lend to non-bank lenders: car lenders, invoice financiers and other finance companies. It's built for any bank, with Wells Fargo as the worked example, because its public filings show the problem clearly. Not affiliated with Wells Fargo. **It is a second pair of eyes next to covenants and field exams, not a fix for fraud.**

**All borrower data in this repository is synthetic.** No real company, person, vehicle or loan is represented in the test books. The one exception is `data/calibration/`: summaries measured from public SEC filings (loan-level ABS-EE data has no VIN and no borrower identity), used to make the synthetic loans behave like real ones and to check the loan-tape thresholds.

---

## The problem, from primary sources

- **Bank lending to non-bank lenders is large and concentrated.** Bank loans to nondepository financial institutions grew from $56 billion in early 2010 to $1.32 trillion in the third quarter of 2025, 10.0% of all bank loans. Banks with assets over $100 billion hold about 86% of them, and ten institutions about 71% (FDIC, *Banking Issues in Focus* no. 1, Feb 2026, pp. 2–3).
- **The worked example: Wells Fargo.**
  - Its largest commercial loan category is lending to non-bank financial firms: $208.8B, 20% of all its loans, at 30 Jun 2026 (10-Q).
  - In Q1 2026 its charge-offs rose, "driven by a single fraud-related loss" (10-Q). Nothing here suggests who that borrower was.
- **Recent frauds against lenders in this market used several tricks at once, each hiding in a different place.** The descriptions are allegations from SEC and DOJ documents:
  - **Tricolor** (SEC complaint, press release 2026-77): loans pledged to several securitizations and warehouse lines at once; "dead loans" reported as current; monthly servicing reports with altered delinquency fields, falsified VINs and adjusted payment terms; a hole of about $800M. The mapping to the checks is below.
  - **First Brands** (DOJ): fake and inflated invoices, collateral pledged two and three times, hidden debt in related "James Entities", and loan money routed to look like customer receipts.
- **One tool already guards the collateral pool.** Setpoint PledgeCheck, backed by Citi and Wells Fargo, checks the pool across lenders. No tool we found in public material (12 Sep 2026, `research/COMPETITORS.md`) joins what happens *around* the pool for one borrower.
- **Why now.** On 17 Apr 2026 the Fed, OCC and FDIC replaced the 2011 model-risk guidance: SR 26-2 replaced SR 11-7, and OCC Bulletin 2026-13 rescinded OCC Bulletin 2011-12.
  - It is guidance, not an enforceable standard. It is most relevant to banks over $30 billion in assets, and it leaves generative and agentic AI models out of scope.
  - Borrower Truth's verdicts come from written, replayable rules. Its AI agent only drafts memos and never decides.

**Sources:** research claims are matched against saved sources by `research/verify.py` (57 of 57 matched, re-run 14 Oct 2026; table: `research/VERIFY.md`). The FDIC report, the SEC Tricolor press release and complaint, the three papers below, SR 26-2 and OCC Bulletin 2026-13 were read at the source on 14 Oct 2026.

### Tricolor's techniques, as alleged, against the checks

From the SEC complaint (SEC v. Chu, Kollar and Seibold, SDNY 26-cv-7041; allegations). Gaps are stated, not hidden.

| Technique (complaint ¶) | What covers it | Honest gap |
|---|---|---|
| Loans pledged to more than one securitization and warehouse line (¶2–3) | S1: the same VIN in two of the bank's own facilities; PledgeCheck results for other lenders; overlap with the borrower's own *registered* public pools | Other lenders are visible only through PledgeCheck, which is simulated here. Tricolor's deals were private (Rule 144A, reported; `proof/REAL_DATA.md`), so no public loan data exists for them. |
| Delinquent "dead loans" reported as current (¶5) | S2: "current" loans with no payment in the bank's own receipts; servicer-system pulls; a paying loan's balance checked against those receipts | When the borrower services its own loans, it controls the servicer data too. The bank's own cash records are the anchor. |
| Monthly servicing reports with altered delinquency fields (¶7) | S2: tape against servicer pulls, impossible jumps, tape against the bank's receipts | Same as above. |
| Falsified VINs (¶7) | none | No VIN validity check yet. It is first on the after-outreach list (in the decision log, which is kept private). |
| Adjusted loan payment terms (¶7) | not checked | — |
| A hole of about $800M across all lenders (¶6) | S1, inside one bank only | Adding up one borrower's collateral across every lender needs a shared registry. |

## What it does

| # | System | What it catches |
|---|---|---|
| S1 | Collateral integrity | Collateral pledged twice. It reads the PledgeCheck result (simulated in the demo) and matches VINs across the bank's own facilities, and notes when a borrower isn't enrolled, so other lenders can't be checked |
| S2 | Tape vs source | Bad loans reported as good: missing payments, fake deferrals, impossible jumps, servicer-system pulls *aimed by the cash* (loans reported current that paid nothing), a paying loan's balance that rises, and credit scores rewritten after origination to clear the eligibility line |
| S3 | Cash provenance | Lender or affiliate money dressed up as customer payments. It checks *who* paid, not how much, and catches money sent out to a middleman that comes back as "customer" cash |
| S4 | Invoice authenticity | Re-submitted invoices with new amounts, unpaid invoices, impossible amounts. An optional document-reading model is off by default |
| S5 | Hidden-debt finder | Undisclosed liens and judgments, matched on names and addresses the way real lien registers work |
| S6 | Relationship mapper | Undisclosed linked companies and shells, linked by owner, address, phone number or registered agent, so a shell with a front person on the paperwork is still found |
| S7 | Financial consistency | Revenue that verified cash doesn't support; receivables piling up far faster than revenue; covenants that repeatedly just clear the line |

The systems feed each other. For example, S6 finds a shell, S5 finds a lien on it, and S3 sees that lender's money arriving as "customer" cash.

A **combiner** turns their clues into a *solved case*: the finding, the evidence, a verdict, a suggested fix (a playbook per trick) and drafted letters. **"Likely fraud" needs one checkable fact, or two independent sources about the same claim** (the same lender or linked company); unrelated clues never back each other up. Since change 32, a clue that names no lender (a judgment against the borrower itself, a PledgeCheck result, leaving PledgeCheck) can't be the second source for a claim about a lender. A person approves every step. Nothing is sent or changed without approval.

Around the decision:
- **Decision record.** Every verdict carries fingerprints of its inputs, the rule code and the git commit. `bt.pipeline.replay` recomputes a run and either shows every decision is identical (120 of 120 on the demo run) or names the input or rule that changed.
- **Investigator agent** (`bt/agent/`). After the rules decide, an open-weights model investigates with read-only tools (registry, liens, courts, payments, disclosures, GLEIF) and drafts a memo for the credit officer.
  - **Nothing leaves the bank by default** (`BT_OFFLINE`): it can only use a model already on the bank's own machines.
  - Code checks every line before it's shown. It must cite a clue or a tool call, and every number and company name in it must appear in what it cites. A claim that a named company was or wasn't disclosed, or that the borrower has no liens or judgments, is also compared with the records, but only when it's worded the way the check expects. Lines that fail are dropped and counted.
  - The check doesn't catch misreadings: money going the wrong way, numbers combined across sources, the borrower called its own related company, or a "no debts" or "no liens" claim worded another way. So every memo shown was also read line by line.
  - The agent never decides.
  - The demo's memos were written on 16 Sep 2026 (Qwen3-8B), 58 in all. On 14 Oct, 11 were hidden because they cite a clue that no longer exists or were written for a different verdict. On 14–15 Oct every line of the other 47 was read and compared with today's clues and records:
    - 33 had at least one false line: the borrower named as its own related company (20 memos), a wrong source (4), wrong or recombined numbers (3), a wrong "no liens" or "no debts" claim (3), money going the wrong way (2), another company's lien or collateral put on the borrower (2). One memo had two kinds. The first false line was enough to hide a memo, so these counts are a floor.
    - 2 more were hidden as misleading or unclear.
    - On 15 Oct one more (B0116) was hidden: change 32 lowered its double-pledge finding after the memo was written, and the memo's recorded lookup still shows the old confidence.
    - 11 are shown. The rules decide; a memo only drafts.
- **Feedback loop, kept human.** Officers' approvals and rejections are counted per finding type (`/api/feedback`, Operations page). A type whose fixes keep getting rejected goes to the person who owns the rules; the rules never change themselves.
- **Public console** (`web/`): the review queue, each case with its fix, memo and decision record, a data section (dictionary, sample rows, one fraud step by step, invoice documents), and "Test it yourself", the answer key including misses.

## Results: every run, never only the best one

**A warning first:** the frauds are ones we planted, so these numbers prove the checks cover the documented tricks. They don't predict a real-world catch rate. Rules were tuned only on development books (seeds 7 and 101–105). Each fresh set was generated for the first time and scored once.

### The current evaluation: seeds 1301–1305, on today's rules (`proof/REPORT_seeds1301-1305.md`)

**Held-out synthetic evaluation, seeds 1301–1305: 249 of 250 planted fraud cases were flagged by month 24 (99.6% on this synthetic test set). This is not a measurement of real-world fraud detection accuracy.** Scored once on 15 Oct 2026 under rule version `c147a0a636e6` (change 32), frozen first (tag `redteam-round3-noparty-fix`). 600 synthetic borrowers: 250 with planted fraud, 350 honest with realistic look-alikes. The report rounds that rate to a whole number; the exact figure is 99.6% (`proof/CORRECTIONS.md`).

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Planted fraud cases flagged by month 24 | **249 of 250** (99.6%) | 95 of 250 (38%) |
| Honest synthetic borrowers flagged "likely fraud" at month 24 | 0 of 350 | – |
| Honest synthetic borrowers flagged at least once, any month | 1 of 350 (B0054, months 21–22; also flagged under the previous rules) | 6 of 350 |
| Honest synthetic borrowers sent to "worth a look" | 107 of 350 (30.6 per 100: the real review workload) | – |
| Highest-priority 10% of the queue that are planted frauds | 60 of 60 | – |
| Suggested fixes that target a planted trick | 434 of 434 | – |
| Detection vs the audit (median, the 95 frauds both caught) | **90 days earlier** | – |
| Flagged frauds PledgeCheck's four checks never flagged | 213 of 249 | – |
| Lost when every SEC-based check is switched off | 40 of 249 | – |
| One monthly run, 120 borrowers | 1.19 s | – |

**The one not flagged:** B0042 on seed 1304, a borrower paying its own bad loans to look current, was sent to "worth a look", under the previous rules too.

**The honest borrower flagged at least once:** B0054 on seed 1305, in months 21–22 only. A few of its pledged loans match loans in its own public securitization, and those loans' payments went elsewhere for three months. The previous rules give the same result, so change 32 didn't cause it. Under the stopping rule decided before these runs, it is published as it came out and recorded as a known limit (below), not fixed.

**The previous rules' evaluation:** seeds 1201–1205 (`proof/REPORT_seeds1201-1205.md`, rule version `bfe7200495c4`, before change 32): 248 of 250 planted fraud cases flagged by month 24, 0 of 350 honest synthetic borrowers flagged at month 24 or in any month, 28.9 per 100 sent to review. `proof/REPORT.md` is now a copy of the current report (1301–1305), not this one.

### Every fresh run so far

| Seeds | What it tested | Frauds caught | Honest flagged at month 24 | Honest flagged in any month | Review per 100 honest |
|---|---|---|---|---|---|
| 201–205 | first rules (`REPORT_v1_seeds201-205.md`) | 143/150 | 0 of 450 | 0 | 31.3 |
| 301–305 | generator v2 (`REPORT_v2_seeds301-305.md`) | 189/190 | 0 of 410 | 0 | 30.5 |
| 306–310 | after an S5 fix | 190/190 | 0 of 410 | 2 | 25.1 |
| 401–405 | generator v3, first run | 247/250 | 0 of 350 | 2 | 33.4 |
| 406–410 | generator v3, final (`REPORT_seeds406-410.md`) | 248/250 | 0 of 350 | 0 | 29.1 |
| 501–505 | red team round 1's books | 246/249 | 0 of 351 | 0 | 25.6 |
| 601–605 | after the round-1 fixes | 246/250 | 0 of 350 | 0 | 30.3 |
| **701–705** | **round 2's books: failed** (a judgment matched by a name three companies share) | 249/250 | **1 of 350** | 1 | 28.3 |
| **801–805** | **after the round-2 fixes: failed** (a cut-off timing difference) | 249/250 | **1 of 350** | 1 | 30.9 |
| 901–905 | after the timing rule | 248/250 | 0 of 350 | 0 | 30.0 |
| 1001–1005 | round 3's books | 248/250 | 0 of 350 | 0 | 28.6 |
| 1101–1105 | after the round-3 fixes | 250/250 | 0 of 350 | 0 | 29.1 |
| 1201–1205 | after the claims fix (change 30) | 248/250 | 0 of 350 | 0 | 28.9 |
| **1301–1305** | **after change 32 (current rules): one honest borrower flagged in months 21–22** | 249/250 | 0 of 350 | **1** | 30.6 |

Each set was scored once under the rules of its day (`proof/REPORT_seeds*.md`). 201–205 was re-scored on 12 Sep after new checks were added (`REPORT_seeds201-205_new_checks.md`, 146/150); a re-score isn't a fresh run, so the table keeps the first one. The "any month" bar came later: 306–310 and 401–405 each had 2 honest borrowers flagged in some month, cleared by month 24. 1301–1305 had 1 (B0054, above), cleared by month 24.

**Pooled honest false alarms across all 14 sets:** 2 of 5,121 honest synthetic borrowers flagged at month 24 (0.04 per 100), and 7 of 5,121 flagged at least once (0.14 per 100). The rate measured is low, not zero; it is summed from the 14 reports in `proof/`.

### The blind red team: three rounds

**The lesson first (Vedant):** "monitoring built on the borrower's own data can't catch a borrower who controls that data, so the next step anchors on the bank's own cash records."

An AI attacker that hadn't seen the rules planted its own frauds into fresh books, and each round was scored once on frozen rules (`RED-TEAM-PLAN.md`). Counted: attacks gaining at least 5% of the borrower's credit limit.

| Round | Attacker | Blind result: caught / review / missed | After fixes (no longer blind) |
|---|---|---|---|
| 1 (seeds 501–505) | Claude Opus 5 | 19 / 21 / 40 of 80 (`proof/REDTEAM.md`) | 18 / 53 / 8 of 79 on 601–605 |
| 2 (seeds 701–705) | Claude Sonnet 5.5 | 42 / 17 / 11 of 70 (`proof/REDTEAM_round2.md`) | 39 / 31 / 0 on 801–805; 43 / 27 / 0 on 901–905 |
| 3 (seeds 1001–1005) | GPT-6 Astra (as shown in Codex), run by a friend with no internet | **0 / 28 / 32 of 60** (`proof/REDTEAM_round3.md`) | 18 / 42 / 0 on 1101–1105 and on 1201–1205; 20 / 40 / 0 on 1301–1305 |

**Caveats:**
- Rounds 1 and 2 used different Claude models (Opus 5, then Sonnet 5.5). Which is stronger wasn't measured, so the rounds aren't a clean comparison of the fixes.
- The rules of the test changed in between, in both directions. Credit limits were sized to each borrower's collateral, which made attacks harder to catch. The payer rule made them easier.
- Round 3 used a different company's model, with smaller attacks (6–8% of the limit, against 14–16%) and rules that had changed since round 2.
- Results "after fixes" are not blind: the fixes were made knowing the attacks. They show the fixes work on fresh books, not how a new attacker would do. The blind numbers remain the measure of each attacker.

### Real data: public SEC filings (`bt/sec/`, `proof/REAL_DATA.md`)

The frauds are planted, but the yardstick is real:
- **2.23M real loan records** from SEC Form ABS-EE: 28 public auto-loan pools of 22 lenders (Santander Drive, Exeter, Bridgecrest, AmeriCredit, Carvana, CarMax, Toyota, Honda and more), two consecutive months each.
- **Real filings** (8-K items, 10-K Exhibit 21, XBRL financials) of 24 public non-bank lenders.
- Honest auto loans in the test books move month to month by the measured rates, by credit band and loan age.
- **The six loan-tape checks were tested on every real pool, and none of the 28 honest pools trips any of them.** Those are current-without-payment, impossible jumps, late loans that never get later, the eligibility-line cluster, rewritten credit scores, and a paying loan's balance that rises. `tests/test_sec_calibration.py` fails if a threshold moves into the real range.
- The other checks (collateral, cash, invoices, liens, relationships, financials) can't be tested on public loan data, so their thresholds are still set on synthetic books.
- The real data rejected a design: an overall peer benchmark would have flagged 3 of 28 honest pools, so it was replaced.

### Evidence from others that the method works on real data

Borrower Truth's premise is that comparing what a borrower reports with independent records finds misreporting. Others have shown this on real loans (from the published abstracts, read 14 Oct 2026):
- **Piskorski, Seru and Witkin** (*Journal of Finance*, 2015) compared the mortgage details disclosed to investors with credit-bureau records. "About one out of every ten loans" was misrepresented, and those loans' delinquencies were "more than 60% higher" (NBER working paper w18843).
- **Griffin and Maturana** (*Review of Financial Studies*, 2016) found "around 48% of loans exhibited at least one indicator of misrepresentation", "associated with a 51% higher likelihood of delinquency".
- **Griffin and Priest** (*Journal of Finance*, 2023) found that underwritten income on commercial mortgage-backed loans "is commonly overstated relative to actual property income".

These are mortgage studies, not loans to non-bank lenders. They support the method, not these numbers.

## What Borrower Truth does not solve

For each: what the product does to help, and what stays outside any tool.

1. **Bank incentives and culture.**
   - **Helps:** puts the evidence in front of the officer, and every decision carries a real name. Clearing a "worth a look" check needs a written reason, and a second person checks a sample of clears.
   - **Outside any tool:** whether the bank acts on what it sees, and the pressure to keep a large client happy.
2. **Data the bank doesn't hold.**
   - **Helps:** a check missing an input says "not run" or "partial", so a missing file never looks clean (`DATA-CONTRACT.md`).
   - **Outside any tool:** other lenders' books, an operating account held at another bank, and private deals with no public data. A borrower that controls every record can pass (red team round 3).
3. **Officer headcount.**
   - **Helps:** ranks the queue; the highest-priority tenth was all real frauds in the tests.
   - **Outside any tool:** about 29 in every 100 honest borrowers still need a person's look. Someone has to do that work. Reducing it is on the after-outreach list.
4. **Legal and competitive limits on demanding data.**
   - **Helps:** works with what credit agreements usually give a lender already: tapes, audit rights, the collection account. Letters ask and never accuse.
   - **Outside any tool:** whether a bank can demand servicer access or ownership data, and whether a borrower agrees when a competing lender asks for less.
5. **Fraud that evolves.**
   - **Helps:** the rules are versioned and replayable, they were red-teamed three times, and every fix is scored once on fresh books.
   - **Outside any tool:** a trick nobody has documented yet. The blind round 3 caught none of its 60 attacks before the fixes.

## Known limits

- **Synthetic data.** Real accuracy needs real data; the pilot measures it.
- **A clue that names no counterparty can't back a claim about one** (change 32 in the decision log, kept private). A judgment records only the defendant, and PledgeCheck names no other lender, so a large judgment won by the same lender, or a PledgeCheck failure about the same pledge, doesn't corroborate a lien claim either. Such clues still corroborate each other, and still pool when no clue in the finding names a counterparty (the tape checks).
- **Leaving PledgeCheck while starting to pay a new lender is weaker evidence than before change 32.** The payments name the new lender; leaving PledgeCheck names no one, so it no longer counts as their second source. On the development books, 4 of round 1's double-pledge attacks went from "likely fraud" to "worth a look" (round 1: 16 / 67 / 12 caught / review / missed of 95, now 12 / 71 / 12), and 9 planted double pledges went from high to medium confidence without changing verdict. Letting registry results about the collateral corroborate claims about that collateral is on the after-outreach list.
- **An honest lender's own public securitization can look like a double pledge for a while:** if a few of its pledged loans also sit in its public trust and their payments go elsewhere, it is marked likely fraud until the pattern ends (B0054 on seed 1305, months 21–22).
- **Large judgments against honest borrowers aren't in the synthetic books:** the generator gives honest borrowers only small ones ($20k–$200k), so no fresh run tests that false alarm; tests do (`tests/test_combiner_claims.py`).
- **A nominee company** with no link to the owner in any table is a known limit.
- **No VIN validity check yet**, against the documented fake-VIN trick.
- **PledgeCheck is simulated.** Other lenders' pledges need the real service.
- **Four of the seven systems need data that only a bank and its borrower hold.** The demo proves the design and the detection logic.
- It recommends; people decide. It is not a credit engine.

## Scale and reliability

| Rows | Seconds (one laptop, 8 GB) | Rows per second |
|---|---|---|
| 1.29M | 1.05 | 1.2M |
| 5.3M | 2.66 | 2.0M |
| 13.2M | 4.39 | 3.0M |

Measured in `proof/scale.json`.
- **Partitioning:** work splits by borrower. The checks are SQL on DuckDB here. Running the same SQL in a bank's own warehouse is not tested.
- **Fault isolation:** every system runs isolated with a time budget. If one crashes, the case still builds and says which check was unavailable (`--fail S4` demonstrates this).
- **Missing or broken data:** a bad file is quarantined and the last good copy is used; a check missing an input says so.
- **Drafting:** letters come from templates. An in-house model service can be plugged in, with the templates as the fallback; none is configured by default.
- **Delivery fallbacks:** if the case service is down, the pipeline parks the run and replays it later.

**Streaming and the full stack were last run on 11 Sep 2026, on earlier rules (`proof/STACK-DEMO.md`)**, in GitHub Codespaces:
- 59,551 payments streamed through Kafka.
- A suspicious payer was flagged 24 ms after the payment arrived (p50; p95 29 ms).
- 0 dead letters.
- All 8 borrowers alerted in real time were planted frauds.
- The Airflow nightly job ran once with all 4 tasks succeeding (`proof/AUDIT.md`; no log was kept).

**Document model** (optional, off by default; `proof/model/MODEL.md`): Donut fine-tuned on a free Kaggle T4, tested on 342 invoices from borrowers it never saw.
- It reads the total correctly 96.5% of the time, and all five fields 84.8%.
- It caught all 11 tampered invoices, with false flags on 3.3% of clean ones. Every flag goes to a person.
- On a book it never saw, it caught 24 of 24 tampered invoices with 2.9% false flags.
- It was compared only with its untrained base model (0%), a weak baseline.

## Architecture

```
borrower files ─► mapper + data-quality gate ─► S6 ─► S1 S2 S3 S4 S5 ─► S7 ─► combiner ─► Java case service ─► web console
bank payments ─► (optional) Kafka ─► streaming S3 worker ─────────────────────────────────┘
```

The product is three parts: the checks, a case service that keeps decisions apart from the checks, and the officer's screen. **Kafka, Airflow and the Java case service fit the platform a bank already runs**, and each has a simpler option:

| Part | Tech | Simpler option | Where |
|---|---|---|---|
| Data generator, 7 systems, combiner, eval | Python 3.12, DuckDB | SQL in the bank's warehouse | `bt/` |
| Case, verdict and fix service | Java 21, Spring Boot 4, H2 | a small Python service | `case-service/` |
| Review console | Next.js 16, React 19, Tailwind 4 | screens served by the case service | `web/` |
| Streaming | Kafka API (Redpanda), confluent-kafka | S3 on each day's payment file | `bt/stream/` |
| Batch | Airflow | one scheduled script | `airflow/dags/` |
| Monitoring | Prometheus, Pushgateway, Grafana | the console's Operations page | `ops/` |
| Document model (optional) | Donut, fine-tuned on Kaggle | the rules alone (the default) | `model/kaggle/` |
| Investigator agent | open-weights models: a local model by default; hosted ones only with `BT_OFFLINE=0` | none: the findings' sentences | `bt/agent/`, `model/kaggle_agent/` |

## Run it

```bash
uv sync --python 3.12
uv run python -m bt.datagen.generate --out data/out/demo      # synthetic book
uv run python -m bt.pipeline.run --data data/out/demo          # all seven checks + combiner
uv run python -m bt.pipeline.replay --data data/out/demo       # recompute every decision
uv run pytest -q                                               # 147 Python tests
```

**Java tests:** `cd case-service && JAVA_HOME=<jdk21> ./gradlew test --rerun` (35 tests).

**A fresh held-out run**, scored once: freeze the rules (`bt.eval.redteam freeze`), push, then generate and score never-used seeds (`bt.eval.redteam plant` and `score`). The procedure and its stopping rule are in the decision log, which is kept private.

**Case service:**
```bash
cd case-service && JAVA_HOME=<jdk21> ./gradlew bootRun
```
Then publish a run with `uv run python -m bt.pipeline.publish`.

**Console:**
```bash
cd web && pnpm dev
```
Set `NEXT_PUBLIC_API_URL=http://localhost:8081` for live mode; without it the console reads the static snapshot.

**Full stack** (last run 11 Sep 2026, in Codespaces, 16 GB):
```bash
export BT_API_KEY=$(openssl rand -hex 16)
docker compose -f ops/docker-compose.yml up -d
```
Grafana is on :3001. All ports are bound to localhost; the case service accepts writes from other machines only with `X-BT-Key`.

## Proposal pack: how it would get approved at a bank (`proposal/`)

A one-page executive memo for a sponsor, a business case (requirements, resources, timeline, break-even, alternatives), a control-partner matrix (model risk under SR 26-2, BSA/AML compliance, legal, InfoSec, third-party risk, operational risk, audit), a 90-day shadow-pilot plan with success and kill criteria, and the committee's hard questions answered.

Fraud facts about named companies are allegations, quoted from SEC and DOJ documents. Nothing here suggests who Wells Fargo's Q1 2026 fraud-loss borrower was.
