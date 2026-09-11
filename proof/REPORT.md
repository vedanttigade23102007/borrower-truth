# Proof report: Borrower Truth on synthetic books

Held-out seeds [201, 202, 203, 204, 205] · 600 borrowers · 150 with planted fraud · 450 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 143/150 (95%) | 71/150 (47%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 2.44 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=71) | 120 | – |
| Frauds the audit never caught but we did | 75 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 59/60 (98%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 294/294 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 31.3 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 4 | |
| Frauds caught that PledgeCheck's four checks never flagged | 111 (PledgeCheck flagged 33) | |
| Mean run time, all borrowers, one month | 0.728 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 27 |
| before the effects start | 25 |
| over 3 months later | 11 |
| same month | 80 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 44/45 (98%) |
| TAPE_DRESSUP | 33/45 (73%) |
| DISGUISED_RECEIPTS | 40/40 (100%) |
| FAKE_INVOICES | 33/33 (100%) |
| HIDDEN_DEBT | 40/40 (100%) |
| RELATED_SHELLS | 45/45 (100%) |
| FIN_MANIPULATION | 59/65 (91%) |

## Per pattern

| Pattern | Caught |
|---|---|
| tricolor_like | 25/25 (100%) |
| first_brands_like | 25/25 (100%) |
| single | 93/100 (93%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 9 | 19 |
| S2 | 17 | 33 |
| S3 | 27 | 109 |
| S4 | 15 | 33 |
| S5 | 24 | 67 |
| S6 | 20 | 115 |
| S7 | 12 | 59 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
