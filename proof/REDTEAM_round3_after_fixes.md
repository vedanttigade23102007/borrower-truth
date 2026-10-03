# Red team result: seeds 1101, 1102, 1103, 1104, 1105, scored once (after the round-3 fixes: these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5; round 3: GPT-6 Astra (as shown in Codex), run by a friend on their own machine with no internet (Vedant, 2 Oct 2026)

**after the round-3 fixes: these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version a88b4d4f561f (frozen: a88b4d4f561f); code 686b748.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| alias_participations | 10 | 10 | 0 | 0 | 0 | - | yes | no |
| capitalized_fees | 10 | 0 | 10 | 0 | - | - | yes | no |
| customer_roundtrip | 10 | 8 | 2 | 0 | 4 | - | no | no |
| hidden_affiliate_debt | 10 | 0 | 10 | 0 | - | - | no | no |
| invoice_uplift | 10 | 0 | 10 | 0 | - | - | no | no |
| shelf_orders | 10 | 0 | 10 | 0 | - | - | no | yes |
| **All counted attacks** | 60 | 18 | 42 | 0 | 0 | | | |
| **Without either partial lever** | 30 | 8 | 22 | 0 | 4 | | | |
| **With the servicer lever** | 20 | 10 | 10 | 0 | 0 | | | |
| **With the company-history lever** | 10 | 0 | 10 | 0 | - | | | |

Honest borrowers in the attacked books: 290. Flagged at month 24: 0; flagged in any month: 0; sent to review: 30.0 per 100.
The books' own planted frauds: 250/250 caught.

## Every red-team fraud not caught

- **capitalized_fees** on B0080 (seed 1101): sent to review; gain $156,003 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0053 (seed 1101): sent to review; gain $390,006 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0018 (seed 1101): sent to review; gain $6,696,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0029 (seed 1101): sent to review; gain $5,504,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0054 (seed 1101): sent to review; gain $582,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0109 (seed 1101): sent to review; gain $1,422,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0023 (seed 1101): sent to review; gain $1,692,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0050 (seed 1101): sent to review; gain $1,644,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0034 (seed 1102): sent to review; gain $636,011 (6% of the credit limit); findings: HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0075 (seed 1102): sent to review; gain $5,196,087 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **customer_roundtrip** on B0022 (seed 1102): sent to review; gain $1,212,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0107 (seed 1102): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), RELATED_SHELLS (low)
- **hidden_affiliate_debt** on B0079 (seed 1102): sent to review; gain $320,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0014 (seed 1102): sent to review; gain $1,716,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0091 (seed 1102): sent to review; gain $1,494,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0052 (seed 1102): sent to review; gain $636,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0039 (seed 1102): sent to review; gain $1,434,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0043 (seed 1103): sent to review; gain $348,006 (6% of the credit limit); findings: RELATED_SHELLS (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0033 (seed 1103): sent to review; gain $3,150,052 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0114 (seed 1103): sent to review; gain $424,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0053 (seed 1103): sent to review; gain $768,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0021 (seed 1103): sent to review; gain $876,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0023 (seed 1103): sent to review; gain $1,248,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0016 (seed 1103): sent to review; gain $1,248,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0069 (seed 1103): sent to review; gain $1,968,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **capitalized_fees** on B0075 (seed 1104): sent to review; gain $1,662,028 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0042 (seed 1104): sent to review; gain $66,001 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **customer_roundtrip** on B0031 (seed 1104): sent to review; gain $1,284,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **hidden_affiliate_debt** on B0030 (seed 1104): sent to review; gain $2,232,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0001 (seed 1104): sent to review; gain $4,368,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0082 (seed 1104): sent to review; gain $1,416,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0069 (seed 1104): sent to review; gain $1,248,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0040 (seed 1104): sent to review; gain $1,998,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0053 (seed 1104): sent to review; gain $1,086,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0022 (seed 1105): sent to review; gain $660,011 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0118 (seed 1105): sent to review; gain $282,005 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low), TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0017 (seed 1105): sent to review; gain $1,152,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0050 (seed 1105): sent to review; gain $7,352,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0038 (seed 1105): sent to review; gain $1,182,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0115 (seed 1105): sent to review; gain $1,674,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shelf_orders** on B0034 (seed 1105): sent to review; gain $1,140,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0090 (seed 1105): sent to review; gain $918,000 (6% of the credit limit); findings: FAKE_INVOICES (low)

## Leak scan of the hand-in: 0 forbidden terms

