# Data contract: what Borrower Truth needs from a bank

REVIEW.md gap 5. Written on 1 Oct 2026. It answers an architect's first question: *what do I have to plug in, and what works on day one with what we already have?*

The same contract is written in code in `bt/pipeline/contract.py`, so the document and the system can't drift apart. Tests: `tests/test_fallbacks.py`.

All data in this project is synthetic. The layouts below are the ones the checks read today.

---

## The three rules

1. **A missing input is never a clean result.** A file that never arrived isn't the same as a file with nothing in it.
   - A check that can't run without an input is **not run**, and every case says so.
   - A check that can run without an optional input runs **partially**. Every case says what wasn't checked.
2. **A missing input never invents a clue.** Where an empty table would make up findings, those findings are dropped.
3. **A delivered file with no rows is fine.** It means there is nothing to report, for example a bank with no invoice-finance borrowers.

**Why these rules exist.** Before 1 Oct, a missing file was read as an empty table, and every check still said "ok". Measured on dev book 7 (120 borrowers, 50 planted frauds; a tuning book, not a public number):

| Input removed | What happened | What the cases said |
|---|---|---|
| Loan tape | Frauds caught: 50 → 37. S3 clues: 24 → 2,030, because payments could no longer be matched to a customer. "Worth a look": 14 → 65. | every check "ok" |
| Servicer-system records | **47 honest borrowers flagged as likely fraud**: every loan pulled from the servicer system looked "gone" | every check "ok" |
| Operating-account outflows | Frauds caught: 50 → 46 (the round trips were lost) | every check "ok" |
| PledgeCheck results | All 120 borrowers noted "not enrolled in PledgeCheck" (53 really were) | every check "ok" |

After the fix, each of these shows on every case. For example: *"S2 (Tape vs source): partial: servicer-system pulls not checked (servicer-system records not delivered)"*. No made-up clue gets through. On complete books nothing changed: the demo replays 120 of 120 decisions identically, and the dev books still catch 298 of 300 with 0 honest borrowers flagged.

---

## The inputs

The run is monthly ("as of" a month). Payments also stream daily for live alerts.

| Input | What it is | Who supplies it | How often | Does the bank already have it? |
|---|---|---|---|---|
| Borrower list | the non-bank lenders the bank lends to | the bank (loan system) | on change | yes |
| Credit lines | each facility, its limit and advance rate | the bank | on change | yes |
| Collection-account payments | money arriving in the account the bank controls | the bank | daily | yes, under cash dominion |
| Borrower disclosures | debts, affiliates and payment-pause programmes the borrower told the bank about | the borrower, via onboarding and compliance certificates | on change, at least quarterly | yes, but usually as documents that need to be turned into data |
| Financial statements | revenue, receivables, debt and the covenant figure | the borrower | quarterly | yes |
| Loan tape | every pledged loan: status, balance, attributes | the borrower (borrowing-base report) | monthly | yes |
| Pledged invoices | every pledged invoice: number, customer, amount | the borrower (borrowing-base report) | monthly | yes, for invoice-finance borrowers |
| Servicer-system records | the same loans, read from the system the borrower services them in | the servicer, pulled by the bank under its audit rights | monthly sample | only through field exams today |
| Operating-account outflows | money leaving the borrower's own operating account | the bank, if it holds that account; otherwise the borrower's bank statements | monthly | only if the bank holds the account |
| Company registry | companies, officers, addresses, phone numbers, registered agents | state business registries, usually through a data vendor | monthly | sometimes, through KYC tools |
| Officers and owners | the people behind the companies | registry and KYC | monthly | partly |
| LEI register (GLEIF) | which companies have a Legal Entity Identifier | GLEIF (public, free) | monthly | free to fetch |
| Lien filings | UCC filings naming the borrower or a linked company | state filing offices, through a lien-search vendor | monthly | often, as one-off searches; a monthly feed is a licence (gap 8) |
| Court judgments | judgments against the borrower or a linked company, with the defendant's address (without it, a name several companies share can't be settled, and the judgment is only a lead) | court dockets, through a vendor | monthly | often, as one-off searches |
| PledgeCheck results | whether the same collateral is pledged at other lenders | Setpoint (third party; simulated here) | monthly | only if subscribed |
| Public securitization reports | loan-level reports of the borrower's own public pools (SEC Form ABS-EE) | SEC EDGAR (public, free; needs a contact email in the request) | monthly | free to fetch |
| SEC filings | 10-K debt notes and Exhibit 21, 8-K items, XBRL revenue | SEC EDGAR (public, free) | as filed | free to fetch |
| Invoice document reads | an optional module, off by default: a fine-tuned model reads each invoice image | produced in-house from the invoice images, only if the bank turns the module on | monthly | not needed: the rules work without it |

**Core inputs:** borrowers, the company registry, payments and disclosures.
- Without them, nothing can be trusted. With no disclosures, for example, every lien and every linked company would look undisclosed.
- A missing core input is quarantined, and the last good copy is used. With no last good copy, the run stops with an error rather than produce cases.

