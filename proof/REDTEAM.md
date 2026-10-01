# Red team result: seeds 501, 502, 503, 504, 505, scored once

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

Rules version 614d4a97ea9e (frozen: 614d4a97ea9e); code 064eaab.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| abs_overlap | 10 | 0 | 4 | 6 | - | - | yes | no |
| deferment_mask | 10 | 10 | 0 | 0 | 1 | - | yes | no |
| double_pledge | 10 | 0 | 1 | 9 | - | - | no | no |
| fee_strip | 10 | 0 | 4 | 6 | - | - | no | yes |
| ghost_vins | 10 | 0 | 2 | 8 | - | - | yes | no |
| month_end_cure | 10 | 0 | 6 | 4 | - | - | yes | no |
| offsheet_shells | 10 | 0 | 3 | 7 | - | - | no | yes |
| round_trip | 10 | 9 | 1 | 0 | 15 | - | no | no |
| **All counted attacks** | 80 | 19 | 21 | 40 | 2 | | | |
| **Without either partial lever** | 20 | 9 | 2 | 9 | 15 | | | |
| **With the servicer lever** | 40 | 10 | 12 | 18 | 1 | | | |
| **With the company-history lever** | 20 | 0 | 7 | 13 | - | | | |

Honest borrowers in the attacked books: 271. Flagged at month 24: 0; flagged in any month: 0; sent to review: 23.6 per 100.
The books' own planted frauds: 246/249 caught.

## Every red-team fraud not caught

