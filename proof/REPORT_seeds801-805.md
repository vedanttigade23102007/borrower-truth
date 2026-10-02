# Proof report: Borrower Truth on synthetic books

Held-out seeds [801, 802, 803, 804, 805] · 600 borrowers · 250 with planted fraud · 350 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 249/250 (100%) | 96/250 (38%) |
| False alarms per 100 honest borrowers (final month) | 0.29 | 3.71 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.29 | |
| Median days earlier than the audit (frauds both caught, n=96) | 120.0 | – |
| Frauds the audit never caught but we did | 154 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 426/426 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 30.9 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 0 | |
| Frauds caught that PledgeCheck's four checks never flagged | 208 (PledgeCheck flagged 41) | |
| Mean run time, all borrowers, one month | 1.029 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 82 |
| before the effects start | 25 |
| over 3 months later | 9 |
| same month | 133 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 65/65 (100%) |
| TAPE_DRESSUP | 64/65 (98%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 35/35 (100%) |
| HIDDEN_DEBT | 60/60 (100%) |
| RELATED_SHELLS | 57/57 (100%) |
| FIN_MANIPULATION | 65/65 (100%) |

## Per pattern

| Pattern | Caught |
|---|---|
| filer_hidden_debt | 20/20 (100%) |
| first_brands_like | 25/25 (100%) |
| nominee_shell | 20/20 (100%) |
| paid_to_look_current | 20/20 (100%) |
| public_pool_double_pledge | 20/20 (100%) |
| round_trip | 20/20 (100%) |
| single | 99/100 (99%) |
| tricolor_like | 25/25 (100%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 29 | 39 |
| S2 | 39 | 64 |
| S3 | 68 | 157 |
| S4 | 12 | 22 |
| S5 | 41 | 82 |
| S6 | 29 | 123 |
| S7 | 15 | 65 |
| SEC | 40 | 40 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.

## After scoring: what caused the one honest flag (diagnosis only, 2 Oct 2026; no code changed)

Everything above this line was written by the evaluation and committed unchanged (7be6d34, pushed). This section was added later.

**B0003, seed 804 (real-estate lender, honest), flagged by the random servicer-system pull: a cut-off timing difference.**
- 2 of the 60 loans pulled at month 24 are 60–89 days late in the servicer system, while the tape reports them 30–59 days late, so still eligible.
- Both loans were 30–59 days late in both systems the month before. Each missed its last two payments, and the servicer's month-end count had rolled it into 60–89 days while the tape had not.
- That is one month of ageing between two cut-off dates, the kind of difference a field examiner reconciles. It isn't loans dressed up as current.
- **Not caused by the round-2 fixes.** The rules frozen before them (tag `redteam-round2-frozen`) flag B0003 on this book too. Checked by running that tagged code on seed 804.
- **On the dev books:**
  - Of the honest loans the pull could flag (eligible on the tape, 60+ late or missing in the servicer system), 318 of 336 rows (95%) are exactly this case: 30–59 on the tape, 60–89 in the servicer, 30–59 in the servicer the month before.
  - Of the fraud borrowers' rows, it is 220 of 10,614 (2%). The rest are loans reported current while really 60+ late, or loans missing from the servicer system.
