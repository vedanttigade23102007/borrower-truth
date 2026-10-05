# Red team result: seeds 901, 902, 903, 904, 905, scored once (after the round-2 fixes and the timing rule: these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5 (as Vedant reported on 2 Oct 2026, after scoring; recorded here afterwards)

**Caveat on comparing round 1 with round 2 (added 2 Oct 2026, at Vedant's request; first sentence corrected 5 Oct 2026).** Rounds 1 and 2 used different Claude models (Opus 5, then Sonnet 5.5); which is stronger wasn't measured, so the rounds aren't a clean comparison of the fixes. The rules of the test also changed in between, in both directions. Credit limits were sized to each borrower's own collateral, so an attack worth 5% of the limit became a smaller share of the book, which is harder to catch. The payer rule took away recording money under a false sender, which is easier to catch. The rounds are not like for like. Both rounds used Claude models, the same family as the model that helped write the checks, so the "same family" limit still stands.

**after the round-2 fixes and the timing rule: these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version d7b1caf7a0b8 (frozen: d7b1caf7a0b8); code 3bad49b.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| fictitious_deferment | 10 | 10 | 0 | 0 | 5 | - | yes | no |
| ghost_invoices | 10 | 3 | 7 | 0 | 7 | - | no | no |
| invoice_inflation | 10 | 0 | 10 | 0 | - | - | no | no |
| phantom_collateral | 10 | 10 | 0 | 0 | 0 | - | no | no |
| seasoned_phantoms | 10 | 10 | 0 | 0 | 0 | - | no | no |
| shadow_repledge | 10 | 10 | 0 | 0 | 0 | - | no | no |
| shell_roundtrip | 10 | 0 | 10 | 0 | - | - | no | yes |
| **All counted attacks** | 70 | 43 | 27 | 0 | 0 | | | |
| **Without either partial lever** | 50 | 33 | 17 | 0 | 0 | | | |
| **With the servicer lever** | 10 | 10 | 0 | 0 | 5 | | | |
| **With the company-history lever** | 10 | 0 | 10 | 0 | - | | | |

Honest borrowers in the attacked books: 280. Flagged at month 24: 0; flagged in any month: 0; sent to review: 28.6 per 100.
The books' own planted frauds: 248/250 caught.

## Every red-team fraud not caught

- **ghost_invoices** on B0047 (seed 901): sent to review; gain $2,058,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0085 (seed 901): sent to review; gain $2,401,392 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0021 (seed 901): sent to review; gain $3,935,294 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low), RELATED_SHELLS (low)
- **shell_roundtrip** on B0080 (seed 901): sent to review; gain $161,319 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0055 (seed 901): sent to review; gain $1,425,452 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **ghost_invoices** on B0039 (seed 902): sent to review; gain $3,766,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0078 (seed 902): sent to review; gain $1,386,000 (14% of the credit limit); findings: DISGUISED_RECEIPTS (low), FAKE_INVOICES (low)
- **invoice_inflation** on B0114 (seed 902): sent to review; gain $2,764,843 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0060 (seed 902): sent to review; gain $3,097,804 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **shell_roundtrip** on B0051 (seed 902): sent to review; gain $2,836,350 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0071 (seed 902): sent to review; gain $2,076,056 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **ghost_invoices** on B0015 (seed 903): sent to review; gain $1,904,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0088 (seed 903): sent to review; gain $3,133,403 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0065 (seed 903): sent to review; gain $2,330,626 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **shell_roundtrip** on B0010 (seed 903): sent to review; gain $4,312,072 (15% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0091 (seed 903): sent to review; gain $363,778 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **ghost_invoices** on B0108 (seed 904): sent to review; gain $2,310,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0014 (seed 904): sent to review; gain $2,802,954 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0111 (seed 904): sent to review; gain $1,324,408 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shell_roundtrip** on B0020 (seed 904): sent to review; gain $1,376,816 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0019 (seed 904): sent to review; gain $301,737 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **ghost_invoices** on B0085 (seed 905): sent to review; gain $5,012,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0007 (seed 905): sent to review; gain $2,464,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0018 (seed 905): sent to review; gain $3,780,092 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_inflation** on B0001 (seed 905): sent to review; gain $2,470,796 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **shell_roundtrip** on B0025 (seed 905): sent to review; gain $3,614,482 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0067 (seed 905): sent to review; gain $4,085,524 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)

## Leak scan of the hand-in: 2 forbidden terms

- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …d["borrower_id"] == borrower_id and d["kind"] == "deferment_program" for d in disc):         disc.append({"borrower_i…
- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …disc.append({"borrower_id": borrower_id, "kind": "deferment_program", "counterparty_entity_id": None,                …