- **abs_overlap** on B0016 (seed 501): sent to review; gain $15,234,668 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **abs_overlap** on B0111 (seed 501): missed; gain $7,293,143 (7% of the credit limit); findings: none
- **double_pledge** on B0079 (seed 501): missed; gain $19,900,816 (7% of the credit limit); findings: none
- **double_pledge** on B0036 (seed 501): missed; gain $14,141,349 (6% of the credit limit); findings: none
- **fee_strip** on B0095 (seed 501): sent to review; gain $6,774,090 (7% of the credit limit); findings: FIN_MANIPULATION (low)
- **fee_strip** on B0075 (seed 501): sent to review; gain $15,912,463 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **ghost_vins** on B0042 (seed 501): missed; gain $4,398,890 (7% of the credit limit); findings: none
- **ghost_vins** on B0088 (seed 501): missed; gain $20,912,232 (7% of the credit limit); findings: none
- **month_end_cure** on B0044 (seed 501): sent to review; gain $25,764,725 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **month_end_cure** on B0120 (seed 501): missed; gain $22,498,236 (7% of the credit limit); findings: none
- **offsheet_shells** on B0040 (seed 501): missed; gain $6,972,735 (6% of the credit limit); findings: none
- **offsheet_shells** on B0094 (seed 501): sent to review; gain $2,000,219 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **abs_overlap** on B0020 (seed 502): missed; gain $26,052,667 (7% of the credit limit); findings: none
- **abs_overlap** on B0091 (seed 502): missed; gain $7,481,740 (7% of the credit limit); findings: none
- **double_pledge** on B0064 (seed 502): missed; gain $8,240,968 (6% of the credit limit); findings: none
- **double_pledge** on B0115 (seed 502): missed; gain $8,960,351 (6% of the credit limit); findings: none
- **fee_strip** on B0112 (seed 502): missed; gain $8,872,880 (6% of the credit limit); findings: none
- **fee_strip** on B0026 (seed 502): missed; gain $16,949,823 (7% of the credit limit); findings: none
- **ghost_vins** on B0015 (seed 502): missed; gain $14,538,855 (7% of the credit limit); findings: none
- **ghost_vins** on B0061 (seed 502): sent to review; gain $14,653,717 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **month_end_cure** on B0080 (seed 502): sent to review; gain $6,490,014 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **month_end_cure** on B0106 (seed 502): missed; gain $3,070,812 (7% of the credit limit); findings: none
- **offsheet_shells** on B0065 (seed 502): missed; gain $4,306,047 (6% of the credit limit); findings: none
- **offsheet_shells** on B0087 (seed 502): missed; gain $4,303,181 (7% of the credit limit); findings: none
- **round_trip** on B0029 (seed 502): sent to review; gain $1,485,854 (7% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **abs_overlap** on B0115 (seed 503): sent to review; gain $5,835,237 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **abs_overlap** on B0028 (seed 503): sent to review; gain $7,255,024 (7% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **double_pledge** on B0036 (seed 503): missed; gain $5,707,106 (6% of the credit limit); findings: none
- **double_pledge** on B0114 (seed 503): sent to review; gain $2,774,825 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **fee_strip** on B0101 (seed 503): missed; gain $10,683,270 (7% of the credit limit); findings: none
- **fee_strip** on B0085 (seed 503): sent to review; gain $9,347,872 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **ghost_vins** on B0005 (seed 503): sent to review; gain $17,087,138 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **ghost_vins** on B0057 (seed 503): missed; gain $7,844,507 (7% of the credit limit); findings: none
- **month_end_cure** on B0120 (seed 503): missed; gain $8,360,608 (7% of the credit limit); findings: none
- **month_end_cure** on B0016 (seed 503): sent to review; gain $19,559,405 (7% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **offsheet_shells** on B0049 (seed 503): missed; gain $17,626,987 (6% of the credit limit); findings: none
- **offsheet_shells** on B0032 (seed 503): sent to review; gain $32,494,161 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **abs_overlap** on B0074 (seed 504): sent to review; gain $12,475,123 (7% of the credit limit); findings: FIN_MANIPULATION (low), HIDDEN_DEBT (low)
- **abs_overlap** on B0021 (seed 504): missed; gain $17,678,507 (7% of the credit limit); findings: none
- **double_pledge** on B0046 (seed 504): missed; gain $8,797,216 (7% of the credit limit); findings: none
- **double_pledge** on B0031 (seed 504): missed; gain $13,142,282 (6% of the credit limit); findings: none
- **fee_strip** on B0002 (seed 504): missed; gain $11,090,918 (6% of the credit limit); findings: none
- **fee_strip** on B0040 (seed 504): missed; gain $4,314,375 (6% of the credit limit); findings: none
- **ghost_vins** on B0004 (seed 504): missed; gain $29,052,383 (7% of the credit limit); findings: none
- **ghost_vins** on B0075 (seed 504): missed; gain $23,023,062 (7% of the credit limit); findings: none
- **month_end_cure** on B0047 (seed 504): sent to review; gain $8,502,268 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **month_end_cure** on B0050 (seed 504): sent to review; gain $10,807,246 (7% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **offsheet_shells** on B0062 (seed 504): sent to review; gain $9,602,552 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **offsheet_shells** on B0076 (seed 504): missed; gain $2,923,470 (6% of the credit limit); findings: none
- **abs_overlap** on B0102 (seed 505): missed; gain $8,684,949 (7% of the credit limit); findings: none
- **abs_overlap** on B0034 (seed 505): missed; gain $21,112,963 (7% of the credit limit); findings: none
- **double_pledge** on B0073 (seed 505): missed; gain $9,221,799 (7% of the credit limit); findings: none
- **double_pledge** on B0030 (seed 505): missed; gain $9,328,001 (7% of the credit limit); findings: none
- **fee_strip** on B0108 (seed 505): missed; gain $30,292,660 (7% of the credit limit); findings: none
- **fee_strip** on B0117 (seed 505): sent to review; gain $3,259,877 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **ghost_vins** on B0075 (seed 505): missed; gain $12,898,056 (7% of the credit limit); findings: none
- **ghost_vins** on B0080 (seed 505): missed; gain $7,223,235 (7% of the credit limit); findings: none
- **month_end_cure** on B0056 (seed 505): missed; gain $4,151,568 (7% of the credit limit); findings: none
- **month_end_cure** on B0023 (seed 505): sent to review; gain $12,544,414 (7% of the credit limit); findings: RELATED_SHELLS (low)
- **offsheet_shells** on B0112 (seed 505): missed; gain $6,094,969 (7% of the credit limit); findings: none
- **offsheet_shells** on B0047 (seed 505): missed; gain $7,031,399 (7% of the credit limit); findings: none

## Leak scan of the hand-in: 9 forbidden terms

- `attacks/README.md`: DOUBLE_PLEDGE: …consumer, real estate | 9 | yes | no | ~6.5% | | `double_pledge` | a second facility on the same collateral, with…
- `attacks/README.md`: DOUBLE_PLEDGE: …and the four that do not touch the tape at all - `double_pledge`, `round_trip`, `offsheet_shells`, `fee_strip` - …
- `attacks/README.md`: round_trip: … no shared key | auto | 6 | yes | no | ~6.5% | | `round_trip` | invoices for sales that never happened, early …
- `attacks/README.md`: round_trip: … do not touch the tape at all - `double_pledge`, `round_trip`, `offsheet_shells`, `fee_strip` - all set it Fal…
- `attacks/deferment_mask/plant.py`: DEFERMENT_PROGRAM: …         "borrower_id": ctx.bid,         "kind": "deferment_program",         "counterparty_entity_id": None,        …
- `attacks/double_pledge/README.md`: DOUBLE_PLEDGE: …# double_pledge  **Story.** From month 8 the borrower raises a se…
- `attacks/double_pledge/plant.py`: DOUBLE_PLEDGE: …"""double_pledge - the same collateral financed twice.  Follows th…
- `attacks/round_trip/README.md`: round_trip: …# round_trip  **Story.** The borrower is an invoice-finance co…
- `attacks/round_trip/plant.py`: round_trip: …"""round_trip - invoices for sales that never happened, paid fo…
