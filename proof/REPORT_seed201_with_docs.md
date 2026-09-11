# Proof report: Borrower Truth on synthetic books

Held-out seeds [201] · 120 borrowers · 30 with planted fraud · 90 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 29/30 (97%) | 14/30 (47%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 0.0 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=14) | 90.0 | – |
| Frauds the audit never caught but we did | 16 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 11/12 (92%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 60/60 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 32.2 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 1 | |
| Frauds caught that PledgeCheck's four checks never flagged | 22 (PledgeCheck flagged 8) | |
| Mean run time, all borrowers, one month | 0.685 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 5 |
| before the effects start | 4 |
| over 3 months later | 3 |
| same month | 17 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 9/9 (100%) |
| TAPE_DRESSUP | 5/9 (56%) |
| DISGUISED_RECEIPTS | 8/8 (100%) |
| FAKE_INVOICES | 7/7 (100%) |
| HIDDEN_DEBT | 8/8 (100%) |
| RELATED_SHELLS | 10/10 (100%) |
| FIN_MANIPULATION | 13/13 (100%) |

## Per pattern

| Pattern | Caught |
|---|---|
| tricolor_like | 5/5 (100%) |
| first_brands_like | 5/5 (100%) |
| single | 19/20 (95%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 2 | 4 |
| S2 | 3 | 5 |
| S3 | 6 | 24 |
| S4 | 3 | 7 |
| S5 | 5 | 13 |
| S6 | 5 | 25 |
| S7 | 3 | 13 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
