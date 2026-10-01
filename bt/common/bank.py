"""The bank running Borrower Truth: one setting, read from the environment.

Wells Fargo is the worked example (Vedant, 1 Oct 2026), so it is the default and the demo reads exactly as before.
Another bank sets BT_BANK_NAME, as it appears in lien filings and letters, and BT_BANK_ENTITY_ID, its own ID in the
company registry. The checks use them to skip the bank's own liens and debt, and to say "disclosed to <bank>".
"""
import os

NAME = os.environ.get("BT_BANK_NAME", "Wells Fargo")
ENTITY_ID = os.environ.get("BT_BANK_ENTITY_ID", "E_WF")


def is_bank(name: str | None) -> bool:
    """A filing or payer name that is this bank ("Wells Fargo Bank, N.A." for "Wells Fargo")."""
    return NAME.upper() in (name or "").upper()
