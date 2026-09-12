# Audit: design claims vs what is built

A line-by-line check of `design/SYSTEM-DESIGN.md` against the code. It was started on 11 Sep 2026 because §14 said "Everything in §1–§13 is implemented", which was not true.

**Status key:**
- **built ✓** — implemented *and* verified by a test or a run named in the Evidence column
- **partial** — some of the claim is built
- **not built** — the design doc now says so
- **corrected** — the doc described something we changed

**Verification at close (12 Sep 2026):**
- 33 Python tests, 11 Java tests, the TypeScript check and lint pass.
- Held-out proof run once on 5 fresh books (seeds 301–305) after all detection changes, and on the original 5 for before/after. The one miss led to an S5 fix, which was then scored once on 5 more fresh books (306–310).
- Full stack re-run live in Codespaces: the Grafana dashboard rendered to an image, and payment-to-case latency measured.

## The seven systems

| Claim | Status | Evidence |
|---|---|---|
| S1: PledgeCheck result, VIN-fingerprint uniqueness across WF facilities, identical invoices across facilities | built ✓ | proof/REPORT.md (double pledge 44/45) |
| S1: `PLEDGECHECK_ABSENT` (coverage note) | **built ✓** (new) | shown on every unenrolled borrower's case as context ("can't verify other lenders"); never moves the verdict or the queue |
| S1: uniqueness across linked entities' facilities (S6→S1) | not built | the synthetic book has no WF facilities for linked shells |
| S2: impossible transitions, source-system sampling, current-without-payment, deferment-without-programme | built ✓ | the old weakest check (v1 held-out: 33/45) |
| S2: cash-targeted servicer pull (`TARGETED_SOURCE_MISMATCH`) | **built ✓** (new) | the weak spot fixed: a random 60-loan sample missed small dress-ups; pulling the loans the tape calls current but that paid nothing (same cost) catches them. Dev books 34/45 → 45/45, 0 of 450 honest borrowers hit. Held-out: REPORT.md |
| S2: credit-score rewrites after origination (`ATTRIBUTE_REWRITE`), `ELIGIBILITY_EDGE_CLUSTER` | **built ✓** (new) | the book now carries origination credit scores; dress-up borrowers lift sub-600 scores over the line, honest servicers make rare corrections. Dev books: rewrite found on 41 fraud borrowers and 0 honest; edge cluster 10 and 0. test_variants.py |
| S2: obligor confirmations, S2→S1 feed | not built | the book doesn't simulate obligors answering confirmation letters |
| S3: payer identity; related-party, lender and non-obligor payers | built ✓ | REPORT.md (disguised receipts 80/80) |
| S3 streaming: real-time payer check, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md (p50 24 ms; 8 of 8 alerted borrowers are frauds) |
| S3: `CIRCULAR_FLOW` (round trips through a middleman) | **built ✓** (new) | the book now has operating-account outflows. Money out to a company and back from it within 35 days, 3+ times, as payments that settle no invoice or loan. Honest look-alike (a customer that is also a supplier) caused 5 false alarms on the dev books until the check required unsettled payments; now 0. Dev round trips 20/20. test_variants.py |
| S3: intermediary concentration | not built | |
| S4: altered, unpaid, implausible invoices | built ✓ | REPORT.md (fake invoices 32/32) |
| S4: document model reads invoices; document-vs-data check with a second look | **built ✓** (was not wired) | MODEL.md (held-out book: 24/24 tampered caught, 2.9% false flags); falls back to rules without reads |
| S5: name + address lien matching, undisclosed/competing liens, judgments | built ✓ | REPORT.md (hidden debt 40/40) |
| S5: filer abbreviations and a registered-address fallback | **built ✓** (new) | the one miss on fresh books 301–305: a second lender's lien filed as "Ironwood Inds Grp L.L.C." at the borrower's own address. Abbreviations are now expanded and a filing at a company's exact registered address matches if the names broadly agree. Dev books unchanged (0 false alarms). Then scored once on new fresh books 306–310: 190/190 caught, audit 38%, 0 honest flagged at the end (2 of 410 flagged in an earlier month, then cleared). REPORT_seeds306-310_after_s5_fix.md; test_s5_matching.py |
| S6: officer/address graph, shell indicators | built ✓ | REPORT.md (shells 62/62) |
| S6: real GLEIF data | **built ✓** (adapter) | `bt/adapters/gleif.py`, run live: Wells Fargo & Company, LEI PBLD0EJDB5FWOLXP3B76, plus a subsidiary's parent chain. The synthetic book itself still uses a GLEIF-like table |
| S6: phone numbers, registered agents | **built ✓** (new) | nominee shells, registered to someone else at another address, are linked by the borrower's phone or the owner acting as registered agent; commercial agent services are ignored. Honest look-alikes (shared virtual office, owner as agent for an unrelated business) stay context. Dev nominee shells 20/20, 0 honest flagged. test_variants.py |
| S6: "single counterparty" | not built | |
| S7: cash-revenue gap, covenant edge, debt gap, receivables quality | built ✓ | REPORT.md |
| S7: receivables growth vs revenue growth (`RECEIVABLES_OUTPACE_REVENUE`) | **built ✓** (new, invoice borrowers only) | dev books: every invoice-fraud borrower at 3–33× its baseline, honest at most 1.3×. On loan books honest drift overlaps fraud, so it is deliberately not applied there |

## Combiner and cases

