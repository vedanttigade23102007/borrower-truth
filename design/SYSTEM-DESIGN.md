# Borrower-truth system: design

**Problem:** Wells Fargo's largest commercial loan category is loans to non-bank financial firms: $208.8B, 20% of all loans [W1, W3], up 9% in six months [W2]. WF's stated protections are collateral eligibility rules and re-margining [W4], and both rely on what the borrower reports. Recent frauds at borrowers of this type (Tricolor, First Brands, MFS) beat those protections in several different ways at once. WF took "a single fraud-related loss" in this category in Q1 2026 [W5, C5] and responded with a manual, one-off sweep: "follow the money trail and trace back all the flows" [C4].

**What we design:** seven connected systems plus a combiner that continuously answer the credit officer's real question: *is this borrower's picture of itself true?*

**Scope boundary:** collateral-pool checks (uniqueness across lenders, field consistency, collections vs. reported) are already covered by Setpoint PledgeCheck, which WF backs [S1, S3]. We **ingest** its result and do not rebuild it. Our systems cover the borrower company *around* the pool.

Bracketed IDs refer to `research/VERIFY.md`. All fraud facts are **allegations** from SEC/DOJ documents.

---

## 1. Cause map: every documented mechanism gets a system

| # | Documented mechanism | Evidence | System that attacks it |
|---|---|---|---|
| 1 | Same collateral pledged to 2–3 lenders | T1, T2, F1 | **S1 Collateral integrity** |
| 2 | Ineligible or defaulted loans dressed up as eligible and current | T3, T6, T7 | **S2 Tape-vs-source check** |
| 3 | Loan money disguised as customer payments; "round trips" | F4, F1 | **S3 Cash provenance** |
| 4 | Fake or inflated invoices sold to invoice buyers | F1 | **S4 Invoice authenticity** |
| 5 | Hidden debt with other lenders ("Off-Sheet Lenders") | F1, F3 | **S5 Hidden-debt finder** |
| 6 | Related shell companies with no operations | F3 | **S6 Relationship mapper** |
| 7 | Manipulated financial statements ("bridge" files); false health | F5, T4 | **S7 Financial consistency** |

Why one system can't do it: each mechanism leaves a trace in a *different* place. That place might be the collateral tape, the source loan system, the bank account, the invoice, the public lien register, the company registry, or the financial statements. A check that reads one of those places is blind to the other six.

---

## 2. The seven systems

Every system is an independent module with the same interface: `run(entity_ids, as_of) -> list[Signal]`.

### S1 Collateral integrity: *is this collateral unique and clean?*
- **Inputs:** the PledgeCheck certificate/status where the borrower uses Setpoint; the borrower tapes for every WF facility.
- **Logic:**
  - (a) Read the PledgeCheck result as a signal.
  - (b) Run a cross-facility uniqueness check *inside WF*, across all WF facilities including those to entities S6 links to the borrower. PledgeCheck only sees the facilities reported to it.
  - (c) Match assets without IDs by attribute fingerprint (the kind of fuzzy match needed when IDs are withheld).
- **Output signals:** `DUPLICATE_ASSET`, `PLEDGECHECK_FAIL`, `PLEDGECHECK_ABSENT`.

### S2 Tape-vs-source check: *does the tape match the system it came from?*
Tricolor's CEO, on a recorded call, said the scheme's problem would be an auditor asking to "pull this up on your screen" [T7].
- **Inputs:** successive monthly tapes; randomly sampled direct pulls from the servicer's system (the borrower's loan system, read-only, as the credit agreement's audit rights allow); obligor confirmations.
- **Logic:**
  - (a) **Tape physics** — impossible transitions across tapes: 90 days past due → current with no matching payment; deferment flags appearing in bulk just before eligibility cut-offs; loan attributes changing after origination.
  - (b) Compare the sampled source records with the tape, field by field.
  - (c) Risk-weight the sampling toward the loans that matter most to eligibility.
- **Output signals:** `IMPOSSIBLE_TRANSITION`, `SOURCE_MISMATCH`, `ELIGIBILITY_EDGE_CLUSTER`.

