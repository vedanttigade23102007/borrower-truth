# Red team result: seeds 1001, 1002, 1003, 1004, 1005, scored once

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5; round 3: GPT-6 Astra (as shown in Codex), run by a friend on their own machine with no internet (Vedant, 2 Oct 2026)

**Caveat on comparing rounds.** Round 3's attacker is a different company's model (GPT-6 Astra in OpenAI Codex), so the "same family" limit of rounds 1 and 2 doesn't apply to it. The rounds are still not like for like. The rules changed between round 2 and round 3 (WHY.md changes 17–20). Round 3's attacks were also much smaller: 6–8% of the credit limit, just over the 5% floor, against 14–16% in round 2. And every one was a single burst at month 6.

Rules version ca03f77baae5 (frozen: ca03f77baae5); code 1b06de2.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| alias_participations | 10 | 0 | 5 | 5 | - | - | yes | no |
| capitalized_fees | 10 | 0 | 4 | 6 | - | - | yes | no |
| customer_roundtrip | 10 | 0 | 2 | 8 | - | - | no | no |
| hidden_affiliate_debt | 10 | 0 | 10 | 0 | - | - | no | no |
| invoice_uplift | 10 | 0 | 1 | 9 | - | - | no | no |
| shelf_orders | 10 | 0 | 6 | 4 | - | - | no | yes |
| **All counted attacks** | 60 | 0 | 28 | 32 | - | | | |
| **Without either partial lever** | 30 | 0 | 13 | 17 | - | | | |
| **With the servicer lever** | 20 | 0 | 9 | 11 | - | | | |
| **With the company-history lever** | 10 | 0 | 6 | 4 | - | | | |

Honest borrowers in the attacked books: 290. Flagged at month 24: 0; flagged in any month: 0; sent to review: 28.3 per 100.
The books' own planted frauds: 248/250 caught.

## Every red-team fraud not caught

