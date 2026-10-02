# Red team result: seeds 601, 602, 603, 604, 605, scored once (After fixes: these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5 (as Vedant reported on 2 Oct 2026, after scoring; recorded here afterwards)

**Caveat on comparing round 1 with round 2 (added 2 Oct 2026, at Vedant's request).** Round 2's attacker (Sonnet 5.5) may have been a weaker model than round 1's (Opus 5), so part of the improvement from round 1 to round 2 may come from that. The rules of the test also changed in between, in both directions. Credit limits were sized to each borrower's own collateral, so an attack worth 5% of the limit became a smaller share of the book, which is harder to catch. The payer rule took away recording money under a false sender, which is easier to catch. The rounds are not like for like. Both rounds used Claude models, the same family as the model that helped write the checks, so the "same family" limit still stands.

**After fixes: these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version cdf8b9b94a09 (frozen: cdf8b9b94a09); code 7309d5f.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| abs_overlap | 9 | 0 | 9 | 0 | - | - | yes | no |
| deferment_mask | 10 | 10 | 0 | 0 | 1 | - | yes | no |
| double_pledge | 10 | 7 | 3 | 0 | 5 | - | no | no |
| fee_strip | 10 | 0 | 9 | 1 | - | - | no | yes |
| ghost_vins | 10 | 0 | 3 | 7 | - | - | yes | no |
| month_end_cure | 10 | 0 | 10 | 0 | - | - | yes | no |
| offsheet_shells | 10 | 1 | 9 | 0 | 9 | - | no | yes |
| round_trip | 10 | 0 | 10 | 0 | - | - | no | no |
| **All counted attacks** | 79 | 18 | 53 | 8 | 3 | | | |
| **Without either partial lever** | 20 | 7 | 13 | 0 | 5 | | | |
| **With the servicer lever** | 39 | 10 | 22 | 7 | 1 | | | |
| **With the company-history lever** | 20 | 1 | 18 | 1 | 9 | | | |

Honest borrowers in the attacked books: 271. Flagged at month 24: 0; flagged in any month: 0; sent to review: 30.6 per 100.
The books' own planted frauds: 246/250 caught.

## Every red-team fraud not caught

- **abs_overlap** on B0068 (seed 601): sent to review; gain $386,051 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **abs_overlap** on B0049 (seed 601): sent to review; gain $200,612 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **double_pledge** on B0107 (seed 601): sent to review; gain $65,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **fee_strip** on B0038 (seed 601): sent to review; gain $1,833,000 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **fee_strip** on B0082 (seed 601): sent to review; gain $1,670,500 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **ghost_vins** on B0051 (seed 601): missed; gain $73,404 (7% of the credit limit); findings: none
- **ghost_vins** on B0120 (seed 601): sent to review; gain $66,072 (7% of the credit limit); findings: HIDDEN_DEBT (low), RELATED_SHELLS (low)
- **month_end_cure** on B0106 (seed 601): sent to review; gain $7,474,947 (7% of the credit limit); findings: CASH_LEAKAGE (low)
- **month_end_cure** on B0057 (seed 601): sent to review; gain $661,809 (7% of the credit limit); findings: CASH_LEAKAGE (low), TAPE_DRESSUP (low)
- **offsheet_shells** on B0092 (seed 601): sent to review; gain $65,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **offsheet_shells** on B0014 (seed 601): sent to review; gain $611,000 (6% of the credit limit); findings: HIDDEN_DEBT (low), RELATED_SHELLS (low)
- **round_trip** on B0031 (seed 601): sent to review; gain $1,007,495 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **round_trip** on B0018 (seed 601): sent to review; gain $1,291,005 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **abs_overlap** on B0119 (seed 602): sent to review; gain $274,444 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **abs_overlap** on B0057 (seed 602): sent to review; gain $220,508 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **fee_strip** on B0078 (seed 602): sent to review; gain $669,500 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **fee_strip** on B0063 (seed 602): sent to review; gain $156,000 (6% of the credit limit); findings: CASH_LEAKAGE (low), HIDDEN_DEBT (low)
- **ghost_vins** on B0018 (seed 602): missed; gain $94,647 (7% of the credit limit); findings: none
- **ghost_vins** on B0010 (seed 602): sent to review; gain $96,902 (7% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **month_end_cure** on B0062 (seed 602): sent to review; gain $65,322 (7% of the credit limit); findings: CASH_LEAKAGE (low), FIN_MANIPULATION (low), TAPE_DRESSUP (low)
- **month_end_cure** on B0014 (seed 602): sent to review; gain $758,495 (7% of the credit limit); findings: CASH_LEAKAGE (low)
- **offsheet_shells** on B0097 (seed 602): sent to review; gain $1,326,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **round_trip** on B0050 (seed 602): sent to review; gain $1,305,724 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **round_trip** on B0037 (seed 602): sent to review; gain $1,574,199 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **abs_overlap** on B0093 (seed 603): sent to review; gain $333,564 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **double_pledge** on B0096 (seed 603): sent to review; gain $370,500 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **fee_strip** on B0027 (seed 603): sent to review; gain $84,500 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **fee_strip** on B0024 (seed 603): sent to review; gain $65,000 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **ghost_vins** on B0038 (seed 603): sent to review; gain $80,768 (7% of the credit limit); findings: HIDDEN_DEBT (low)
- **ghost_vins** on B0089 (seed 603): missed; gain $543,000 (7% of the credit limit); findings: none
- **month_end_cure** on B0075 (seed 603): sent to review; gain $817,716 (7% of the credit limit); findings: CASH_LEAKAGE (low), TAPE_DRESSUP (low)
- **month_end_cure** on B0010 (seed 603): sent to review; gain $383,074 (7% of the credit limit); findings: CASH_LEAKAGE (low), TAPE_DRESSUP (low)
- **offsheet_shells** on B0087 (seed 603): sent to review; gain $1,449,500 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **offsheet_shells** on B0031 (seed 603): sent to review; gain $2,151,500 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **round_trip** on B0098 (seed 603): sent to review; gain $966,376 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **round_trip** on B0068 (seed 603): sent to review; gain $1,396,907 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **abs_overlap** on B0103 (seed 604): sent to review; gain $666,014 (7% of the credit limit); findings: DOUBLE_PLEDGE (low), HIDDEN_DEBT (low)
- **abs_overlap** on B0064 (seed 604): sent to review; gain $331,530 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **fee_strip** on B0089 (seed 604): missed; gain $858,000 (6% of the credit limit); findings: none
- **fee_strip** on B0081 (seed 604): sent to review; gain $2,086,500 (6% of the credit limit); findings: CASH_LEAKAGE (low)
- **ghost_vins** on B0099 (seed 604): missed; gain $65,516 (7% of the credit limit); findings: none
- **ghost_vins** on B0061 (seed 604): missed; gain $782,728 (7% of the credit limit); findings: none
- **month_end_cure** on B0027 (seed 604): sent to review; gain $67,357 (7% of the credit limit); findings: CASH_LEAKAGE (low), HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **month_end_cure** on B0105 (seed 604): sent to review; gain $614,009 (7% of the credit limit); findings: CASH_LEAKAGE (low), DOUBLE_PLEDGE (low), HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **offsheet_shells** on B0069 (seed 604): sent to review; gain $260,000 (6% of the credit limit); findings: HIDDEN_DEBT (low), RELATED_SHELLS (low)
- **offsheet_shells** on B0034 (seed 604): sent to review; gain $292,500 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **round_trip** on B0082 (seed 604): sent to review; gain $1,940,465 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **round_trip** on B0086 (seed 604): sent to review; gain $633,167 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)
- **abs_overlap** on B0108 (seed 605): sent to review; gain $455,247 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **abs_overlap** on B0039 (seed 605): sent to review; gain $680,653 (7% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **double_pledge** on B0042 (seed 605): sent to review; gain $585,000 (6% of the credit limit); findings: CASH_LEAKAGE (low), HIDDEN_DEBT (low)
- **fee_strip** on B0111 (seed 605): sent to review; gain $1,423,500 (6% of the credit limit); findings: CASH_LEAKAGE (low), FIN_MANIPULATION (low), HIDDEN_DEBT (low)
- **fee_strip** on B0033 (seed 605): sent to review; gain $1,956,500 (6% of the credit limit); findings: CASH_LEAKAGE (low), HIDDEN_DEBT (low)
- **ghost_vins** on B0117 (seed 605): missed; gain $3,268,078 (7% of the credit limit); findings: none
- **ghost_vins** on B0093 (seed 605): missed; gain $344,933 (7% of the credit limit); findings: none
- **month_end_cure** on B0028 (seed 605): sent to review; gain $1,855,953 (7% of the credit limit); findings: CASH_LEAKAGE (low)
- **month_end_cure** on B0022 (seed 605): sent to review; gain $67,060 (7% of the credit limit); findings: CASH_LEAKAGE (low), HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **offsheet_shells** on B0002 (seed 605): sent to review; gain $65,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **offsheet_shells** on B0116 (seed 605): sent to review; gain $760,500 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **round_trip** on B0115 (seed 605): sent to review; gain $1,182,842 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **round_trip** on B0024 (seed 605): sent to review; gain $651,456 (7% of the credit limit); findings: CASH_LEAKAGE (low), FAKE_INVOICES (low)

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
