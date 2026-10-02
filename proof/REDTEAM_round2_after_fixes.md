# Red team result: seeds 801, 802, 803, 804, 805, scored once (after the round-2 fixes: these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5 (as Vedant reported on 2 Oct 2026, after scoring; recorded here afterwards)

**Caveat on comparing round 1 with round 2 (added 2 Oct 2026, at Vedant's request).** Round 2's attacker (Sonnet 5.5) may have been a weaker model than round 1's (Opus 5), so part of the improvement from round 1 to round 2 may come from that. The rules of the test also changed in between, in both directions. Credit limits were sized to each borrower's own collateral, so an attack worth 5% of the limit became a smaller share of the book, which is harder to catch. The payer rule took away recording money under a false sender, which is easier to catch. The rounds are not like for like. Both rounds used Claude models, the same family as the model that helped write the checks, so the "same family" limit still stands.

**after the round-2 fixes: these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version 4f2503e6bfa4 (frozen: 4f2503e6bfa4); code c2742b1.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| fictitious_deferment | 10 | 8 | 2 | 0 | 6 | - | yes | no |
| ghost_invoices | 10 | 1 | 9 | 0 | 7 | - | no | no |
| invoice_inflation | 10 | 0 | 10 | 0 | - | - | no | no |
| phantom_collateral | 10 | 10 | 0 | 0 | 0 | - | no | no |
| seasoned_phantoms | 10 | 10 | 0 | 0 | 0 | - | no | no |
| shadow_repledge | 10 | 10 | 0 | 0 | 0 | - | no | no |
| shell_roundtrip | 10 | 0 | 10 | 0 | - | - | no | yes |
| **All counted attacks** | 70 | 39 | 31 | 0 | 0 | | | |
| **Without either partial lever** | 50 | 31 | 19 | 0 | 0 | | | |
| **With the servicer lever** | 10 | 8 | 2 | 0 | 6 | | | |
| **With the company-history lever** | 10 | 0 | 10 | 0 | - | | | |

Honest borrowers in the attacked books: 280. Flagged at month 24: 1; flagged in any month: 1; sent to review: 31.8 per 100.
The books' own planted frauds: 249/250 caught.

## Every red-team fraud not caught

- **ghost_invoices** on B0096 (seed 801): sent to review; gain $3,052,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0101 (seed 801): sent to review; gain $5,310,734 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0083 (seed 801): sent to review; gain $4,911,436 (14% of the credit limit); findings: FAKE_INVOICES (low), RELATED_SHELLS (low)
- **shell_roundtrip** on B0097 (seed 801): sent to review; gain $162,476 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), RELATED_SHELLS (low)
- **shell_roundtrip** on B0059 (seed 801): sent to review; gain $156,497 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **ghost_invoices** on B0099 (seed 802): sent to review; gain $3,374,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0090 (seed 802): sent to review; gain $2,310,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0053 (seed 802): sent to review; gain $1,554,573 (15% of the credit limit); findings: FAKE_INVOICES (low), FIN_MANIPULATION (low)
- **invoice_inflation** on B0012 (seed 802): sent to review; gain $2,451,945 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **shell_roundtrip** on B0011 (seed 802): sent to review; gain $4,119,498 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0013 (seed 802): sent to review; gain $162,004 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **fictitious_deferment** on B0034 (seed 803): sent to review; gain $1,670,828 (7% of the credit limit); findings: TAPE_DRESSUP (low)
- **ghost_invoices** on B0083 (seed 803): sent to review; gain $4,368,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0017 (seed 803): sent to review; gain $5,320,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0005 (seed 803): sent to review; gain $3,053,540 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0007 (seed 803): sent to review; gain $1,936,523 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0044 (seed 803): sent to review; gain $4,372,670 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0052 (seed 803): sent to review; gain $4,453,746 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), FIN_MANIPULATION (low)
- **fictitious_deferment** on B0049 (seed 804): sent to review; gain $2,764,810 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **ghost_invoices** on B0033 (seed 804): sent to review; gain $4,200,000 (14% of the credit limit); findings: FAKE_INVOICES (low), FIN_MANIPULATION (low), HIDDEN_DEBT (low)
- **ghost_invoices** on B0076 (seed 804): sent to review; gain $4,788,000 (14% of the credit limit); findings: FAKE_INVOICES (low), FIN_MANIPULATION (low), HIDDEN_DEBT (low)
- **invoice_inflation** on B0001 (seed 804): sent to review; gain $2,510,301 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_inflation** on B0106 (seed 804): sent to review; gain $3,771,694 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0079 (seed 804): sent to review; gain $786,834 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0118 (seed 804): sent to review; gain $609,541 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **ghost_invoices** on B0022 (seed 805): sent to review; gain $2,604,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0108 (seed 805): sent to review; gain $2,716,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0097 (seed 805): sent to review; gain $4,956,818 (14% of the credit limit); findings: FAKE_INVOICES (low), RELATED_SHELLS (low)
- **invoice_inflation** on B0074 (seed 805): sent to review; gain $3,482,015 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **shell_roundtrip** on B0109 (seed 805): sent to review; gain $3,061,801 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0113 (seed 805): sent to review; gain $2,615,863 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)

## Leak scan of the hand-in: 2 forbidden terms

- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …d["borrower_id"] == borrower_id and d["kind"] == "deferment_program" for d in disc):         disc.append({"borrower_i…
- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …disc.append({"borrower_id": borrower_id, "kind": "deferment_program", "counterparty_entity_id": None,                …