### S3 Cash provenance: *who actually paid?*
A collections-matching check passes disguised loan money, because the cash really does arrive. First Brands routed lender money so that it "appeared to be ordinary customer receipts" [F4].
- **Inputs:** transactions in the controlled collection and operating accounts WF can see; the obligor/customer list; S6's relationship graph.
- **Logic:**
  - Classify each inbound payment by **payer identity**, not amount. A payer must be a known obligor or customer.
  - Flag payers that are lenders, related entities or collection entities outside the structure.
  - Detect circular flows (money out to X → back in "from customers").
  - Check the concentration of inflows through a single intermediary.
- **Output signals:** `NON_OBLIGOR_PAYER`, `RELATED_PARTY_INFLOW`, `CIRCULAR_FLOW`.

### S4 Invoice authenticity: *is this receivable real?*
- **Inputs:** invoices and receivable schedules (documents plus data); debtor confirmations; the debtors' later payments.
- **Logic:**
  - Duplicate fingerprints across facilities and financing partners (same debtor + amount + date + description, normalised).
  - Edit and inflation detection: the amount changes between versions; the amount is implausible for the debtor's size.
  - Dilution analysis: invoices that never get paid by the named debtor.
  - Claude reads document images and extracts fields. It never scores.
- **Output signals:** `DUPLICATE_INVOICE`, `ALTERED_INVOICE`, `UNPAID_BY_DEBTOR`.

### S5 Hidden-debt finder: *who else has a claim on this borrower?*
- **Inputs:** UCC financing statements (public; free per-state search, bulk data paid) against the borrower **and every entity S6 links to it**; court records (CourtListener API [D2]); the debt the borrower disclosed.
- **Logic:** secured parties or lien collateral descriptions not in the borrower's disclosed debt, especially liens on inventory or receivables that WF also relies on. Also: judgments, and new filings over time.
- **Output signals:** `UNDISCLOSED_SECURED_PARTY`, `COMPETING_LIEN`, `JUDGMENT`.

### S6 Relationship mapper: *who is really connected to this borrower?*
- **Inputs:** GLEIF Level 2 "who owns whom" [D1]; state business registries; shared officers, addresses, registered agents and phone numbers found in S4/S5 documents.
- **Logic:** build an entity graph and score "shell-likeness" (no operations, shared address, recent formation, a single counterparty).
- **Output signals:** `RELATED_ENTITY`, `SHELL_INDICATORS`.
- **Feeds** new entities into S1, S3 and S5.

### S7 Financial consistency: *do the reported financials fit the evidence?*
- **Inputs:** the borrower's reported financials and covenant certificates; aggregates from S3 (cash seen), S4 (receivables validity) and S5 (discovered debt).
- **Logic:**
  - Reported revenue vs. cash WF actually saw.
  - Receivables growth vs. revenue growth.
  - Debt disclosed vs. debt discovered.
  - A pattern of metrics repeatedly landing just above covenant thresholds.
- **Output signals:** `CASH_REVENUE_GAP`, `DEBT_GAP`, `COVENANT_EDGE_PATTERN`.

---

## 3. How the systems feed each other

```
S6 relationships ──► S5 (search liens on linked entities)
       │         ──► S3 (treat linked payers as related-party inflows)
       └───────► S1 (uniqueness across linked entities' facilities)
S4 invalid invoices ─► S7 (receivables quality)
S5 discovered debt ──► S7 (debt gap)
S3 cash seen ───────► S7 (cash vs revenue)
S2 source mismatches ► S1 (re-check affected assets)
All signals ────────► COMBINER ─► case file ─► credit officer (human decides)
```

**Worked chain** (the First Brands pattern):
1. S6 finds "Entity X", with the same owner and no operations.
2. S5 finds an inventory financier's UCC lien on X that the borrower never disclosed.
3. S3 finds X's lender money arriving as "customer receipts".
4. S7 now shows a debt gap and a cash-revenue gap.

No single signal is decisive, but four independent systems agreeing is.

---

## 4. Shared result contract

