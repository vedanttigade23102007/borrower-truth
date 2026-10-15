# Audit: design claims vs what is built

A line-by-line check of `design/SYSTEM-DESIGN.md` against the code. It was started on 11 Sep 2026 because §14 said "Everything in §1–§13 is implemented", which was not true.

**Status on 15 Oct 2026** (this audit was written 11–14 Sep; its numbers are kept as history):
- 147 Python tests and 35 Java tests pass.
- The current evaluation is held-out synthetic seeds 1301–1305 (`REPORT_seeds1301-1305.md`), scored once under rule version `c147a0a636e6`: 249 of 250 planted fraud cases flagged by month 24 (99.6% on this synthetic test set; not a measurement of real-world fraud detection accuracy; the report rounds it, see `CORRECTIONS.md`); honest synthetic borrowers 0 of 350 flagged at month 24, 1 of 350 at least once (B0054, months 21–22, also under the previous rules); 30.6 per 100 to review. Across 14 sets: 2 of 5,121 flagged at month 24, 7 of 5,121 at least once.
- The previous rules' evaluation is seeds 1201–1205 (`REPORT_seeds1201-1205.md`, also copied to `REPORT.md`, kept as published): 248 of 250, 0 of 350 honest flagged, 28.9 per 100 to review. Every fresh run, the pooled false-alarm rate and the three blind red-team rounds are in the README.
- The 406–410 report cited below as the evidence of the day is now `REPORT_seeds406-410.md`.
- Kafka, Prometheus, Grafana, Airflow and the full stack were last run on 11–12 Sep 2026, on earlier rules (`STACK-DEMO.md`). They have not been re-run since.

**Status key:**
- **built ✓** — implemented *and* verified by a test or a run named in the Evidence column
- **partial** — some of the claim is built
- **not built** — the design doc now says so
- **corrected** — the doc described something we changed

**Verification after the real-data build (14 Sep 2026):** 41 Python tests pass; generator v3 calibrated on real SEC data; held-out proof run once on fresh seeds 406–410 (REPORT_seeds406-410.md); every S2 threshold checked against 28 real pools (REAL_DATA.md, tests/test_sec_calibration.py).

**Verification at close (12 Sep 2026):**
- 33 Python tests, 11 Java tests, the TypeScript check and lint pass.
- Held-out proof run once on 5 fresh books (seeds 301–305) after all detection changes, and on the original 5 for before/after. The one miss led to an S5 fix, which was then scored once on 5 more fresh books (306–310).
- Full stack re-run live in Codespaces: the Grafana dashboard rendered to an image, and payment-to-case latency measured.

## The seven systems

