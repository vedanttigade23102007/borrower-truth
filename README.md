# Borrower Truth

**Seven connected checks that answer one question for a lender: *is this borrower's picture of itself true?***

Built as an internship-application project for the Wells Fargo 2027 Technology Program. Not affiliated with Wells Fargo. **All data in this repository is synthetic.** No real company, person, vehicle or loan is represented.

---

## The problem, from primary sources

- Wells Fargo's largest commercial loan category is lending to non-bank financial firms: **$208.8B, 20% of all loans** at 30 Jun 2026, up from $191.1B six months earlier (10-Q).
- In Q1 2026 its charge-offs rose, "driven by a single fraud-related loss" (10-Q).
- Recent frauds against lenders in this market used several tricks at once, each hiding in a different place. The descriptions below are allegations from DOJ and SEC documents:
  - **Tricolor:** pledged ~$2.2B of collateral while holding ~$1.4B of real collateral; made defaulted loans "appear current".
  - **First Brands:** fake and inflated invoices, collateral pledged two and three times, hidden debt in related "James Entities", and loan money routed to look like customer receipts.
- Wells Fargo already backs one fix: Setpoint PledgeCheck checks the collateral *pool*. Nothing watches the *borrower around the pool*. That gap is what this project fills.

Every claim is matched against a saved source by `research/verify.py` (57 of 57 matched: 42 primary, 15 secondary). The claim table is `research/VERIFY.md`.

## What it does

| # | System | What it catches |
|---|---|---|
| S1 | Collateral integrity | Collateral pledged twice. Ingests the PledgeCheck result and matches VINs across Wells Fargo facilities; notes when a borrower isn't enrolled, so other lenders can't be checked |
| S2 | Tape vs source | Bad loans reported as good: missing payments, fake deferrals, impossible jumps, a servicer-system pull *targeted by the cash* (loans reported current that paid nothing), and credit scores rewritten after origination to clear the eligibility line |
| S3 | Cash provenance | Lender or affiliate money dressed up as customer payments. It checks *who* paid, not how much, and catches money sent out to a middleman that comes back as "customer" cash |
| S4 | Invoice authenticity | Re-submitted invoices with new amounts, unpaid invoices, impossible amounts, plus a document-reading model |
| S5 | Hidden-debt finder | Undisclosed liens and judgments, matched on names and addresses the way real lien registers work |
| S6 | Relationship mapper | Undisclosed linked companies and shells, linked by owner, address, phone number or registered agent, so a shell with a front person on the paperwork is still found |
| S7 | Financial consistency | Revenue that verified cash doesn't support; receivables piling up far faster than revenue; covenants that repeatedly just clear the line |

The systems feed each other. For example, S6 finds a shell, S5 finds a lien on it, and S3 sees that lender's money arriving as "customer" cash.

A **combiner** turns their signals into a *solved case*:
- the finding
- the evidence
- a verdict based on independent sources
- a suggested fix (a playbook per trick)
- drafted letters

A person approves every step. Nothing is sent or changed without approval.

Around the decision:
- **Decision record.** Every verdict carries fingerprints of its inputs, the rule code and the git commit. `bt.pipeline.replay` recomputes a run and either shows every decision is identical (120 of 120 on the demo run) or names the input or rule that changed.
- **Investigator agent** (`bt/agent/`). After the rules decide, an open model (Qwen3-8B / gpt-oss, open weights) investigates with read-only tools: registry, liens, courts, payments, disclosures, live GLEIF. It drafts a memo for the credit officer. Code enforces the guardrails: every line must cite a signal or a tool call, every number must appear in what it cites, and claims about what was disclosed or whether liens and judgments exist are checked against the records. Lines that fail are dropped and counted. The agent never decides.
- **Feedback loop, kept human.** Officers' approvals and rejections are counted per finding type (`/api/feedback`, Operations page). A type whose fixes keep getting rejected goes to the person who owns the rules; the rules never change themselves.
- **Public console** (`web/`): the review queue, each case with its fix, memo and decision record, a data section (dictionary, sample rows, one fraud step by step, invoice documents), and "Test it yourself", the answer key including misses.

## Proof: data it never saw

Rules were built on development books (seed 7 and seeds 101–105). The numbers below come from five fresh books generated and scored once, after every change was final (seeds 301–305: 600 borrowers, 190 with planted fraud, including 40 of two harder types, 410 honest with realistic look-alikes). Full report: `proof/REPORT.md`.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught | **99%** (189/190) | 41% (78/190) |
| Honest borrowers flagged "likely fraud" | 0 per 100 | 1.5 per 100 |
| Honest borrowers sent to "worth a look" | 30 per 100 (the real review workload) | – |
| Highest-priority 10% of the queue that are real frauds | 100% (60/60) | – |
| Suggested fixes that target a planted trick | 365 of 366 | – |
| Detection vs the audit (median) | **150 days earlier** | – |
| Frauds PledgeCheck's four checks never flagged | **146** | – |
| One monthly run, 120 borrowers | 0.86 s | – |

Every system loses detections when it is switched off, so each one earns its place.

**Before and after, same books:** the first version caught 143 of 150 on seeds 201–205; the current checks catch 146 of 150 on those same books (`proof/REPORT_v1_seeds201-205.md`, `proof/REPORT_seeds201-205_new_checks.md`). The old weakest check, dressed-up loan tapes (73%), is now 100% on the fresh books because the servicer pull is aimed by the cash.

