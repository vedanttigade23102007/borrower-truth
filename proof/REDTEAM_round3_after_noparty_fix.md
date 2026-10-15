# Red team result: seeds 1301, 1302, 1303, 1304, 1305, scored once (after change 32 (no-counterparty clues): these attacks are no longer blind)

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5; round 3: GPT-6 Astra (as shown in Codex), run by a friend on their own machine with no internet (Vedant, 2 Oct 2026)

**after change 32 (no-counterparty clues): these attacks are no longer blind.** The rules were fixed after round 1 of these same attacks was scored, so this run is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.

Rules version c147a0a636e6 (frozen: c147a0a636e6); code 4ba3293.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| alias_participations | 10 | 10 | 0 | 0 | 0 | - | yes | no |
| capitalized_fees | 10 | 0 | 10 | 0 | - | - | yes | no |
| customer_roundtrip | 10 | 10 | 0 | 0 | 4 | - | no | no |
| hidden_affiliate_debt | 10 | 0 | 10 | 0 | - | - | no | no |
| invoice_uplift | 10 | 0 | 10 | 0 | - | - | no | no |
| shelf_orders | 10 | 0 | 10 | 0 | - | - | no | yes |
| **All counted attacks** | 60 | 20 | 40 | 0 | 4 | | | |
| **Without either partial lever** | 30 | 10 | 20 | 0 | 4 | | | |
| **With the servicer lever** | 20 | 10 | 10 | 0 | 0 | | | |
| **With the company-history lever** | 10 | 0 | 10 | 0 | - | | | |

Honest borrowers in the attacked books: 290. Flagged at month 24: 0; flagged in any month: 1; sent to review: 30.7 per 100.
The books' own planted frauds: 249/250 caught.

## Every red-team fraud not caught

- **capitalized_fees** on B0099 (seed 1301): sent to review; gain $858,014 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0088 (seed 1301): sent to review; gain $300,005 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0097 (seed 1301): sent to review; gain $312,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0054 (seed 1301): sent to review; gain $2,920,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0001 (seed 1301): sent to review; gain $2,010,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0006 (seed 1301): sent to review; gain $1,554,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0036 (seed 1301): sent to review; gain $1,890,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low), RELATED_SHELLS (low)
- **shelf_orders** on B0053 (seed 1301): sent to review; gain $1,368,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0030 (seed 1302): sent to review; gain $618,010 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0106 (seed 1302): sent to review; gain $588,010 (6% of the credit limit); findings: DOUBLE_PLEDGE (low), TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0116 (seed 1302): sent to review; gain $2,080,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0105 (seed 1302): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0114 (seed 1302): sent to review; gain $366,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0087 (seed 1302): sent to review; gain $1,014,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **shelf_orders** on B0073 (seed 1302): sent to review; gain $1,110,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0079 (seed 1302): sent to review; gain $714,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0063 (seed 1303): sent to review; gain $2,676,045 (6% of the credit limit); findings: HIDDEN_DEBT (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0095 (seed 1303): sent to review; gain $60,001 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0086 (seed 1303): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0001 (seed 1303): sent to review; gain $568,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0105 (seed 1303): sent to review; gain $1,278,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0023 (seed 1303): sent to review; gain $1,026,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0055 (seed 1303): sent to review; gain $582,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0028 (seed 1303): sent to review; gain $1,218,000 (6% of the credit limit); findings: FAKE_INVOICES (low), FIN_MANIPULATION (low)
- **capitalized_fees** on B0117 (seed 1304): sent to review; gain $1,416,024 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **capitalized_fees** on B0111 (seed 1304): sent to review; gain $114,002 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0005 (seed 1304): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0017 (seed 1304): sent to review; gain $808,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0014 (seed 1304): sent to review; gain $1,836,000 (6% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0006 (seed 1304): sent to review; gain $960,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0038 (seed 1304): sent to review; gain $1,458,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0094 (seed 1304): sent to review; gain $1,152,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **capitalized_fees** on B0072 (seed 1305): sent to review; gain $102,002 (6% of the credit limit); findings: HIDDEN_DEBT (low), RELATED_SHELLS (low), TAPE_DRESSUP (low)
- **capitalized_fees** on B0075 (seed 1305): sent to review; gain $276,005 (6% of the credit limit); findings: TAPE_DRESSUP (low)
- **hidden_affiliate_debt** on B0074 (seed 1305): sent to review; gain $1,640,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0112 (seed 1305): sent to review; gain $1,568,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0014 (seed 1305): sent to review; gain $864,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_uplift** on B0043 (seed 1305): sent to review; gain $534,000 (6% of the credit limit); findings: FAKE_INVOICES (low)
- **shelf_orders** on B0063 (seed 1305): sent to review; gain $1,662,000 (6% of the credit limit); findings: FAKE_INVOICES (low), RELATED_SHELLS (low)
- **shelf_orders** on B0064 (seed 1305): sent to review; gain $1,284,000 (6% of the credit limit); findings: FAKE_INVOICES (low)

## Leak scan of the hand-in: 0 forbidden terms

