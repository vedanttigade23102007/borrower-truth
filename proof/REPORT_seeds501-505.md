# Proof report: Borrower Truth on synthetic books

Held-out seeds [501, 502, 503, 504, 505] · 600 borrowers · 249 with planted fraud · 351 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 246/249 (99%) | 89/249 (36%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 1.99 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=89) | 90 | – |
| Frauds the audit never caught but we did | 159 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 426/426 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 25.6 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 2 | |
| Frauds caught that PledgeCheck's four checks never flagged | 212 (PledgeCheck flagged 34) | |
| Mean run time, all borrowers, one month | 0.927 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 80 |
| before the effects start | 25 |
| over 3 months later | 12 |
| same month | 129 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 64/64 (100%) |
| TAPE_DRESSUP | 63/65 (97%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 33/33 (100%) |
| HIDDEN_DEBT | 60/60 (100%) |
| RELATED_SHELLS | 62/62 (100%) |
| FIN_MANIPULATION | 64/65 (98%) |

## Per pattern

| Pattern | Caught |
|---|---|
| filer_hidden_debt | 20/20 (100%) |
| first_brands_like | 25/25 (100%) |
| nominee_shell | 20/20 (100%) |
| paid_to_look_current | 18/20 (90%) |
| public_pool_double_pledge | 19/19 (100%) |
| round_trip | 20/20 (100%) |
| single | 99/100 (99%) |
| tricolor_like | 25/25 (100%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 26 | 31 |
| S2 | 38 | 63 |
| S3 | 68 | 165 |
| S4 | 10 | 24 |
| S5 | 43 | 86 |
| S6 | 35 | 135 |
| S7 | 14 | 64 |
| SEC | 39 | 39 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
