# Proof report: Borrower Truth on synthetic books

Held-out seeds [1101, 1102, 1103, 1104, 1105] · 600 borrowers · 250 with planted fraud · 350 honest. **All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.

| Measure | Borrower Truth | Quarterly sample audit |
|---|---|---|
| Frauds caught by month 24 | 250/250 (100%) | 98/250 (39%) |
| False alarms per 100 honest borrowers (final month) | 0.0 | 2.0 (ever) |
| False alarms per 100 honest borrowers (ever, any month) | 0.0 | |
| Median days earlier than the audit (frauds both caught, n=98) | 120.0 | – |
| Frauds the audit never caught but we did | 152 | – |
| Top-decile precision (highest-priority 10% of the queue that are real frauds) | 60/60 (100%) | |
| Caught frauds whose suggested fix targets a planted mechanism | 100% | |
| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | 433/434 (100%) | |
| Honest borrowers routed to 'needs more evidence' (review load) per 100 | 29.1 | |
| Planted frauds left at 'needs more evidence' (not missed, not flagged) | 0 | |
| Frauds caught that PledgeCheck's four checks never flagged | 216 (PledgeCheck flagged 34) | |
| Mean run time, all borrowers, one month | 1.214 s | |

## When we caught it, relative to the fraud's first effects in the data

| Timing | Frauds |
|---|---|
| 1-3 months later | 85 |
| before the effects start | 23 |
| over 3 months later | 7 |
| same month | 135 |

'Before the effects start' happens because precursors are public records that exist before the fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. It is not a sign the system sees the future.

## Per mechanism (finding at medium or high confidence)

| Mechanism | Caught |
|---|---|
| DOUBLE_PLEDGE | 65/65 (100%) |
| TAPE_DRESSUP | 65/65 (100%) |
| DISGUISED_RECEIPTS | 80/80 (100%) |
| FAKE_INVOICES | 35/35 (100%) |
| HIDDEN_DEBT | 60/60 (100%) |
| RELATED_SHELLS | 64/64 (100%) |
| FIN_MANIPULATION | 64/65 (98%) |

## Per pattern

| Pattern | Caught |
|---|---|
| filer_hidden_debt | 20/20 (100%) |
| first_brands_like | 25/25 (100%) |
| nominee_shell | 20/20 (100%) |
| paid_to_look_current | 20/20 (100%) |
| public_pool_double_pledge | 20/20 (100%) |
| round_trip | 20/20 (100%) |
| single | 100/100 (100%) |
| tricolor_like | 25/25 (100%) |

## Switch-off test: what is lost when one system is removed

| System off | Fraud borrowers lost | Mechanism detections lost |
|---|---|---|
| S1 | 28 | 39 |
| S2 | 40 | 65 |
| S3 | 66 | 165 |
| S4 | 8 | 21 |
| S5 | 42 | 88 |
| S6 | 35 | 133 |
| S7 | 15 | 64 |
| SEC | 39 | 40 |

Every system that loses detections when switched off earns its place. Zero borrowers lost with a system off means the others overlap it (defence in depth), not that it is useless: check the mechanism column.