```json
{ "signal_id": "S5-000123",
  "entity_id": "BORROWER-017",
  "system": "S5",
  "type": "UNDISCLOSED_SECURED_PARTY",
  "severity": 0.8,            // how bad if true, 0–1
  "confidence": 0.9,          // how sure the system is, 0–1
  "evidence": ["ucc:OH-2025-0012345", "disclosure:2026-06-30#debt"],
  "explanation": "Secured party 'Inventory Capital LLC' not in disclosed debt schedule",
  "observed_at": "2026-07-01T00:00:00Z" }
```

Every signal must carry evidence pointers back to source rows or documents. A signal without evidence is rejected at ingest.

## 5. Combiner: from signals to verdict and fix

A risk number tells a credit officer nothing about what to do. The combiner's job is to hand a human a **solved case**: what's wrong, the proof, the verdict, the fix, and the paperwork, ready for one-click approval.

### The case flow (what the officer sees, in order)

| Step | What it is | Who produces it |
|---|---|---|
| 1. Finding | Plain words: "Likely hidden debt through a related company" | Combiner rules → open model writes the sentence |
| 2. Evidence | Every signal, with drill-down to its source row or document; the chain diagram | Systems S1–S7 |
| 3. Verdict | One of: *No issue · Explained (benign) · Needs more evidence · Likely fraud mechanism X*, with confidence *low / medium / high* | Deterministic rules over the signals; the model only phrases it |
| 4. Suggested fix | Concrete next steps from the playbook for that mechanism (below) | Playbook table (deterministic) |
| 5. Drafts | The letters, requests and memo for each step, pre-filled from the evidence | Open model, from the signal records only; every sentence cites signal IDs |
| 6. Approve | The officer approves, edits or rejects each step with one click. **Nothing is sent or changed without it.** | Human |
| 7. Track to resolved | Each step has an owner, a due date and a status; the case closes only when the issue is resolved or explained | Case service |
| 8. Learn | The officer's outcome (confirmed / benign) is saved as a label to re-tune thresholds | Case service → nightly job |

**The score still exists, but hidden:** a noisy-OR of `severity × confidence` with a corroboration bonus when *independent* systems agree. It only sets the **order of the queue**, so the officer sees the most urgent of 200 borrowers first. Hard escalations (a confirmed duplicate pledge or altered invoice) jump the queue.

### Playbooks: one per mechanism (the "suggested fix")

| Mechanism | Suggested fix steps (drafted, human-approved) |
|---|---|
| Double pledging (S1) | Hold advances on the duplicated assets · request lien searches/payoff letters from the other facility · re-run eligibility excluding those assets |
| Tape ≠ source (S2) | Expand the sample on affected pools · schedule a field exam with screen-level source review · recompute the borrowing base on verified data |
| Disguised receipts (S3) | Ask the borrower to explain each non-obligor payer · trace the flows back to origin (the manual sweep WF ran after Q1 [C4], now automatic) · tighten cash dominion on the collection account |
| Fake/altered invoices (S4) | Send debtor confirmations for the flagged invoices · mark them ineligible pending confirmation · widen confirmations to that debtor's other invoices |
| Hidden debt (S5) | Request the undisclosed lender's payoff/estoppel letter · check the intercreditor position · update the disclosed-debt schedule and covenants |
| Related shells (S6) | Request an ownership certification and related-party schedule · add the linked entities to monitoring |
| Financial inconsistency (S7) | Request reconciliations (revenue ↔ cash ↔ receivables) · have the borrower's auditor bridge the gap · re-test covenants on reconciled numbers |

**Why this split** (deterministic verdict/playbook, model only for reading and writing): a bank must be able to explain and validate every decision path. The OCC's agreement with WF itself cites the model-risk guidance, OCC Bulletin 2011-12 [O1]. WF's own Agentspace tools are described as helping employees "navigate policies and procedures" and "sort through scores of documentation": assisting, not deciding [A2]. WF has also used a network of interacting agents to re-underwrite 15 years of archived loan documents [A3]. That's the same multi-system pattern as this design. Keeping judgement in auditable rules and humans, and language in the model, is what makes the automation approvable.

## 6. Architecture: aligned to Wells Fargo's own engineering stack

The intern posting asks for Java, C#, SQL and Python [W18, primary]. WF's India engineering job ads also list Kafka, Spark, Spring Boot, and Airflow on Cloud Composer with Pub/Sub [W19, W20]. Those two are secondary: they come from search snippets, because the posting pages no longer load. We build with the same tools, so the project maps one-to-one onto the resume and the interview.