| Claim | Status | Evidence |
|---|---|---|
| S1: PledgeCheck result, VIN-fingerprint uniqueness across WF facilities, identical invoices across facilities | built ✓ | proof/REPORT.md (double pledge 65/65) |
| S1: `PLEDGECHECK_ABSENT` (coverage note) | **built ✓** (new) | shown on every unenrolled borrower's case as context ("can't verify other lenders"); never moves the verdict or the queue |
| S1: uniqueness across linked entities' facilities (S6→S1) | not built | the synthetic book has no WF facilities for linked shells |
| S2: impossible transitions, source-system sampling, current-without-payment, deferment-without-programme | built ✓ | the old weakest check (v1 held-out: 33/45) |
| S2: cash-targeted servicer pull (`TARGETED_SOURCE_MISMATCH`) | **built ✓** (new) | the weak spot fixed: a random 60-loan sample missed small dress-ups; pulling the loans the tape calls current but that paid nothing (same cost) catches them. Dev books 34/45 → 45/45, 0 of 450 honest borrowers hit. Held-out: REPORT_seeds406-410.md |
| S2: credit-score rewrites after origination (`ATTRIBUTE_REWRITE`), `ELIGIBILITY_EDGE_CLUSTER` | **built ✓** (new) | the book now carries origination credit scores; dress-up borrowers lift sub-600 scores over the line, honest servicers make rare corrections. Dev books: rewrite found on 41 fraud borrowers and 0 honest; edge cluster 10 and 0. test_variants.py |
| S2: obligor confirmations, S2→S1 feed | not built | the book doesn't simulate obligors answering confirmation letters |
| S3: payer identity; related-party, lender and non-obligor payers | built ✓ | REPORT_seeds406-410.md (disguised receipts 80/80) |
| S3 streaming: real-time payer check, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md (p50 24 ms; 8 of 8 alerted borrowers are frauds) |
| S3: `CIRCULAR_FLOW` (round trips through a middleman) | **built ✓** (new) | the book now has operating-account outflows. Money out to a company and back from it within 35 days, 3+ times, as payments that settle no invoice or loan. Honest look-alike (a customer that is also a supplier) caused 5 false alarms on the dev books until the check required unsettled payments; now 0. Dev round trips 20/20. test_variants.py |
| S3: intermediary concentration | not built | |
| S4: altered, unpaid, implausible invoices | built ✓ | REPORT_seeds406-410.md (fake invoices 34/34) |
| S4: document model reads invoices; document-vs-data check with a second look | **built ✓** (was not wired) | MODEL.md (held-out book: 24/24 tampered caught, 2.9% false flags); falls back to rules without reads |
| S5: name + address lien matching, undisclosed/competing liens, judgments | built ✓ | REPORT_seeds406-410.md (hidden debt 60/60) |
| S5: filer abbreviations and a registered-address fallback | **built ✓** (new) | the one miss on fresh books 301–305: a second lender's lien filed as "Ironwood Inds Grp L.L.C." at the borrower's own address. Abbreviations are now expanded and a filing at a company's exact registered address matches if the names broadly agree. Dev books unchanged (0 false alarms). Then scored once on new fresh books 306–310: 190/190 caught, audit 38%, 0 honest flagged at the end (2 of 410 flagged in an earlier month, then cleared). REPORT_seeds306-310_after_s5_fix.md; test_s5_matching.py |
| S6: officer/address graph, shell indicators | built ✓ | REPORT_seeds406-410.md (shells 64/65) |
| S6: real GLEIF data | **built ✓** (adapter) | `bt/adapters/gleif.py`, run live: Wells Fargo & Company, LEI PBLD0EJDB5FWOLXP3B76, plus a subsidiary's parent chain. The synthetic book itself still uses a GLEIF-like table |
| S6: phone numbers, registered agents | **built ✓** (new) | nominee shells, registered to someone else at another address, are linked by the borrower's phone or the owner acting as registered agent; commercial agent services are ignored. Honest look-alikes (shared virtual office, owner as agent for an unrelated business) stay context. Dev nominee shells 20/20, 0 honest flagged. test_variants.py |
| S6: "single counterparty" | not built | |
| S7: cash-revenue gap, covenant edge, debt gap, receivables quality | built ✓ | REPORT_seeds406-410.md |
| S7: receivables growth vs revenue growth (`RECEIVABLES_OUTPACE_REVENUE`) | **built ✓** (new, invoice borrowers only) | dev books: every invoice-fraud borrower at 3–33× its baseline, honest at most 1.3×. On loan books honest drift overlaps fraud, so it is deliberately not applied there |

## Combiner and cases

| Claim | Status | Evidence |
|---|---|---|
| Independent-source confidence, facts, chaining, verdicts, priority | built ✓ | top-decile precision 60/60; fixes on target 430/430 (fresh v3 books 406–410) |
| Cases, playbooks, drafts, approvals, 409 before approval, audit, Prometheus | built ✓ | CaseFlowTest; browser approval stored server-side |
| Real-time alerts reach the case | **built ✓** (was not built) | signal bridge, `/api/live-alerts`, case page; CaseFlowTest; live run: 48 alerts forwarded |
| Finding sentences and drafts written by an open model | partial | the investigator agent's memo is model-written; code checks its citations, numbers and names, and a read by hand on 14–15 Oct hid 35 of 47 memos for a false or misleading line, and one more was hidden when the rules changed on 15 Oct (11 shown); letters and finding sentences stay templates (model hook with fallback exists) |
| Every decision replayable | **built ✓** (new) | `bt/pipeline/record.py`: each verdict carries input, rule and code fingerprints; `bt.pipeline.replay` on the demo run: 120 of 120 identical; test_replay.py (an edited input is named) |
| Investigator agent on an open model | **built ✓** (new) | `bt/agent/`: Qwen3-8B on a free Kaggle T4×2, 58 cases on the v3 demo book, every likely-fraud case covered. Read-only tools; memo lines must cite a signal or tool call, every number must be in the cited source, and claims about disclosures and liens/judgments are compared with the records only when they name the company or use wording the check knows; misreadings are not caught (read by hand on 14–15 Oct: of the 47 memos still shown then, 33 had at least one false line; 36 are now hidden and 11 shown); the agent never decides; test_agent.py. Audit found and fixed: lien/court searches by ID instead of name, and false "undisclosed"/"no liens" lines slipping through. Latest run (16 Sep, v3 demo book): 349 lines kept, 57 dropped, with reasons shown on each case. The earlier limit is closed: the model never called the outgoing-payments tool however the prompt asked, so the harness now runs it for every flagged payer and hands over the result as a normal, citable tool call. The round-trip case's memo now states the money out and the money back ($64,048 sent, $63,574 returned) |
| Security review | **done ✓** (new) | no secrets in git history or the site; `pnpm audit` clean; site sends CSP, X-Frame-Options, nosniff, HSTS, Referrer-Policy; case service binds to localhost, writes from another machine need `X-BT-Key`, input sizes capped, actuator limited to health/info/metrics, CORS only for the console (SecurityTest.java). Not built: officer sign-in through a bank SSO |
| "Learn" loop from decisions | **built ✓** (kept human) | `/api/feedback` and the Operations page: approvals and rejections per finding type; a type with 30%+ rejections of 5+ decisions goes to the rules owner. Rules never change themselves (that would be an unvalidated model change). CaseFlowTest |
| Hard escalations jump the queue | **built ✓** | a high-confidence finding backed by a checkable fact sets priority to at least 0.95 |

