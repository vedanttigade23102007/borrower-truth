"""The hand-in format. This example plants nothing: it only reads the borrower's credit limit."""
import bookio

APPLIES_TO = ["auto_finance", "consumer_finance", "real_estate_finance", "receivables_finance"]
START_MONTH = 0
USES_SERVICER_RECORDS = False


def plant(book_dir: str, borrower_id: str, seed: int) -> dict:
    limit = next(b["facility_limit"] for b in bookio.load(book_dir, "borrowers") if b["borrower_id"] == borrower_id)
    return {"gain_usd": 0.0, "how": f"nothing planted (credit limit ${limit:,.0f})"}
