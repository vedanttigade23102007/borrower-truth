# Proof report: Borrower Truth on synthetic books

Held-out seeds [1201, 1202, 1203, 1204, 1205] · 600 borrowers · 250 with planted fraud · 350 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 248/250 (99%) | 92/250 (37%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 2.0 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=92) | 90.0 | – |
| Frauds the audit never caught but we did | 157 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 427/429 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 28.9 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 1 | |
| Frauds caught that PledgeCheck's four checks never flagged | 210 (PledgeCheck flagged 38) | |
| Mean run time, all borrowers, one month | 0.723 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 81 |
| before the effects start | 27 |
| over 3 months later | 9 |
| same month | 131 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 65/65 (100%) |
| TAPE_DRESSUP | 64/65 (98%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 36/36 (100%) |
| HIDDEN_DEBT | 60/60 (100%) |
| RELATED_SHELLS | 59/59 (100%) |
| FIN_MANIPULATION | 63/65 (97%) |

## Per pattern

| Pattern | Caught |
|---|---|
| filer_hidden_debt | 20/20 (100%) |
| first_brands_like | 25/25 (100%) |
| nominee_shell | 20/20 (100%) |
| paid_to_look_current | 19/20 (95%) |
| public_pool_double_pledge | 20/20 (100%) |
| round_trip | 20/20 (100%) |
| single | 99/100 (99%) |
| tricolor_like | 25/25 (100%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 24 | 39 |
| S2 | 39 | 64 |
| S3 | 67 | 161 |
| S4 | 12 | 29 |
| S5 | 42 | 82 |
| S6 | 30 | 121 |
| S7 | 14 | 63 |
| SEC | 39 | 41 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