- **alias_participations** on B0065 (seed 1001): missed; gain $84,001 (6% of the credit limit); findings: none
- **alias_participations** on B0010 (seed 1001): missed; gain $60,001 (6% of the credit limit); findings: none
- **capitalized_fees** on B0115 (seed 1001): missed; gain $60,001 (6% of the credit limit); findings: none
- **capitalized_fees** on B0004 (seed 1001): missed; gain $4,260,071 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0014 (seed 1001): missed; gain $1,260,000 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0032 (seed 1001): missed; gain $1,644,000 (6% of the credit limit); findings: none
- **hidden_affiliate_debt** on B0066 (seed 1001): sent to review; gain $3,072,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0021 (seed 1001): sent to review; gain $352,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0078 (seed 1001): missed; gain $1,908,000 (6% of the credit limit); findings: none
- **invoice_uplift** on B0068 (seed 1001): missed; gain $1,818,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0030 (seed 1001): sent to review; gain $1,320,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **shelf_orders** on B0002 (seed 1001): missed; gain $1,290,000 (6% of the credit limit); findings: none
- **alias_participations** on B0014 (seed 1002): missed; gain $3,888,065 (6% of the credit limit); findings: none
- **alias_participations** on B0051 (seed 1002): missed; gain $60,001 (6% of the credit limit); findings: none
- **capitalized_fees** on B0040 (seed 1002): missed; gain $360,006 (6% of the credit limit); findings: none
- **capitalized_fees** on B0022 (seed 1002): sent to review; gain $60,001 (6% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **customer_roundtrip** on B0015 (seed 1002): missed; gain $1,662,000 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0078 (seed 1002): missed; gain $930,000 (6% of the credit limit); findings: none
- **hidden_affiliate_debt** on B0023 (seed 1002): sent to review; gain $80,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0064 (seed 1002): sent to review; gain $2,256,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **invoice_uplift** on B0087 (seed 1002): missed; gain $1,122,000 (6% of the credit limit); findings: none
- **invoice_uplift** on B0062 (seed 1002): missed; gain $1,656,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0093 (seed 1002): missed; gain $1,032,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0038 (seed 1002): sent to review; gain $588,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **alias_participations** on B0086 (seed 1003): sent to review; gain $2,154,036 (6% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **alias_participations** on B0098 (seed 1003): missed; gain $4,080,068 (6% of the credit limit); findings: none
- **capitalized_fees** on B0055 (seed 1003): missed; gain $114,002 (6% of the credit limit); findings: none
- **capitalized_fees** on B0033 (seed 1003): sent to review; gain $444,007 (6% of the credit limit); findings: RELATED_SHELLS (low)
- **customer_roundtrip** on B0099 (seed 1003): missed; gain $726,000 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0053 (seed 1003): sent to review; gain $858,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0024 (seed 1003): sent to review; gain $1,872,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0009 (seed 1003): sent to review; gain $424,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0020 (seed 1003): missed; gain $1,866,000 (6% of the credit limit); findings: none
- **invoice_uplift** on B0061 (seed 1003): missed; gain $1,110,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0027 (seed 1003): sent to review; gain $720,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **shelf_orders** on B0084 (seed 1003): sent to review; gain $654,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **alias_participations** on B0015 (seed 1004): sent to review; gain $2,352,039 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **alias_participations** on B0095 (seed 1004): sent to review; gain $60,001 (6% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **capitalized_fees** on B0111 (seed 1004): sent to review; gain $3,120,052 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **capitalized_fees** on B0016 (seed 1004): missed; gain $822,014 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0045 (seed 1004): missed; gain $1,290,000 (6% of the credit limit); findings: none
- **customer_roundtrip** on B0109 (seed 1004): missed; gain $996,000 (6% of the credit limit); findings: none
- **hidden_affiliate_debt** on B0075 (seed 1004): sent to review; gain $160,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **hidden_affiliate_debt** on B0081 (seed 1004): sent to review; gain $88,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0114 (seed 1004): missed; gain $1,146,000 (6% of the credit limit); findings: none
- **invoice_uplift** on B0002 (seed 1004): sent to review; gain $1,560,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **shelf_orders** on B0084 (seed 1004): sent to review; gain $534,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **shelf_orders** on B0073 (seed 1004): missed; gain $1,248,000 (6% of the credit limit); findings: none
- **alias_participations** on B0022 (seed 1005): sent to review; gain $3,042,051 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **alias_participations** on B0009 (seed 1005): sent to review; gain $138,002 (6% of the credit limit); findings: DOUBLE_PLEDGE (low)
- **capitalized_fees** on B0001 (seed 1005): missed; gain $390,006 (6% of the credit limit); findings: none
- **capitalized_fees** on B0005 (seed 1005): sent to review; gain $4,326,072 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **customer_roundtrip** on B0100 (seed 1005): sent to review; gain $600,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)
- **customer_roundtrip** on B0044 (seed 1005): missed; gain $2,058,000 (6% of the credit limit); findings: none
- **hidden_affiliate_debt** on B0091 (seed 1005): sent to review; gain $4,272,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low), HIDDEN_DEBT (low)
- **hidden_affiliate_debt** on B0102 (seed 1005): sent to review; gain $6,672,000 (8% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **invoice_uplift** on B0063 (seed 1005): missed; gain $1,572,000 (6% of the credit limit); findings: none
- **invoice_uplift** on B0002 (seed 1005): missed; gain $1,110,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0080 (seed 1005): missed; gain $672,000 (6% of the credit limit); findings: none
- **shelf_orders** on B0068 (seed 1005): sent to review; gain $1,590,000 (6% of the credit limit); findings: HIDDEN_DEBT (low)

## Leak scan of the hand-in: 0 forbidden terms


## After scoring: what the attacks actually changed (diagnosis only, 2 Oct 2026; no code changed)

Everything above was written by the harness and committed unchanged (`21ca7c1`, pushed). This section was added later. **Round 3 is a measurement only** (WHY.md): no fixes before outreach.

**"Sent to review" overstates it.** About 28 of every 100 honest borrowers sit at review anyway, because of honest look-alikes. Each attacked borrower was compared with the same borrower in copy A, the same book without the attack, month by month (months 7–24). The question was whether the attack changed what an officer would see.

| Attack | Never changed, any month | Attack-caused review, some month | Attack-caused flag, some month |
|---|---|---|---|
| alias_participations | 7 | 3 | 0 |
| capitalized_fees | 10 | 0 | 0 |
| customer_roundtrip | 2 | 1 | 7 (months 11–14 only) |
| hidden_affiliate_debt | 3 | 7 | 0 |
| invoice_uplift | 2 | 8 (months 11–14 only) | 0 |
| shelf_orders | 6 | 4 (months 10–16 only) | 0 |
| **All 60** | **30** | **23** | **7** |

At month 24, 12 of the 28 reviews carry a finding the same borrower doesn't have without the attack. The other 16 would have been at review anyway.

**What each attack exposed:**
- **capitalized_fees: never seen (uses the servicer lever).** Fees were added into real loans' balances, in the tape and in the servicer system alike. No check follows a loan's balance against the payments the bank actually received (a balance roll-forward). A current loan's balance only goes down, so one that rises with no new money lent is the examiner's tell.
- **alias_participations: 7 never seen (uses the servicer lever).** "Participations" were split off real loans under new IDs, with the same VIN and the same customer, in the same facility. The duplicate check looks for a VIN in two facilities, not twice in one.
- **customer_roundtrip, invoice_uplift, shelf_orders: seen for a few months, then forgotten.**
  - Each was a single burst at month 6, and the fake or inflated invoices stay in the borrowing base.
  - The checks look back over recent months only (the past 3–9 months, depending on the check), so the evidence ages out while the collateral is still pledged.
  - `customer_roundtrip` was flagged as likely fraud at months 11–14. The clues were the dilution check (change 18), an invoice far above the customer's usual size, and receivables quality. From month 17 it showed nothing.
  - In a bank, the case would have been opened at month 11 and stayed open in the case service. The month-24 score doesn't count that, but the forgetting is a real weakness.
- **hidden_affiliate_debt: sent to review, as in round 2 (`shell_roundtrip`).** Money arrives from a new company in a nominee's name, with no link to the owner in any table. This is already a known limit; ownership records are the data-contract answer.

**What this doesn't change:** copy A, the books as generated, passes the bar (`proof/REPORT_seeds1001-1005.md`): 248/250 caught, 0 of 350 honest flagged in any month, 28.6 per 100 sent to review, and every check ran.

**Proposed, for Vedant to confirm (no fixes before outreach):**
- **On the list for after outreach,** each a mechanism a credit officer knows:
  1. a balance roll-forward against the bank's own receipts (capitalized_fees)
  2. the same VIN or customer pledged twice in one facility (alias_participations)
  3. evidence stays in scope as long as the collateral is still pledged, not for a fixed number of months (customer_roundtrip, invoice_uplift, shelf_orders)
- **Known limit, already recorded:** a nominee company with no link to the owner in any table (hidden_affiliate_debt).