| Claim | Status | Evidence |
|---|---|---|
| Independent-source confidence, facts, chaining, verdicts, priority | built ✓ | top-decile precision 60/60; fixes on target 365/366 |
| Cases, playbooks, drafts, approvals, 409 before approval, audit, Prometheus | built ✓ | CaseFlowTest; browser approval stored server-side |
| Real-time alerts reach the case | **built ✓** (was not built) | signal bridge, `/api/live-alerts`, case page; CaseFlowTest; live run: 48 alerts forwarded |
| Finding sentences and drafts written by an open model | partial | the investigator agent's memo is model-written and checked line by line; letters and finding sentences stay templates (model hook with fallback exists) |
| Every decision replayable | **built ✓** (new) | `bt/pipeline/record.py`: each verdict carries input, rule and code fingerprints; `bt.pipeline.replay` on the demo run: 120 of 120 identical; test_replay.py (an edited input is named) |
| Investigator agent on an open model | **built ✓** (new) | `bt/agent/`: Qwen3-8B on a free Kaggle T4×2 (37 cases). Read-only tools; memo lines must cite a signal or tool call, every number must be in the cited source, and claims about disclosures and liens/judgments are checked against the records; the agent never decides; test_agent.py. Audit found and fixed: lien/court searches by ID instead of name, and false "undisclosed"/"no liens" lines slipping through. Checks re-applied to the saved output: 231 lines kept, the rest dropped with reasons shown on each case |
| Security review | **done ✓** (new) | no secrets in git history or the site; `pnpm audit` clean; site sends CSP, X-Frame-Options, nosniff, HSTS, Referrer-Policy; case service binds to localhost, writes from another machine need `X-BT-Key`, input sizes capped, actuator limited to health/info/metrics, CORS only for the console (SecurityTest.java). Not built: officer sign-in through a bank SSO |
| "Learn" loop from decisions | **built ✓** (kept human) | `/api/feedback` and the Operations page: approvals and rejections per finding type; a type with 30%+ rejections of 5+ decisions goes to the rules owner. Rules never change themselves (that would be an unvalidated model change). CaseFlowTest |
| Hard escalations jump the queue | **built ✓** | a high-confidence finding backed by a checkable fact sets priority to at least 0.95 |

## Architecture, fallbacks, operations

| Claim | Status | Evidence |
|---|---|---|
| Kafka streaming, offsets, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md |
| Airflow nightly job | **built ✓** (was written, never run) | `airflow dags test` in Codespaces: all 4 tasks SUCCESS (refresh → run seven checks → publish 120 cases → replay dead letters), 0 errors |
| Bad-file quarantine with last-good fallback | **built ✓** | test_fallbacks.py (schema break → last good copy, same verdicts) |
| Public-data cache with "stale since" | **built ✓** | test_fallbacks.py (source down → stale cache; no cache → clear error) |
| Isolated checks, time budget, break-it test | built ✓ | test_pipeline; STACK-DEMO break-it |
| Model fallback | partial | S4 falls back to rules; drafts fall back to templates; no base-model tier |
| Incremental processing, partitioned Parquet, autoscaled worker pools | not built (deliberate) | a full monthly run of 12.4M rows takes 2.3 s on one laptop; partitioning pays off beyond one machine and would complicate the data-quality gate for no gain here |
| Model reads flagged docs only; 4-bit quantization | not built | the demo reads a per-borrower sample in fp16 |
| promptfoo faithfulness check; dbt | not built | promptfoo would be a new install (not approved). Its job, checking model-written text against sources, is done in code by the agent's memo checks; dbt optional |
| Grafana dashboard | **built ✓** | rendered to an image by Grafana's own image renderer in Codespaces: [grafana-dashboard.png](grafana-dashboard.png); every panel draws data (STACK-DEMO.md, 12 Sep) |
| Console live mode against the Java service | **built ✓** | browser: live alerts shown; Approve stored server-side with audit |
| Console public deployment, data section, answer key | **built ✓** (new) | /data (dictionary + 10 sample rows per input, one fraud step by step, invoice documents), /test (answer key with misses, held-out results); samples only, no code, full data, rules or weights published |

## Proof

| Claim | Status | Evidence |
|---|---|---|
| Catch rate, switch-off test, beyond PledgeCheck, audit baseline, false alarms | built ✓ | REPORT.md (fresh books 301–305): 189/190 (99%) vs 41% for the audit; 0 false alarms; review load 30.5/100. Same new code on the original books 201–205: 146/150 (97%, was 95%). v1 report kept as REPORT_v1_seeds201-205.md |
| Top-decile precision, fix quality | **built ✓** | 60/60; 365/366 |
| Fresh held-out books | **built ✓** | seeds 301–305 generated and scored after every change was final. Seeds 301 and 302 were first created by the older generator when a run was stopped mid-way; they were regenerated and all five re-scored, with no code change in between |
| Alert → ready case file time | **built ✓** | payment into Kafka → alert visible on the officer's case: p50 1.50 s, max 1.54 s over 10 tagged payments (STACK-DEMO.md); batch monthly run in under 1.5 s |
| Loan tapes calibrated on SEC ABS-EE | not built | SEC's EDGAR requires a contact email in every automated request; I won't send your email without your OK |
| Fine-tuned vs base model | built ✓ | weak baseline, labelled |
| Model section: LoRA, P100, CORD/FUNSD | corrected | Donut full fine-tune on T4, synthetic invoices |