---

## The checks

**Needs:** without it, the check is **not run**. **Optional:** without it, the check runs, and the case says what wasn't checked.

| Check | Needs | Optional, and what is lost without it |
|---|---|---|
| **S1 Collateral integrity** | — | Loan tape: duplicate vehicles and public-pool overlap. Pledged invoices: duplicate invoices. PledgeCheck: pledges of the same collateral at other lenders; the "not enrolled" note is dropped, because it would call every borrower unenrolled. Public securitization reports: public-pool overlap. |
| **S2 Tape vs source** | loan tape | Servicer-system records: the servicer-system pulls. The mismatch findings are dropped, because every pulled loan would look "gone". The other tape checks (current without a payment, impossible jumps, roll rates, rewritten scores) still run. |
| **S3 Cash provenance** | loan tape and pledged invoices (they say who counts as a customer; without them every payer looks unknown) | Operating-account outflows: round trips, and who the borrower pays (undisclosed debt service, cash leakage to new payees). |
| **S4 Invoice authenticity** | pledged invoices | Invoice document reads, only if the optional document module is turned on (`BT_DOCUMENT_MODEL=on`). When it is off, the default, cases say nothing about documents. When it is on and the reads are missing, every case says so. |
| **S5 Hidden debt** | — | Lien filings: liens. Court judgments: judgments. SEC filings: debt named in SEC filings. |
| **S6 Relationship mapper** | LEI register (without it every company looks unregistered, so shell scores rise) | SEC filings: subsidiaries listed in Exhibit 21. If S6 doesn't run, S1, S3 and S5 search the borrower only, not its linked companies. |
| **S7 Financial consistency** | financial statements | SEC filings: revenue reported to the SEC. |

---

## What works on day one

**Before anything runs:** the four core inputs. The bank already holds three of them (borrowers, payments, disclosures). The fourth is company registry data. Without it there is no run: S3 can't resolve who a payer is, and S6 can't find undisclosed linked companies, which is the point of S6.

**How to say it in the pitch (Vedant, 1 Oct 2026):** "It plugs into the company data you already use for KYC. If you don't have a feed, this is what you'd need." There is no starter mode without registry data. Such a mode would miss exactly the hidden companies S6 exists to find.

**Day one, with a registry feed, what the bank already holds** (credit lines, financials, loan tapes, invoices), **and the free public sources** (GLEIF, SEC EDGAR):

| Check | Day one |
|---|---|
| S1 | partial: the bank's own duplicate pledges and public-pool overlap work; other lenders' pledges need PledgeCheck |
| S2 | partial: the tape checks run; servicer-system pulls need field-exam access as data |
| S3 | runs; round trips only for borrowers whose operating account the bank holds |
| S4 | runs (rules only) |
| S5 | partial: debt named in SEC filings runs, for borrowers that file; liens and judgments need the vendor feeds |
| S6 | runs |
| S7 | runs |

**Recommended, because no table here can show it (found by the blind red team, 1 Oct 2026):** loans invented and kept consistent across the tape, the servicer system and the payments can't be told apart from real ones using the borrower's own data. Two outside sources can:
- **Vehicle title and registration records**, to show that the vehicle exists and that the lien is noted on the title.
- **Confirming a sample of customers directly**, the way receivables are confirmed with debtors.

Both are outside this data contract today, and both are pilot items.

**Recommended: ownership records (found by the blind red team, round 2, 2 Oct 2026).**
- A company held in someone else's name, backdated, with no link to the owner in the registry, can send the borrower money that looks like customer receipts.
- The money is found, but nothing in the registry links the payer to the owner. Only records of who really owns each company can.
- Sources: the beneficial-ownership records the bank already keeps under KYC for companies that are its own customers, or an ownership-data vendor.
- Outside this data contract today, and a pilot item.

**What to add next, in order of value:**
1. A monthly lien feed (S5 liens).
2. Servicer-system access as data (S2's strongest facts).
3. PledgeCheck.
4. Court judgments.

---

## Known limits

- **Book level, not borrower level.** "Not delivered" is decided per file, for the whole book. In a bank, inputs arrive per borrower: the operating account might be held for some borrowers and not others. The case should then say which inputs were missing *for that borrower*. **Not built.**
- **A crashed check upstream.** S7 compares revenue with the verified cash S3 publishes. If S3 crashes or doesn't run, S7 quietly skips that comparison. The case already shows S3 as unavailable, but not that S7 lost a check. **Not built.**
- **The layouts are this project's own.** A bank's loan tape, servicer extract or lien feed will have different column names. Since 2 Oct 2026, the file mapper (`bt/mapper`, `INTEGRATION.md` section 3) maps the files borrowers send (loan tapes, invoice lists, servicer extracts), with checks and a signed report. The feeds from bank systems and vendors are still mapped once per bank, in a pilot.
- **The bank's own identity is fixed in the data.** The bank's own liens and its own SEC-listed debt are skipped by name and by entity ID. Gap 6 makes the name a setting.
