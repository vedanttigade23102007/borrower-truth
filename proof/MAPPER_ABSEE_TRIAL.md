# The file mapper on a real lender layout (SEC ABS-EE)

Run once on 2026-10-02 (`bt/mapper/trial_absee.py`). **Real public data:** 2,000 loans from BMW Vehicle Owner Trust 2023-A, report for 2026-03, as filed with the SEC. Not a borrowing-base spreadsheet: ABS-EE is the loan-level report auto lenders file for investors, so it shows how real lenders name their fields.

## 1. Suggesting from the headers alone

The file has 29 columns, named as the lender files them. Our loan tape has 18 columns a file could fill. ABS-EE carries 13 of them; the other 5 (VIN, customer ID, eligibility, deferral, facility) aren't in ABS-EE at all.

- **Right:** 12 of 13
- **Wrong:** 0 (a column filled from the wrong field)
- **Missed, for a person to map:** 1
- **Correctly left empty** (no ABS-EE field holds them): 5 of 5

| Our column | Right answer | Suggested | Score | Verdict |
|---|---|---|---|---|
| `month` | reportingPeriodEndingDate | reportingPeriodEndingDate | 87.5 | right |
| `asset_id` | assetNumber | assetNumber | 100.0 | right |
| `balance` | reportingPeriodActualEndBalanceAmount | reportingPeriodActualEndBalanceAmount | 83.3 | right |
| `dpd_bucket_reported` | currentDelinquencyStatus | currentDelinquencyStatus | 91.7 | right |
| `orig_month` | originationDate | originationDate | 100.0 | right |
| `orig_amount` | originalLoanAmount | originalLoanAmount | 100.0 | right |
| `rate` | originalInterestRatePercentage | originalInterestRatePercentage | 87.5 | right |
| `term` | originalLoanTerm | originalLoanTerm | 91.7 | right |
| `make` | vehicleManufacturerName | vehicleManufacturerName | 83.3 | right |
| `model` | vehicleModelName | vehicleModelName | 91.7 | right |
| `model_year` | vehicleModelYear | vehicleModelYear | 91.7 | right |
| `obligor_state` | obligorGeographicLocation | - | - | missed: a person maps it |
| `credit_score` | obligorCreditScore | obligorCreditScore | 91.7 | right |
| `facility_id` | (none in ABS-EE) | - | - | right: left for a person |
| `vin` | (none in ABS-EE) | - | - | right: left for a person |
| `obligor_id` | (none in ABS-EE) | - | - | right: left for a person |
| `deferred_flag` | (none in ABS-EE) | - | - | right: left for a person |
| `eligible_reported` | (none in ABS-EE) | - | - | right: left for a person |

Lender columns left unused: 17 (originatorName, vehicleNewUsedCode, vehicleValueAmount, obligorCreditScoreType, paymentToIncomePercentage, obligorGeographicLocation, assetAddedIndicator, reportingPeriodModificationIndicator, reportingPeriodBeginningLoanBalanceAmount, reportingPeriodScheduledPaymentAmount, totalActualAmountPaid, zeroBalanceCode, zeroBalanceEffectiveDate, chargedoffPrincipalAmount, recoveredAmount, paymentExtendedNumber, repossessedIndicator)

## 2. Mapping the file, after a person's corrections

A person fixes what the suggestion got wrong or missed, maps customer ID to the loan number (ABS-EE has no customer ID), and sets the values ABS-EE doesn't carry: facility, no VIN, not deferred, eligible.

- Result: **written**
- Rows read 2,000, written 2,000, rejected 0
- Control total (the same loans' ending balances): off by $0.00
- Formats guessed from the values: {'dates': 'MDY', 'dpd': 'days', 'rate': 'decimal'}

## Caveats

- The mapper's column names (`bt/mapper/targets.py`) were written before this run and not changed after it. Their author had seen these field names before, in `bt/sec/absee.py`, so this is not a fully blind test.
- One trust, one month. Other lenders name fields differently; a borrowing-base spreadsheet sent to a bank may look nothing like this.