## Architecture, fallbacks, operations

| Claim | Status | Evidence |
|---|---|---|
| Kafka streaming, offsets, dedupe, dead-letter queue | built ✓ | STACK-DEMO.md |
| Airflow nightly job | **built ✓** (was written, never run) | `airflow dags test` in Codespaces, 11 Sep 2026: all 4 tasks SUCCESS (refresh → run seven checks → publish 120 cases → replay dead letters), 0 errors. No log was saved; this line is the only record |
| Bad-file quarantine with last-good fallback | **built ✓** | test_fallbacks.py (schema break → last good copy, same verdicts) |
| Public-data cache with "stale since" | **built ✓** | test_fallbacks.py (source down → stale cache; no cache → clear error) |
| Isolated checks, time budget, break-it test | built ✓ | test_pipeline; STACK-DEMO break-it |
| Model fallback | partial | S4 falls back to rules; drafts fall back to templates; no base-model tier |
| Incremental processing, partitioned Parquet, autoscaled worker pools | not built (deliberate) | a full monthly run of 13.2M rows takes 4.4 s on one laptop; partitioning pays off beyond one machine and would complicate the data-quality gate for no gain here |
| Model reads flagged docs only; 4-bit quantization | not built | the demo reads a per-borrower sample in fp16 |
| promptfoo faithfulness check; dbt | not built | promptfoo would be a new install (not approved). Part of its job, checking that model-written text cites real sources and numbers, is done in code by the agent's memo checks; misreadings are not caught (read by hand, 14–15 Oct); dbt optional |
| Grafana dashboard | **built ✓** | rendered to an image by Grafana's own image renderer in Codespaces: [grafana-dashboard.png](grafana-dashboard.png); every panel draws data (STACK-DEMO.md, 12 Sep) |
| Console live mode against the Java service | **built ✓** | browser: live alerts shown; Approve stored server-side with audit |
| Console public deployment, data section, answer key | **built ✓** (new) | /data (dictionary + 10 sample rows per input, one fraud step by step, invoice documents), /test (answer key with misses, held-out results); samples only, no code, full data, rules or weights published |

## Proof

| Claim | Status | Evidence |
|---|---|---|
| Catch rate, switch-off test, beyond PledgeCheck, audit baseline, false alarms | built ✓ | REPORT_seeds406-410.md (fresh v3 books 406–410): 248/250 (99%) vs 38% for the audit; 0 of 350 honest flagged in any month; review load 29.1/100; SEC-based checks off: 41 lost. Earlier reports kept: v1 (201–205), v2 (301–305: 189/190), v3 first run (401–405: 247/250) |
| Top-decile precision, fix quality | **built ✓** | 60/60; 430/430 |
| Fresh held-out books | **built ✓** | seeds 406–410 generated and scored once after every change was final (14 Sep). 401–405 were scored once before a generator change (v3 auto loans moved to their own random stream) and are kept as history, not re-used |
| Alert → ready case file time | **built ✓** | payment into Kafka → alert visible on the officer's case: p50 1.50 s, max 1.54 s over 10 tagged payments (STACK-DEMO.md); batch monthly run in under 1.5 s |
| Loan tapes calibrated on SEC ABS-EE | **built ✓** (14 Sep) | 56 ABS-EE files, 28 public auto pools, 22 lenders, 2.23M loan rows (contact email approved by Vedant). Honest auto loans in generator v3 move by the measured rates; every S2 threshold checked against every real pool: 0 of 28 flagged; a rejected level benchmark flagged 3 of 28 (REAL_DATA.md) |
| SEC filings cross-check (10-K debt, 8-K 2.03/2.04, Exhibit 21, XBRL revenue) | **built ✓** (14 Sep) | FILED_DEBT_UNDISCLOSED, FILED_VS_REPORTED, Exhibit 21 links, 8-K 2.04 context; real 8-K/Ex21/XBRL pulled for 24 public non-bank lenders (58 new-debt 8-Ks in 12 months, so an 8-K alone is never a clue) |
| Same loans in a public trust and on the bank's tape | **built ✓** (14 Sep) | PUBLIC_POOL_OVERLAP (no-VIN fingerprint, 99.99% unique on 787,944 real loans) + POOL_LOANS_PAID_ELSEWHERE (fact) |
| Fine-tuned vs base model | built ✓ | weak baseline, labelled |
| Model section: LoRA, P100, CORD/FUNSD | corrected | Donut full fine-tune on T4, synthetic invoices |
