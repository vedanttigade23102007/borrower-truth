# Red team result: seeds 1201, 1202, 1203, 1204, 1205, scored once (after the claims fix: these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5; round 3: GPT-6 Astra (as shown in Codex), run by a friend on their own machine with no internet (Vedant, 2 Oct 2026)

**after the claims fix: these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version bfe7200495c4 (frozen: bfe7200495c4); code 8eb8acb.

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

Honest borrowers in the attacked books: 290. Flagged at month 24: 0; flagged in any month: 0; sent to review: 29.0 per 100.
The books' own planted frauds: 248/250 caught.

## Every red-team fraud not caught

- **capitalized_fees** on B0041 (seed 1201): sent to review; gain $354,006 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0064 (seed 1201): sent to review; gain $372,006 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0089 (seed 1201): sent to review; gain $480,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0004 (seed 1201): sent to review; gain $744,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), DOUBLE_PLEDGE (low)
- **invoice_uplift** on B0087 (seed 1201): sent to review; gain $882,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0050 (seed 1201): sent to review; gain $1,674,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0047 (seed 1201): sent to review; gain $1,110,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0008 (seed 1201): sent to review; gain $1,770,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0068 (seed 1202): sent to review; gain $282,005 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0096 (seed 1202): sent to review; gain $414,007 (6% of the credit limit); findings: RELATED_SHELLS (low), TAPE_DRESSUP (low)
- **customer_roundtrip** on B0120 (seed 1202): sent to review; gain $1,914,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **hidden_affiliate_debt** on B0109 (seed 1202): sent to review; gain $3,848,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0091 (seed 1202): sent to review; gain $2,864,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0037 (seed 1202): sent to review; gain $1,200,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0005 (seed 1202): sent to review; gain $552,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0076 (seed 1202): sent to review; gain $330,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shelf_orders** on B0001 (seed 1202): sent to review; gain $1,548,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0084 (seed 1203): sent to review; gain $60,001 (6% of the credit limit); findings: HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0112 (seed 1203): sent to review; gain $1,926,032 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0050 (seed 1203): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0063 (seed 1203): sent to review; gain $136,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0037 (seed 1203): sent to review; gain $1,002,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0065 (seed 1203): sent to review; gain $2,310,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0071 (seed 1203): sent to review; gain $1,698,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0110 (seed 1203): sent to review; gain $684,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0040 (seed 1204): sent to review; gain $60,001 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0001 (seed 1204): sent to review; gain $1,488,025 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low), TAPE_DRESSUP (low)
- **customer_roundtrip** on B0118 (seed 1204): sent to review; gain $336,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0041 (seed 1204): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0069 (seed 1204): sent to review; gain $7,312,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0101 (seed 1204): sent to review; gain $924,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0043 (seed 1204): sent to review; gain $1,356,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0088 (seed 1204): sent to review; gain $1,452,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0024 (seed 1204): sent to review; gain $792,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0003 (seed 1205): sent to review; gain $1,134,019 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0066 (seed 1205): sent to review; gain $66,001 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low), TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0065 (seed 1205): sent to review; gain $824,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0064 (seed 1205): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0034 (seed 1205): sent to review; gain $1,584,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0099 (seed 1205): sent to review; gain $1,866,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0113 (seed 1205): sent to review; gain $2,874,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0004 (seed 1205): sent to review; gain $882,000 (6% of the credit limit); findings: FAKE_INVOICES (low)

## Leak scan of the hand-in: 0 forbidden terms

