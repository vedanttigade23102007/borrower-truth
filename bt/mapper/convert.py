"""Turn a lender's cell values into the checks' values. Each converter returns a value or raises Bad with a reason
a person can act on. Empty cells come back as None; whether that's allowed is decided by the caller."""
from __future__ import annotations

import datetime as dt
import math
import re


class Bad(ValueError):
    pass


EMPTY = {"", "n/a", "na", "null", "none", "-", "--"}
TRUE_WORDS = {"y", "yes", "true", "t", "1", "eligible", "e"}
FALSE_WORDS = {"n", "no", "false", "f", "0", "ineligible", "i", "not eligible"}
TOTAL = re.compile(r"^\s*(grand\s+|sub-?\s*)?totals?\b", re.I)


def is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, str) and v.strip().lower() in EMPTY


def text(v) -> str:
    if is_empty(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))  # an ID Excel stored as a number
    return str(v).strip()


def ident(v) -> str | None:
    s = text(v)
    return s or None


def money(v) -> float | None:
    if is_empty(v):
        return None
    if isinstance(v, bool):
        raise Bad(f"'{v}' is not an amount")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("$", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        raise Bad(f"'{v}' is not an amount")
    if math.isnan(x) or math.isinf(x):
        raise Bad(f"'{v}' is not an amount")
    return -x if neg else x


def integer(v) -> int | None:
    if is_empty(v):
        return None
    if isinstance(v, bool):
        raise Bad(f"'{v}' is not a whole number")
    try:
        x = float(str(v).strip().replace(",", "")) if not isinstance(v, (int, float)) else float(v)
    except ValueError:
        raise Bad(f"'{v}' is not a whole number")
    if not x.is_integer():
        raise Bad(f"'{v}' is not a whole number")
    return int(x)


def terms(v) -> int | None:
    """Payment terms: 30, '30', 'Net 30', 'NET30' -> 30."""
    if is_empty(v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return integer(v)
    m = re.fullmatch(r"\s*(?:net\s*)?(\d+)\s*(?:days?)?\s*", str(v), re.I)
    if not m:
        raise Bad(f"'{v}' is not a payment term")
    return int(m.group(1))


def rate(v, unit: str) -> float | None:
    """unit: 'decimal' (0.0525) or 'percent' (5.25). A value written with % is always a percent."""
    if is_empty(v):
        return None
    if isinstance(v, str) and v.strip().endswith("%"):
        return money(v.strip()[:-1]) / 100
    x = money(v)
    return x / 100 if unit == "percent" else x


DPD_TEXT = {"current": 0, "0": 0, "1-29": 0, "30": 1, "30-59": 1, "60": 2, "60-89": 2, "90": 3, "90+": 3, "90-119": 3,
            "120+": 3}


def bucket_of_days(d: int) -> int:
    if d < 0:
        raise Bad(f"{d} days late is negative")
    return 0 if d < 30 else 1 if d < 60 else 2 if d < 90 else 3


def dpd(v, unit: str) -> int | None:
    """unit: 'days' (days late), 'bucket' (0 current, 1 30-59, 2 60-89, 3 90+, 4 charged off) or 'text'."""
    if is_empty(v):
        return None
    if unit == "text":
        k = re.sub(r"\s+", "", str(v).strip().lower()).replace("days", "").replace("dpd", "")
        if k not in DPD_TEXT:
            raise Bad(f"'{v}' is not a delinquency status")
        return DPD_TEXT[k]
    n = integer(v)
    if unit == "days":
        return bucket_of_days(n)
    if not 0 <= n <= 4:
        raise Bad(f"{n} is not a late bucket (0-4)")
    return n


def boolean(v, true_words=TRUE_WORDS, false_words=FALSE_WORDS) -> bool | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    s = str(v).strip().lower()
    if s in true_words:
        return True
    if s in false_words:
        return False
    raise Bad(f"'{v}' is not yes or no")


FORMATS = {"MDY": ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"), "DMY": ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y")}


def date(v, order: str = "MDY") -> dt.date | None:
    """A calendar date, from an Excel date or text. Month-only text ('2024-03', '03/2024') is the 1st."""
    if is_empty(v):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    for f in ("%Y-%m-%d", "%Y/%m/%d") + FORMATS[order]:
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s) or None
    if m and 1 <= int(m.group(2)) <= 12:
        return dt.date(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"(\d{1,2})[/-](\d{4})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return dt.date(int(m.group(2)), int(m.group(1)), 1)
    raise Bad(f"'{v}' is not a date")


def month_index(d: dt.date, first_month: str) -> int:
    """Reporting month number, counted from the facility's first month (month 0)."""
    y0, m0 = map(int, first_month.split("-"))
    return (d.year * 12 + d.month) - (y0 * 12 + m0)


def is_total_row(cells: list, id_idx: int | None) -> bool:
    """A subtotal or grand-total line: its ID cell is empty or says "total", and its first filled cell says "total".
    A real row whose customer happens to be called "Total Logistics Inc" keeps its ID, so it is never dropped."""
    first = next((c for c in cells if not is_empty(c)), None)
    if not (isinstance(first, str) and TOTAL.match(first)):
        return False
    own = cells[id_idx] if id_idx is not None and id_idx < len(cells) else None
    return is_empty(own) or (isinstance(own, str) and bool(TOTAL.match(own)))
