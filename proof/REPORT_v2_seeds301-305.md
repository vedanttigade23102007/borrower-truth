# Proof report: Borrower Truth on synthetic books

Held-out seeds [301, 302, 303, 304, 305] · 600 borrowers · 190 with planted fraud · 410 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 189/190 (99%) | 78/190 (41%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 1.46 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=78) | 150.0 | – |
| Frauds the audit never caught but we did | 111 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 365/366 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 30.5 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 0 | |
| Frauds caught that PledgeCheck's four checks never flagged | 146 (PledgeCheck flagged 43) | |
| Mean run time, all borrowers, one month | 0.86 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 37 |
| before the effects start | 30 |
| over 3 months later | 14 |
| same month | 108 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 44/45 (98%) |
| TAPE_DRESSUP | 45/45 (100%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 32/32 (100%) |
| HIDDEN_DEBT | 40/40 (100%) |
| RELATED_SHELLS | 62/62 (100%) |
| FIN_MANIPULATION | 62/65 (95%) |

## Per pattern

| Pattern | Caught |
|---|---|
| first_brands_like | 25/25 (100%) |
| nominee_shell | 20/20 (100%) |
| round_trip | 20/20 (100%) |
| single | 99/100 (99%) |
| tricolor_like | 25/25 (100%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 7 | 15 |
| S2 | 20 | 45 |
| S3 | 69 | 170 |
| S4 | 10 | 21 |
| S5 | 23 | 67 |
| S6 | 38 | 149 |
| S7 | 15 | 62 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