**Weakest now:** financials that don't fit, 62 of 65. **The one miss** on 301–305: collateral pledged to a second lender, whose lien was filed under an abbreviated name ("Inds Grp L.L.C.") at the borrower's own address. S5 now expands filer abbreviations and falls back to the registered address. Because that fix came after seeing 301–305, it was tested on another five fresh books, scored once (seeds 306–310, `proof/REPORT_seeds306-310_after_s5_fix.md`): **190 of 190 caught**, audit 38%, 0 honest borrowers flagged at the end (2 of 410 were flagged in an earlier month and cleared), review load 25 per 100.

**A warning about near-perfect scores:** the frauds are ones I planted, so these numbers prove the checks cover the documented tricks. They don't predict a real-world catch rate.

**Honesty notes:**
- This is synthetic data, so the numbers prove *coverage of documented mechanisms*, not real-world catch rates.
- Zero hard false alarms reflects the honest noise we chose to simulate. Real books will be messier.

## Scale and reliability

| Rows | Seconds (one laptop, 8 GB) | Rows per second |
|---|---|---|
| 1.27M | 0.90 | 1.4M |
| 5.1M | 1.98 | 2.6M |
| 12.4M | 3.20 | 3.9M |

- **Partitioning:** work splits by borrower. Kafka is keyed by borrower, and the same SQL runs on DuckDB here or on Spark / BigQuery at bank scale.
- **Fault isolation:** every system runs isolated with a time budget. If one crashes, the case still builds and says which check was unavailable (`--fail S4` demonstrates this).
- **Messaging fallbacks:** the streaming worker is at-least-once, drops duplicates, and parks bad messages in a dead-letter queue.
- **Drafting fallbacks:** drafts fall back from the model to templates.
- **Delivery fallbacks:** if the case service is down, the pipeline parks the run and replays it later.

**Document model** (`proof/model/MODEL.md`): Donut fine-tuned on a free Kaggle T4, tested on 342 invoices from borrowers it never saw.
- It reads the **total correctly 96.5%** of the time, and all five fields 84.8%.
- It **caught all 11 tampered invoices**, with false flags on 3.3% of clean ones; every flag goes to a person to confirm.
- It reads 120 invoices per minute.
- The untrained base model scores 0%. That's a weak comparison (it can't produce the format without training), and is labelled as such.

**Real-time alerts reach the case, and only real ones go out** (`proof/STACK-DEMO.md`):
- A Kafka-to-Java bridge forwards streaming alerts to the case service.
- Only facts are streamed: money from a linked company or a lender.
- In the live run, **all 8 borrowers alerted were planted frauds**, and all 8 disguised-receipt frauds were alerted.

**Document check in S4** (`proof/model/MODEL.md`):
- On a book the model never saw, it caught **24 of 24 tampered invoices** with **2.9% false flags**.
- The second read helped only a little: false flags went from 17 to 15.

**Full stack, live in Codespaces** (`proof/STACK-DEMO.md`):
- 59,551 payments streamed through Kafka.
- A suspicious payer is flagged **24 ms after the payment arrives** (p50; p95 29 ms).
- 0 dead letters.
- The batch run takes 1.34 s.
- All services are healthy and reporting to Grafana.

## Architecture

```
synthetic book ─► Airflow (nightly) ─► S6 ─► S1 S2 S3 S4 S5 ─► S7 ─► combiner ─► Java case service ─► web console
bank payments ─► Kafka/Redpanda ─► streaming S3 worker ─────────────────────────┘        │
                                        Prometheus + Grafana ◄── metrics from every part ─┘
```

| Part | Tech | Where |
|---|---|---|
| Data generator, 7 systems, combiner, eval | Python 3.12, DuckDB | `bt/` |
| Case, verdict and fix service | Java 21, Spring Boot 4, H2 | `case-service/` |
| Review console | Next.js 16, React 19, Tailwind 4 | `web/` |
| Streaming | Kafka API (Redpanda), confluent-kafka | `bt/stream/` |
| Batch | Airflow | `airflow/dags/` |
| Monitoring | Prometheus, Pushgateway, Grafana | `ops/` |
| Document model | Donut, fine-tuned on Kaggle | `model/kaggle/` |
| Investigator agent | open models (Kaggle GPU or Hugging Face router) | `bt/agent/`, `model/kaggle_agent/` |

## Run it

```bash
uv sync --python 3.12
uv run python -m bt.datagen.generate --out data/out/demo      # synthetic book
uv run python -m bt.pipeline.run --data data/out/demo          # all seven checks + combiner
uv run python -m bt.eval.evaluate --seeds 201 202 203 204 205  # the proof
uv run python -m bt.pipeline.replay --data data/out/demo       # recompute every decision
uv run pytest -q                                               # 33 tests
```

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

**Full stack** (Codespaces, 16 GB):
```bash
export BT_API_KEY=$(openssl rand -hex 16)
docker compose -f ops/docker-compose.yml up -d
```
Grafana is on :3001. All ports are bound to localhost; the case service accepts writes from other machines only with `X-BT-Key`.

## Limits, said plainly
- Four of the seven systems need data that only a bank and its borrower hold. The demo proves the design and the detection logic; real accuracy needs real data.
- It recommends; people decide. It is not a credit engine.
- Fraud facts about named companies are allegations, quoted from DOJ/SEC documents. Nothing here suggests who Wells Fargo's Q1 2026 fraud-loss borrower was.
