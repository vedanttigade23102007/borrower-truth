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
| S1 | Collateral integrity | Collateral pledged twice. Ingests the PledgeCheck result and matches VINs across Wells Fargo facilities |
| S2 | Tape vs source | Bad loans reported as good: missing payments, fake deferrals, impossible jumps, servicer-system sampling |
| S3 | Cash provenance | Lender or affiliate money dressed up as customer payments. It checks *who* paid, not how much |
| S4 | Invoice authenticity | Re-submitted invoices with new amounts, unpaid invoices, impossible amounts, plus a document-reading model |
| S5 | Hidden-debt finder | Undisclosed liens and judgments, matched on names and addresses the way real lien registers work |
| S6 | Relationship mapper | Undisclosed linked companies and shells |
| S7 | Financial consistency | Revenue that verified cash doesn't support; covenants that repeatedly just clear the line |

The systems feed each other. For example, S6 finds a shell, S5 finds a lien on it, and S3 sees that lender's money arriving as "customer" cash.

A **combiner** turns their signals into a *solved case*:
- the finding
- the evidence
- a verdict based on independent sources
- a suggested fix (a playbook per trick)
- drafted letters

A person approves every step. Nothing is sent or changed without approval.

## Proof: data it never saw

Rules were tuned on one synthetic book (seed 7). The numbers below come from five fresh books (seeds 201–205: 600 borrowers, 150 with planted fraud, 450 honest, including realistic honest look-alikes). Full report: `proof/REPORT.md`.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught | **95%** (143/150) | 47% (71/150) |
| Honest borrowers flagged "likely fraud" | 0 per 100 | 2.4 per 100 |
| Honest borrowers sent to "worth a look" | 31 per 100 (the real review workload) | – |
| Highest-priority 10% of the queue that are real frauds | 98% (59/60) | – |
| Suggested fixes that target a planted trick | 100% (294/294) | – |
| Detection vs the audit (median) | **120 days earlier** | – |
| Frauds PledgeCheck's four checks never flagged | **111** | – |
| One monthly run, 120 borrowers | 0.67 s | – |

Every system loses detections when it is switched off, so each one earns its place.

**Weakest mechanism:** dressed-up loan tapes, caught 73% of the time.

**Honesty notes:**
- This is synthetic data, so the numbers prove *coverage of documented mechanisms*, not real-world catch rates.
- Zero hard false alarms reflects the honest noise we chose to simulate. Real books will be messier.

## Scale and reliability

| Rows | Seconds (one laptop, 8 GB) | Rows per second |
|---|---|---|
| 1.25M | 0.51 | 2.5M |
| 5.0M | 1.31 | 3.9M |
| 12.4M | 2.30 | 5.4M |

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

## Run it

```bash
uv sync --python 3.12
uv run python -m bt.datagen.generate --out data/out/demo      # synthetic book
uv run python -m bt.pipeline.run --data data/out/demo          # all seven checks + combiner
uv run python -m bt.eval.evaluate --seeds 201 202 203 204 205  # the proof
uv run pytest -q                                               # 13 tests
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
docker compose -f ops/docker-compose.yml up -d
```
Grafana is on :3001.

## Limits, said plainly
- Four of the seven systems need data that only a bank and its borrower hold. The demo proves the design and the detection logic; real accuracy needs real data.
- It recommends; people decide. It is not a credit engine.
- Fraud facts about named companies are allegations, quoted from DOJ/SEC documents. Nothing here suggests who Wells Fargo's Q1 2026 fraud-loss borrower was.