| Layer | Choice | Why |
|---|---|---|
| Streaming | **Kafka API** (Redpanda broker locally, a Kafka-compatible single binary) | Bank inflows arrive as events, so S3 alerts same-day instead of at month-end. WF uses Kafka [W18–W20] |
| Batch orchestration | **Airflow** | Nightly tape loads plus UCC/GLEIF/court pulls. WF uses Cloud Composer, which is managed Airflow [W19] |
| Store | **DuckDB** (+ optional **dbt-duckdb** for tested transforms) | Light, fast, and the data-quality tests are themselves controls. dbt isn't in WF ads, hence optional |
| Seven systems | **Python** modules, same `run() -> list[Signal]` interface | Independent, testable, replaceable |
| Case and playbook service | **Java Spring Boot** | Verdicts, playbooks, approvals, tracking. WF's backend language, and the intern posting lists Java [J1] |
| Model layer | **Swappable**: default is a fine-tuned small open model (section 6a) | Runs "inside the bank" |
| Console | **Next.js** + Tailwind; the chain view as a node graph | The officer's case screen |
| Monitoring (optional) | **Grafana** | Pipeline health, alert volumes, model drift: the ongoing monitoring model-risk rules expect. Not in WF ads |
| Proof | pytest, JUnit, promptfoo, an evaluation harness | Numbers, not claims |

**RAM limit:** the 8 GB Mac can't run Redpanda, Airflow, Spring Boot, Next.js and Grafana at once. Develop one service at a time; run the full stack in a cloud dev environment for the demo. No local model inference (per TOOLS.md).

## 6a. Model layer: a fine-tuned open model that runs "inside the bank"

**Why open, and why fine-tuned.** Cost is not the main reason. The main reason is privacy: a bank cannot send borrowers' confidential invoices and statements to an outside AI company. WF's own Fargo assistant already works this way: a small language model inside WF detects personal data before Google's Flash 2.0 is called [A1]. WF describes itself as "poly-model": Llama is used internally, and OpenAI models are used as needed [A1b]. Both come from VentureBeat, so they're secondary.

| Job | Model | How |
|---|---|---|
| Read invoices, receipts and statements (S4, S3), and scrub personal data | A **small open vision-language model, fine-tuned** with LoRA/QLoRA | Train on **Kaggle** free P100 GPUs, 30+ hours a week [G1]. Data: CORD receipts (CC-BY-4.0) [D3], FUNSD forms (licence to confirm) [D4], plus synthetic altered and duplicate invoices |
| Write findings, verdict sentences and draft letters | A small open instruct model | Prompted with the signal records only; must cite signal IDs |
| Optional larger model | Any provider, via the same interface | Sees **scrubbed** text only, the Fargo pattern |
| Live demo hosting | **Hugging Face ZeroGPU Space** (free) [G2] | Can be slow to wake up; the demo also ships precomputed results as a fallback |

**The proof point it creates:** "My fine-tuned small model extracts invoice fields at X% vs. the base model's Y% on a held-out set, and it never sends data outside." Pick the specific base model at build time; newer ones may exist after the knowledge cutoff.

**Licences:** check each dataset's licence before training (research use vs. commercial) and record it in the model card.

## 7. Data: real where it exists, labelled synthetic where banks keep it private

| Input | Real / synthetic | Status |
|---|---|---|
| Who owns whom | Real: GLEIF API [D1] | ok |
| Liens | Real samples via state search; synthetic registry at scale in UCC-1 format | warn (bulk is paid) |
| Court records | Real: CourtListener [D2] | ok |
| Loan tapes | Synthetic, with distributions calibrated on SEC ABS-EE public auto-loan data | warn (ABS-EE has no VIN/obligor ID per the sec-api docs; secondary) |
| Bank flows, invoices, financials | Synthetic | crit: private in real life. **WF has these; we don't.** |

The honest consequence: the demo proves the *design and detection logic*. Real performance needs WF's own data, which is exactly why this is pitched as "here's the design, let me build it on your data".

