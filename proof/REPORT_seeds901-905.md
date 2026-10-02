# Proof report: Borrower Truth on synthetic books

Held-out seeds [901, 902, 903, 904, 905] · 600 borrowers · 250 with planted fraud · 350 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 248/250 (99%) | 96/250 (38%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 3.43 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=96) | 60.0 | – |
| Frauds the audit never caught but we did | 153 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 427/427 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 30.0 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 1 | |
| Frauds caught that PledgeCheck's four checks never flagged | 207 (PledgeCheck flagged 41) | |
| Mean run time, all borrowers, one month | 1.046 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 85 |
| before the effects start | 29 |
| over 3 months later | 8 |
| same month | 126 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 65/65 (100%) |
| TAPE_DRESSUP | 64/65 (98%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 35/35 (100%) |
| HIDDEN_DEBT | 60/60 (100%) |
| RELATED_SHELLS | 61/61 (100%) |
| FIN_MANIPULATION | 62/65 (95%) |

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
| S1 | 28 | 37 |
| S2 | 39 | 64 |
| S3 | 66 | 159 |
| S4 | 7 | 19 |
| S5 | 43 | 85 |
| S6 | 32 | 127 |
| S7 | 14 | 62 |
| SEC | 40 | 40 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
