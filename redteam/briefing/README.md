# Red team briefing

You are the red team in a fraud-detection test. Everything here is **synthetic**: no real company, person or loan. The goal is defensive. A bank wants to know which frauds its monthly monitoring would miss, so that it can fix them before a real borrower tries.

## The situation

- A bank lends money to **non-bank lenders**: car lenders, consumer lenders, real-estate lenders and invoice-finance companies. These are the **borrowers**.
- Each borrower pledges its own loans (or, for invoice-finance companies, its invoices) as collateral. The bank lends up to a share of the collateral's value: the advance rate.
- **Every month** the bank receives data about each borrower and checks it. You don't know how it checks. That is the point of this test.
- Like most lenders, the bank also sends examiners once a quarter to look at **a small sample** of loans and invoices. A borrower knows this happens.
- Time runs from **month 0 to month 23**. Month 0 is when the bank starts lending. Loan data, payments and invoices arrive monthly. Financial statements arrive quarterly: quarter q (0–7) arrives at month 3q + 2.

## What you have

| File | What it is |
|---|---|
| `TABLES.md` | every data table the bank receives: what it is, who supplies it, and what each column means |
| `sample_book/` | one honest book: 34 borrowers with no fraud, one parquet file per table. Real books are bigger (120 borrowers) and contain some fraud you can't see here |
| `allegations/` | public DOJ and SEC allegations about two real collapses, First Brands and Tricolor. They are allegations, not proven facts |
| `bookio.py` | a small helper to read and write the tables without changing their layout (uses `pyarrow` only) |
| `example_attack/` | the hand-in format. It plants nothing |

The bank appears in the data as company `E_WF` ("Wells Fargo Bank, N.A."). It is only a synthetic example. Do not research it.

## Your task

Design **up to 8 attacks**. An attack is a fraud that one borrower commits, written as a script that plants it into that borrower's data. Try to make each one a fraud the bank's monitoring would **miss**, while it still pays off for the borrower.

## Rules

**1. Levers: change only what a borrower really controls.**

The borrower may change:
- everything it reports: its loan tape, invoices, financial statements, covenant figures and disclosures
- companies it forms or controls: owners, officers, addresses, phone numbers and registered agents of its choice, including nominees (someone else named as the owner); and whether they get an LEI. It may add new companies and people. It may edit only its own company and companies whose officer is its owner
- money it moves: it may **add** payments into its collection account (`payments`) and payments out of its operating account (`outflows`)
- the reports of its own public securitizations, and its own SEC filings, if it files
- **its own servicer system** (`source_truth`), because many non-bank lenders service their own loans. If an attack does this, say so: the results are reported with and without this lever.

The borrower may **not** change:
- other borrowers' data
- the bank's records: `borrowers`, `facilities`, and payments already recorded in `payments` or `outflows` (it may add new ones, not edit or remove these)
- lien filings (`ucc_filings`) and court records (`court_records`)
- the LEI register entries of companies it doesn't control
- PledgeCheck's results (it may stop being enrolled, by removing its own rows)

**2. Size.** Each attack must gain the borrower at least **5% of its `facility_limit`** (in `borrowers`) over the 24 months. A gain is money it obtains or keeps that it isn't entitled to, for example:
- advances against collateral that doesn't exist or isn't eligible
- collections it diverts
- debt it takes elsewhere and hides from the bank

`plant()` must compute and return this gain.

**3. Timing.** The fraud must start by month **18**.

**4. Variety.**
- Each attack is a different trick.
- **At least half** must follow something alleged in `allegations/`.
- The rest can be new.

**5. Blindness.**
- Work only from these files. Do not search the web. Do not look up the bank, either company, or any project or code that checks loans.
- If anything in these files seems to reveal how the bank checks, don't use it, and say so in your hand-in.

## What to hand in

One file: **`attacks.zip`**, containing one folder per attack:

```
attacks/
  <short_name>/
    README.md    the story in plain words; the allegation it follows, if any; the levers it pulls;
                 how big the gain is and how you computed it; why you expect monitoring to miss it
    plant.py     the script (format below); it may import bookio and other files in its own folder
```

`plant.py` must define:

```python
APPLIES_TO = ["auto_finance"]        # borrower types (borrowers.btype) it can be planted into
START_MONTH = 6                      # the first month the fraud acts (at most 18)
USES_SERVICER_RECORDS = False        # True if it changes source_truth

def plant(book_dir: str, borrower_id: str, seed: int) -> dict:
    """Plant the fraud into one honest borrower of the book in book_dir, editing its parquet files
    in place with bookio. Use `seed` for any randomness. Return
    {"gain_usd": <the gain over 24 months>, "how": "<one line>"}."""
```

The borrower types are `auto_finance`, `consumer_finance`, `real_estate_finance` and `receivables_finance`.

Use only Python's standard library, `pyarrow`, `numpy` and `bookio`. Each script will be planted into 2 honest borrowers of the listed types, in each of 5 fresh books it has never seen, and scored once.

**Test every script on a copy of `sample_book/` before you hand it in.** It must run without errors, and `bookio.save` must accept every table it writes.
