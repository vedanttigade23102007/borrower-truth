# Audit: design claims vs what is built

A line-by-line check of `design/SYSTEM-DESIGN.md` against the code. It was started on 11 Sep 2026 because §14 said "Everything in §1–§13 is implemented", which was not true.

**Status key:**
- **built ✓** — implemented *and* verified by a test or a run named in the Evidence column
- **partial** — some of the claim is built
- **not built** — the design doc now says so
- **corrected** — the doc described something we changed

**Verification at close:**
- 19 Python tests, 7 Java tests and the TypeScript check pass.
- Held-out proof re-run on 5 books.
- Full stack re-run live in Codespaces.

## The seven systems

| Claim | Status | Evidence |
|---|---|---|
| S1: PledgeCheck result, VIN-fingerprint uniqueness across WF facilities, identical invoices across facilities | built ✓ | proof/REPORT.md (double pledge 44/45) |
| S1: `PLEDGECHECK_ABSENT`; uniqueness across linked entities' facilities (S6→S1) | not built | the synthetic book has no WF facilities for linked shells; absence is shown as coverage context |
| S2: impossible transitions, source-system sampling, current-without-payment, deferment-without-programme | built ✓ | REPORT.md (tape dressing 33/45; the weakest check) |
| S2: `ELIGIBILITY_EDGE_CLUSTER`, attribute changes after origination, obligor confirmations, S2→S1 feed | not built | doc corrected |
| S3: payer identity; related-party, lender and non-obligor payers | built ✓ | REPORT.md (disguised receipts 40/40) |
| S3 streaming: real-time payer check, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md (p50 24 ms; 8 of 8 alerted borrowers are frauds) |
| S3: `CIRCULAR_FLOW`, intermediary concentration | not built | needs outflow data the book lacks |
| S4: altered, unpaid, implausible invoices | built ✓ | REPORT.md (fake invoices 33/33) |
| S4: document model reads invoices; document-vs-data check with a second look | **built ✓** (was not wired) | MODEL.md (held-out book: 24/24 tampered caught, 2.9% false flags); falls back to rules without reads |
| S5: name + address lien matching, undisclosed/competing liens, judgments | built ✓ | REPORT.md (hidden debt 40/40) |
| S6: officer/address graph, shell indicators | built ✓ | REPORT.md (shells 45/45) |
| S6: real GLEIF data | **built ✓** (adapter) | `bt/adapters/gleif.py`, run live: Wells Fargo & Company, LEI PBLD0EJDB5FWOLXP3B76, plus a subsidiary's parent chain. The synthetic book itself still uses a GLEIF-like table |
| S6: phone numbers, registered agents, "single counterparty" | not built | doc corrected |
| S7: cash-revenue gap, covenant edge, debt gap, receivables quality | built ✓ | REPORT.md (financials 59/65) |
| S7: receivables growth vs revenue growth | not built | doc corrected |

## Combiner and cases

| Claim | Status | Evidence |
|---|---|---|
| Independent-source confidence, facts, chaining, verdicts, priority | built ✓ | top-decile precision 98%; fixes on target 294/294 |
| Cases, playbooks, drafts, approvals, 409 before approval, audit, Prometheus | built ✓ | CaseFlowTest; browser approval stored server-side |
| Real-time alerts reach the case | **built ✓** (was not built) | signal bridge, `/api/live-alerts`, case page; CaseFlowTest; live run: 48 alerts forwarded |
| Finding sentences and drafts written by an open model | not built | template sentences and drafts; model hook with fallback exists |
| Every decision replayable | **built ✓** (new) | `bt/pipeline/record.py`: each verdict carries input, rule and code fingerprints; `bt.pipeline.replay` on the demo run: 120 of 120 identical; test_replay.py (an edited input is named) |
| Investigator agent on an open model | **built ✓** (new) | `bt/agent/`: Qwen3-8B on a free Kaggle T4×2 (37 cases). Read-only tools; memo lines must cite a signal or tool call, every number must be in the cited source, and claims about disclosures and liens/judgments are checked against the records; the agent never decides; test_agent.py. Audit found and fixed: lien/court searches by ID instead of name, and false "undisclosed"/"no liens" lines slipping through. Checks re-applied to the saved output: 231 lines kept, the rest dropped with reasons shown on each case |
| Security review | **done ✓** (new) | no secrets in git history or the site; `pnpm audit` clean; site sends CSP, X-Frame-Options, nosniff, HSTS, Referrer-Policy; case service binds to localhost, writes from another machine need `X-BT-Key`, input sizes capped, actuator limited to health/info/metrics, CORS only for the console (SecurityTest.java). Not built: officer sign-in through a bank SSO |
| "Learn" loop from decisions | not built | doc corrected |
| Hard escalations jump the queue | partial | facts force medium or higher |

## Architecture, fallbacks, operations

| Claim | Status | Evidence |
|---|---|---|
| Kafka streaming, offsets, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md |
| Airflow nightly job | **built ✓** (was written, never run) | `airflow dags test` in Codespaces: all 4 tasks SUCCESS (refresh → run seven checks → publish 120 cases → replay dead letters), 0 errors |
| Bad-file quarantine with last-good fallback | **built ✓** | test_fallbacks.py (schema break → last good copy, same verdicts) |
| Public-data cache with "stale since" | **built ✓** | test_fallbacks.py (source down → stale cache; no cache → clear error) |
| Isolated checks, time budget, break-it test | built ✓ | test_pipeline; STACK-DEMO break-it |
| Model fallback | partial | S4 falls back to rules; drafts fall back to templates; no base-model tier |
| Incremental processing, partitioned Parquet, autoscaled worker pools | not built | doc labels them "designed, not built" |
| Model reads flagged docs only; 4-bit quantization | not built | the demo reads a per-borrower sample in fp16 |
| promptfoo faithfulness check; dbt | not built | no model-written text to check; dbt optional |
| Grafana dashboard | partial | provisioned; the data path is verified through Grafana's own query API. Visual rendering was not confirmed by me (the preview pane was hidden, so Grafana didn't draw) |
| Console live mode against the Java service | **built ✓** | browser: live alerts shown; Approve stored server-side with audit |
| Console public deployment, data section, answer key | **built ✓** (new) | /data (dictionary + 10 sample rows per input, one fraud step by step, invoice documents), /test (answer key with misses, held-out results); samples only, no code, full data, rules or weights published |

## Proof

| Claim | Status | Evidence |
|---|---|---|
| Catch rate, switch-off test, beyond PledgeCheck, audit baseline, false alarms | built ✓ | REPORT.md: 95% vs 47%; 0 false alarms; review load 31/100 |
| Top-decile precision, fix quality | **built ✓** | 98% (59/60); 294/294 |
| Alert → ready case file time | partial | batch 0.73 s per monthly run; streaming 24 ms to alert; drafting time not measured separately |
| Loan tapes calibrated on SEC ABS-EE | not built | doc corrected |
| Fine-tuned vs base model | built ✓ | weak baseline, labelled |
| Model section: LoRA, P100, CORD/FUNSD | corrected | Donut full fine-tune on T4, synthetic invoices |
