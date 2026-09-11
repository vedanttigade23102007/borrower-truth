# Audit: design claims vs what is built

A line-by-line check of `design/SYSTEM-DESIGN.md` against the code. It was started because §14 said "Everything in §1–§13 is implemented", which was not true.

**Status key:**
- **built** — implemented and verified by a test or a run
- **partial** — some of the claim is built
- **not built** — claimed but missing
- **stale** — the doc describes something we changed

**Resolution key:**
- **→ fix** — being built now
- **→ doc** — the doc is being corrected, with the reason stated

**Baseline:** 13 Python tests, 4 Java tests and the TypeScript check all pass.

## The seven systems

| Claim | Status | Resolution |
|---|---|---|
| S1: PledgeCheck result, VIN-fingerprint uniqueness across WF facilities, identical invoices across facilities | built | — |
| S1: `PLEDGECHECK_ABSENT` signal | not built | → doc (it is coverage context, not evidence; it is shown via coverage) |
| S1: uniqueness across *linked entities'* facilities (S6→S1) | not built | → doc (the synthetic book has no WF facilities for linked shells) |
| S2: impossible transitions, source-system sampling, current-without-payment, deferment-without-programme | built | — |
| S2: `ELIGIBILITY_EDGE_CLUSTER`, attribute changes after origination, obligor confirmations | not built | → doc |
| S2→S1 re-check of mismatched assets | not built | → doc |
| S3: payer identity; related-party, lender and non-obligor payers | built | — |
| S3: `CIRCULAR_FLOW`, intermediary concentration | not built | → doc (needs outflow data the book doesn't have) |
| S4: altered, unpaid, implausible invoices | built | — |
| S4: document model reads invoice images | not built (model trained, not wired) | → fix: doc-vs-data check |
| S4: "Claude reads document images" | stale | → doc (it is the fine-tuned Donut) |
| S5: name + address lien matching, undisclosed/competing liens, judgments | built | — |
| S6: officer/address graph, shell indicators | built | — |
| S6: phone numbers, registered agents, "single counterparty" | not built | → doc |
| S6: real GLEIF data | not built (synthetic GLEIF-like table) | → fix: live GLEIF adapter with cache and stale fallback |
| S7: cash-revenue gap, covenant edge, debt gap, receivables quality | built | — |
| S7: receivables growth vs revenue growth | not built | → doc |

## Combiner and cases

| Claim | Status | Resolution |
|---|---|---|
| Independent-source confidence, facts, chaining through linked entities, verdicts, priority | built | — |
| Finding sentence written by an open model | not built (deterministic sentence) | → doc |
| Drafts written by an open model | partial (template drafts; a model hook with fallback exists, but no model service) | → doc |
| "Learn" loop: decisions become labels for re-tuning | not built | → doc |
| Hard escalations jump the queue | partial (facts force medium or higher) | → doc |
| Cases, playbooks, approvals, 409 on done-before-approve, audit, Prometheus | built | — |

## Architecture, fallbacks, operations

| Claim | Status | Resolution |
|---|---|---|
| Kafka streaming worker, dead-letter topic, dedupe, offsets | built (live run) | — |
| Stream alerts reach the case service | not built | → fix: signal bridge + live alerts on the case page |
| Airflow nightly job | partial (written, never run) | → fix: run it |
| Incremental processing / change data capture | not built (full recompute: 1.3 s for 120 borrowers) | → doc (designed for bank scale; not needed at demo scale) |
| Partitioned Parquet, worker pools | not built | → doc |
| Bad-file quarantine with last-good fallback | not built | → fix |
| Public-data cache with "stale since" flag | not built | → fix, together with the GLEIF adapter |
| Model fallback: base model → OCR + rules → human | partial (template fallback for drafts only) | → fix: S4 falls back to rules when document reads are missing |
| Model reads only rule-flagged documents; 4-bit | not built | → fix (flagged + sample); → doc (no quantization) |
| promptfoo faithfulness check | not built (no model-written text to check) | → doc |
| dbt | not built (optional) | → doc |
| Grafana dashboard | partial (queried via Prometheus, never looked at) | → fix: visual check |
| Console live mode against the Java service | partial (code only) | → fix: browser check |

## Proof

| Claim | Status | Resolution |
|---|---|---|
| Catch rate, switch-off test, beyond PledgeCheck, audit baseline, false alarms | built | — |
| Top-decile precision | not built | → fix |
| Fix quality: does the playbook address the planted mechanism? | not built | → fix |
| Alert → ready case file time | not built | → fix |
| Loan tapes calibrated on SEC ABS-EE data | not built | → doc |
| Fine-tuned vs base model | built (weak baseline, labelled) | — |
| Model section: LoRA/QLoRA, P100, CORD/FUNSD | stale | → doc (Donut full fine-tune on T4, synthetic invoices) |