## 8. Proof plan (realistic, not "100%")

**Synthetic book:** ~200 borrowers, 24 months, with planted scenarios:
- one per documented mechanism
- combinations (a First Brands-style multi-mechanism borrower)
- **innocent noise** that should *not* be flagged: legitimate deferment programmes, late files, real related-party leases

**Measures:**
1. Catch rate per mechanism and overall.
2. **Ablation:** switch off each system and measure the drop. This proves each system earns its place and that several beat one.
3. **Beyond PledgeCheck:** simulate PledgeCheck's four published checks [S3] as a baseline and count the frauds that pass it but that we catch.
4. Days to detection vs. a quarterly sample-audit baseline.
5. False alarms per 100 clean borrowers; precision in the top decile of the queue.
6. AI faithfulness: 100% of summary and draft sentences cite an existing signal (promptfoo).
7. **Fine-tuned vs. base model:** field-extraction accuracy on held-out receipts and invoices, plus the altered-invoice detection rate.
8. **Fix quality:** for each planted case, does the suggested playbook address the planted mechanism? (Checked against the scenario's ground truth.) Also: time from alert to a ready-to-approve case file.

## 9. Where it would sit at Wells Fargo
First line: credit officers and portfolio managers for NDFI facilities. Second line: credit risk review. We name roles, never people.

## 10. Limits and risks (said out loud)
- **Private data dependence:** the S2, S3, S4 and S7 inputs exist only inside WF and the borrower.
- **Synthetic realism:** planted frauds follow the documented mechanisms, so catching them proves coverage, not real-world rates.
- **Legal:** all fraud facts are allegations. We never suggest that WF's Q1 loss borrower is any named company.
- **Not a credit engine:** it produces verdicts, fixes and drafts for a human to approve. It never sends, changes or decides anything by itself.
- **Model risk:** the fine-tuned model is validated on held-out data, documented in a model card, and monitored for drift. Verdicts come from auditable rules, not the model.

## 12. Scale, speed, fallbacks and optimization

**How it scales.** Every check is scoped to one borrower, so the work partitions by `borrower_id`:
- **Streaming:** payment events go to a Kafka topic keyed by `borrower_id`. Adding partitions and consumers scales S3 linearly.
- **Batch:** tapes, filings and financials are processed **incrementally**. Only rows that changed since the last run are processed, found by content hash / change data capture. Nothing is recomputed from scratch.
- **Storage and engine:** columnar Parquet, partitioned by borrower and month. The same SQL runs on DuckDB (demo, one machine) and on Spark or BigQuery (bank scale).
- **Workers:** stateless, horizontally scalable containers, one pool per system.
- WF does not disclose borrower or asset counts for this book, so capacity is **measured, not claimed**. The load test runs 10k → 1M → 10M+ synthetic rows and reports throughput and latency per system. Bank-scale capacity is extrapolated from that curve, with the arithmetic shown.

**Speed targets** (our proposed service levels, to be measured):

| Path | Target |
|---|---|
| Suspicious payment → S3 signal | minutes after the payment event |
| Nightly batch, all borrowers | finishes before business opens |
| New signals → case file with verdict, fix and drafts | < 1 minute |
| Document reading | documents per minute per GPU, reported |

**Fallbacks: nothing fails silently.**

| Failure | Behaviour |
|---|---|
| One system crashes or times out | The case still builds, marked "S4 unavailable, confidence reduced". The combiner never waits forever |
| A message fails processing | Retry with backoff → a dead-letter topic → a replay tool; idempotent handlers make replay safe |
| Fine-tuned model is down or unsure | Base model → OCR + rules → human review queue |
| Public data source is down (GLEIF, courts, UCC) | Serve the cached result with a "stale since" flag; a background retry refreshes it |
| Bad borrower file (schema or quality failure) | Quarantined by data-quality tests; an alert goes out; the last good data is kept |
| Kafka or the batch scheduler restarts | Consumers resume from committed offsets; batch jobs resume from checkpoints |

**Optimization:**
- **Cheap checks first:** the model only reads documents that the rules flagged.
- **Model runs:** batched inference with a 4-bit quantized model.
- **Smart matching:** blocking keys for fuzzy matching, so pairs are never compared all-against-all.
- **Caching:** cached public-record lookups and a precomputed entity graph.
- **Queries:** partition pruning on every query.

**Showing it working:**
1. A live operations dashboard (Prometheus + Grafana): throughput, backlog, latency, health per system, fallback events.
2. A load-test report with charts.
3. A break-it demo: kill a system mid-run and show degraded mode and recovery.
4. A 24-month replay of a planted First Brands-style borrower, showing the detection day vs. a quarterly audit.

## 13. Fitting into Wells Fargo's real environment

A great tool can still fail to fit a bank. This design plans for that from day one:
- **Ports and adapters:** every input and output goes through an adapter behind a fixed interface: tapes, bank transactions, UCC/GLEIF/courts, case output, outbound drafts. Moving into WF means writing adapters to WF systems, not rewriting the seven checks.
- **Standard interfaces:** Kafka topics, REST (OpenAPI), SQL, and containers that run on Kubernetes or managed cloud. WF's job ads mention Kafka and Google Cloud [W19, W20, secondary].
- **Private by default:** the model runs in-house and no external calls are required.
- **Bank paperwork included:** a model card, a validation report, monitoring, an audit log of every signal, verdict, approval and change; role-based access.
- **Adoptable piece by piece:** each system runs alone, so WF could start with S3 alone.
- **Not solvable from outside (stated plainly):** WF's approval timelines (security, third-party risk, model-risk validation) and access to real data. The design makes those reviews easy; it cannot skip them.

## 14. Built and measured (11 Sep 2026)

Everything in §1–§13 is implemented. Measured on synthetic data:

**Held-out proof** (seeds 201–205, never used while tuning; `proof/REPORT.md`):

| Measure | Result |
|---|---|
| Catch rate | 95% (143/150) vs 47% for a quarterly sample audit |
| Honest borrowers flagged "likely fraud" | 0 per 100 |
| Honest borrowers routed to "worth a look" | 29 per 100 |
| Detection vs the audit (median) | 120 days earlier |
| Frauds never flagged by PledgeCheck | 111 |
| Weakest mechanism | dressed-up tapes, 73% |

The switch-off test shows every system contributes.

**Scale** (`proof/scale.json`, one 8 GB laptop):
- 1.25M rows in 0.51 s
- 5.0M rows in 1.31 s
- 12.4M rows in 2.30 s (5.4M rows/s)

**Break-it:**
- With S4 crashed, all 120 cases still build and are marked "S4 unavailable"; 3 fraud cases drop to a lower verdict.
- With S6 crashed, downstream systems run degraded; 5 drop.

**End to end:**
1. The pipeline publishes to the Java case service, which creates 173 proposed steps with drafts.
2. Approving a step works; marking an unapproved step done is refused (HTTP 409).
3. Every decision is audited and exported to Prometheus.
4. The console shows the solved case and works live or from the static snapshot.

**Changes from the plan, and why:**
- **Seven systems, not six.** S2 (tape-vs-source) was split from cash, because the DOJ record shows two distinct tricks.
- **The combiner's verdict is Python, not Java.** Evaluation needs the same code the demo serves. Java owns cases, playbooks, drafts, approvals and audit.
- **PledgeCheck covers more than first assumed**, including collections matching. The design now ingests its result and targets the borrower around the pool.
- **Lien matching uses names plus addresses.** Registers have no IDs, and name-only matching produced false alarms.

**Still to do:**
- Fine-tune the document model on Kaggle. It needs Vedant's Kaggle and Hugging Face tokens.
- Run the full stack in Codespaces.
- Deploy the console to Vercel, after Vedant approves the public link.

## 11. Interview story, in 30 seconds
"Your biggest loan book is lending to lenders. The frauds hitting that market use seven different tricks, and each one hides in a different place. You backed a tool that protects the collateral pool. I designed seven connected checks that watch the borrower around the pool. The system doesn't just flag a borrower: it tells the officer what's wrong, shows the proof, suggests the fix and drafts the paperwork, all for one-click approval. The document reading runs on a small model I fine-tuned, so borrower data never leaves the bank. It's built on your stack: Kafka, Airflow, Spring Boot."
