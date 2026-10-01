# The data the bank receives

One parquet file per table. Money is in US dollars. "Month" runs from 0 to 23. A negative month means before month 0, the date the bank started lending. All names, IDs and numbers are synthetic.

**Who supplies it:**
- **bank**: the bank's own records
- **borrower**: the borrower reports it
- **servicer**: the system the loans are serviced in, often run by the borrower itself
- **public**: a public register or filing
- **third party**: a service the lenders use

---

### borrowers (bank)
The non-bank lenders the bank lends to. One row each.
- `borrower_id`: the borrower's ID, for example `B0001`
- `entity_id`: its company in the registry (`entities`)
- `name`: its company name
- `btype`: what it lends against: `auto_finance`, `consumer_finance`, `real_estate_finance` or `receivables_finance` (invoices)
- `state`: its US state
- `owner_person_id`: its owner (`persons`)
- `facility_limit`: the most the bank will lend it, across all its credit lines

### facilities (bank)
The borrower's credit lines with the bank.
- `facility_id`: the credit line's ID
- `borrower_id`: whose credit line it is
- `lender_entity_id`: the bank (`E_WF`)
- `kind`: `warehouse` or `term`
- `limit`: the line's maximum
- `advance_rate`: the share of eligible collateral the bank lends against

### tape (borrower, monthly)
The loan tape: every loan the borrower has pledged, every month. Car, consumer and real-estate lenders only.
- `month`, `facility_id`, `borrower_id`
- `asset_id`: the loan's ID, for example `A-B0001-000003`
- `vin`: the vehicle ID (car loans)
- `obligor_id`: the person who owes the loan, for example `O-B0001-000003`
- `balance`: what is still owed
- `dpd_bucket_reported`: how late the loan is, as reported: `0` current, `1` 30–59 days late, `2` 60–89, `3` 90 or more
- `deferred_flag`: `1` if payments are paused (deferred) that month
- `eligible_reported`: whether the borrower says the loan counts as eligible collateral
- `orig_month`, `orig_amount`, `rate`, `term`: when it was made, for how much, at what rate, for how many months
- `make`, `model`, `model_year`: the vehicle (car loans)
- `obligor_state`: the borrower's customer's US state
- `credit_score`: the customer's credit score when the loan was made

### source_truth (servicer, monthly)
The same loans as recorded in the system they are serviced in. The bank can obtain these records under its audit rights.
- `month`, `borrower_id`, `asset_id`
- `dpd_bucket_true`: how late the loan really is: `0`–`3` as above, `4` charged off (written off)
- `balance_true`: what is really still owed

### payments (bank, monthly)
Money arriving in the borrower's collection account, which the bank controls.
- `txn_id`, `month`, `day`, `borrower_id`, `account_id`
- `payer_id`, `payer_name`: who paid. Customers paying their loans appear as their `obligor_id`; companies as their `entity_id`
- `amount`
- `memo`: for example `loan payment`
- `ref`: what the payment says it pays: a loan `asset_id`, an invoice number, or something else

### outflows (bank, monthly)
Money leaving the borrower's operating account, held at the bank.
- `txn_id`, `month`, `day`, `borrower_id`, `account_id`
- `payee_id`, `payee_name`: who was paid
- `amount`
- `memo`: for example `vendor payment`, `payroll`, `rent`, `debt service`

### invoices (borrower, monthly)
Invoices pledged by invoice-finance borrowers.
- `borrower_id`, `invoice_id`, `facility_id`
- `pledged_month`: when it was pledged
- `invoice_number`, `po_number`
- `debtor_id`, `debtor_name`: the customer who owes the invoice
- `issue_month`, `issue_day`, `due_days`: when it was issued, and how many days the customer has to pay
- `amount`, `description`

Customers pay invoices into the collection account (`payments`), with the invoice number in `ref`.

### financials (borrower, quarterly)
Financial statements and the covenant figure. Quarter `q` (0–7) arrives at month `3q + 2`.
- `borrower_id`, `quarter`
- `revenue_reported`, `receivables_reported`, `cash_reported`, `debt_reported`
- `covenant_metric_reported`, `covenant_threshold`: the credit agreement requires the metric to stay at or above the threshold

### disclosures (borrower)
What the borrower has told the bank.
- `borrower_id`
- `kind`: `debt` (another lender), `related_party` (a related company) or `deferment_program` (a programme that lets customers pause payments)
- `counterparty_entity_id`: the other company, if any
- `start_month`: when it applies from
- `note`: a short description

### entities (public: company registry)
Companies: borrowers, their customers, other lenders, holding companies and other companies.
- `entity_id`, `name`
- `kind`: for example `borrower`, `lender`, `bank`, `holding`, `company`, `debtor`
- `officer_person_id`: its officer (`persons`)
- `address`, `state`, `phone`, `registered_agent`
- `formed_month`: when it was formed
- `has_operations`: whether it shows signs of a real business

### persons (public)
People named as owners and officers.
- `person_id`, `name`

### gleif (public: the Legal Entity Identifier register)
Companies that have an LEI.
- `lei`, `entity_id`, `legal_name`
- `parent_entity_id`: its parent company, if any

### ucc_filings (public: lien filings)
Liens that lenders have filed against companies' assets.
- `filing_id`, `state`
- `debtor_name`, `debtor_address`: the company the lien is against, as the filer typed it
- `secured_party_name`: the lender holding the lien
- `collateral_desc`: what it covers
- `filed_month`

### court_records (public)
Court judgments against companies.
- `case_id`, `defendant_name`, `plaintiff`, `kind`, `amount`, `month`

### pledgecheck (third party, monthly)
A shared collateral registry that lenders use to see whether the same collateral is pledged to more than one lender. Borrowers enrol their credit lines.
- `borrower_id`, `facility_id`, `month`
- `enrolled`
- `uniqueness`, `data_integrity`, `completeness`, `single_record`: each `PASS` or `FAIL`

### public_abs (public: SEC Form ABS-EE)
Some borrowers sell loans into public securitizations. Each month they report every loan in the pool to investors. These reports have no vehicle ID.
- `pool_id`, `issuer_borrower_id`: the pool, and the borrower that sold the loans
- `month`, `pool_loan_id`
- `orig_month`, `orig_amount`, `rate`, `term`, `make`, `model`, `model_year`, `obligor_state`, `credit_score`: the loan
- `dpd_bucket`: how late it is

### sec_filings (public: SEC filings, for borrowers that file)
- `borrower_id`
- `form`: `10-K`, `10-Q` or `8-K`
- `filed_month`
- `item`:
  - `debt`: a lender named in the 10-K debt note
  - `subsidiary`: Exhibit 21
  - `revenue`: XBRL revenue
  - `2.03`: a new direct financial obligation
  - `2.04`: an obligation sped up
- `counterparty_entity_id`, `counterparty_name`: the lender or subsidiary, if any
- `amount`, `quarter`, `note`
