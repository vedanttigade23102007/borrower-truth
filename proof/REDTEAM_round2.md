# Red team result: seeds 701, 702, 703, 704, 705, scored once

**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules (RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.

**Attacker models:** round 1: Opus 5; round 2: Sonnet 5.5 (as Vedant reported on 2 Oct 2026, after scoring; recorded here afterwards)

Rules version cdf8b9b94a09 (frozen: cdf8b9b94a09); code f5b95b9.

Counted: frauds gaining at least 5% of the borrower's credit limit. Smaller ones are shown apart, as "too small to matter".

| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |
|---|---|---|---|---|---|---|---|---|
| fictitious_deferment | 10 | 10 | 0 | 0 | 11 | - | yes | no |
| ghost_invoices | 10 | 4 | 6 | 0 | 9 | - | no | no |
| invoice_inflation | 10 | 0 | 1 | 9 | - | - | no | no |
| phantom_collateral | 10 | 10 | 0 | 0 | 0 | - | no | no |
| seasoned_phantoms | 10 | 8 | 0 | 2 | 0 | - | no | no |
| shadow_repledge | 10 | 10 | 0 | 0 | 0 | - | no | no |
| shell_roundtrip | 10 | 0 | 10 | 0 | - | - | no | yes |
| **All counted attacks** | 70 | 42 | 17 | 11 | 0 | | | |
| **Without either partial lever** | 50 | 32 | 7 | 11 | 0 | | | |
| **With the servicer lever** | 10 | 10 | 0 | 0 | 11 | | | |
| **With the company-history lever** | 10 | 0 | 10 | 0 | - | | | |

Honest borrowers in the attacked books: 280. Flagged at month 24: 1; flagged in any month: 1; sent to review: 28.2 per 100.
The books' own planted frauds: 249/250 caught.

## Every red-team fraud not caught

- **invoice_inflation** on B0018 (seed 701): missed; gain $968,078 (14% of the credit limit); findings: none
- **invoice_inflation** on B0031 (seed 701): missed; gain $3,110,889 (14% of the credit limit); findings: none
- **seasoned_phantoms** on B0061 (seed 701): missed; gain $570,036 (11% of the credit limit); findings: none
- **shell_roundtrip** on B0025 (seed 701): sent to review; gain $8,156,875 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0089 (seed 701): sent to review; gain $5,043,767 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **ghost_invoices** on B0106 (seed 702): sent to review; gain $4,466,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0007 (seed 702): sent to review; gain $5,867,932 (14% of the credit limit); findings: HIDDEN_DEBT (low)
- **invoice_inflation** on B0029 (seed 702): missed; gain $1,760,798 (14% of the credit limit); findings: none
- **shell_roundtrip** on B0085 (seed 702): sent to review; gain $162,049 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0099 (seed 702): sent to review; gain $6,009,652 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **ghost_invoices** on B0040 (seed 703): sent to review; gain $2,716,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0109 (seed 703): sent to review; gain $2,968,000 (14% of the credit limit); findings: FAKE_INVOICES (low), HIDDEN_DEBT (low)
- **invoice_inflation** on B0085 (seed 703): missed; gain $4,230,933 (14% of the credit limit); findings: none
- **invoice_inflation** on B0037 (seed 703): missed; gain $4,846,566 (14% of the credit limit); findings: none
- **shell_roundtrip** on B0056 (seed 703): sent to review; gain $1,081,783 (17% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0018 (seed 703): sent to review; gain $256,384 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **ghost_invoices** on B0059 (seed 704): sent to review; gain $2,996,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **ghost_invoices** on B0038 (seed 704): sent to review; gain $2,422,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0067 (seed 704): missed; gain $2,667,284 (14% of the credit limit); findings: none
- **invoice_inflation** on B0053 (seed 704): missed; gain $2,642,583 (14% of the credit limit); findings: none
- **seasoned_phantoms** on B0077 (seed 704): missed; gain $905,591 (12% of the credit limit); findings: none
- **shell_roundtrip** on B0005 (seed 704): sent to review; gain $186,556 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0027 (seed 704): sent to review; gain $162,171 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low), FIN_MANIPULATION (low)
- **ghost_invoices** on B0016 (seed 705): sent to review; gain $2,464,000 (14% of the credit limit); findings: FAKE_INVOICES (low)
- **invoice_inflation** on B0002 (seed 705): missed; gain $2,682,129 (14% of the credit limit); findings: none
- **invoice_inflation** on B0098 (seed 705): missed; gain $2,649,179 (14% of the credit limit); findings: none
- **shell_roundtrip** on B0085 (seed 705): sent to review; gain $3,215,929 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)
- **shell_roundtrip** on B0087 (seed 705): sent to review; gain $2,700,383 (16% of the credit limit); findings: DISGUISED_RECEIPTS (low)

## Leak scan of the hand-in: 2 forbidden terms

- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …d["borrower_id"] == borrower_id and d["kind"] == "deferment_program" for d in disc):         disc.append({"borrower_i…
- `attacks/fictitious_deferment/plant.py`: DEFERMENT_PROGRAM: …disc.append({"borrower_id": borrower_id, "kind": "deferment_program", "counterparty_entity_id": None,                …

## After scoring: what caused each miss (diagnosis only, 2 Oct 2026; no code changed)

Everything above this line was written by the harness and committed unchanged (fba807e, pushed before this section). This section was added later. Causes were worked out on the dev books (7, 101–105), with the same seven attacks planted there: caught 45, review 26, missed 13 of 84, close to the fresh result. The one exception is the honest flag below, which was read on seed 701 itself, read-only.

**The one honest borrower flagged (B0100, seed 701, in both copies): a name mix-up.**
- A $6.46M judgment names "Magnolia Holdings Group LLC". Three registered companies in that book have that exact name: B0100's parent, another borrower, and a third company's parent.
- Court records carry a name only, with no address, so the check gave the judgment to all three. Lien filings carry an address, and there the check already picks the right company. Judgments had no such tie-breaker.
- Without that judgment, B0100 has only an old pre-onboarding lien and a $28k landlord judgment. Those would send it to review, not flag it.
- On the dev books, judgments under a shared name happen 2 times in 67, never above $1M. That's why the dev bars never showed it.

**invoice_inflation (0 caught, 1 review, 9 missed): nothing compares what a customer pays with what the invoice says.**
- The customer pays the real amount, so each inflated invoice is paid about 38% short.
- No check measures dilution (the share of invoice value that never arrives as cash).
- On the dev books, the attacked borrowers' dilution rose 2.4 points (median) against their own first six months. Honest borrowers moved at most 0.5 points.
- Caveat: real dilution (returns, credits, disputes) is noisier than this generator's. The line would have to be set on real receivables data, which we don't have.

**seasoned_phantoms (8 caught, 2 missed): the servicer-system pull is a random sample.**
- Six large fake loans in a big book can escape a random pull.
- Because they are paid (the money comes from the borrower, through the customers), the pull aimed at unpaid loans skips them.
- The 8 caught were caught by the random pull hitting them.

**ghost_invoices (4 caught, 6 sent to review):** the never-paid invoices are found every time (12 of 12 on dev). That is one source alone, so it goes to review, where the check step is to confirm the invoices with the customers.

**shell_roundtrip (0 caught, 10 sent to review; uses the company-history lever):** the receipts with no invoice or loan behind them are found every time. The payer is a backdated company in a nominee's name with no link to the owner in any table, so there is no second source.

**Leak scan of the hand-in:** the 2 hits are the disclosure kind `deferment_program`, which the table guide documents (`TABLES.md`). Not a leak.
