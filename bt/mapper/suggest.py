"""Suggest which of a lender's columns is which of ours. A suggestion only: a person confirms it once per lender.

A header is split into words ("reportingPeriodEndingDate" -> "reporting period ending date", "Cur. Bal" ->
"current balance") and scored against each column's names: how much of a name the header contains, and how much
of the header that name explains. A header holding a word that means a different number ("original", "beginning",
"code") scores half. Each of our columns takes at most one header, best scores first, and only from SCORE_MIN up.
"""
from __future__ import annotations

import re
import statistics

from rapidfuzz import fuzz

from bt.mapper import convert
from bt.mapper.targets import TABLES

SCORE_MIN = 60
ABBREV = {"bal": "balance", "amt": "amount", "orig": "original", "prin": "principal", "cur": "current",
          "curr": "current", "no": "number", "num": "number", "nbr": "number", "dt": "date", "pct": "percent",
          "yr": "year", "mo": "month", "acct": "account", "cust": "customer", "inv": "invoice", "desc": "description",
          "elig": "eligible", "dlq": "delinquency", "delinq": "delinquency", "int": "interest", "addr": "address"}


def words(header) -> list[str]:
    s = convert.text(header)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = s.replace("#", " number ").replace("%", " percent ").replace("&", " and ")
    s = re.sub(r"[^A-Za-z0-9]+", " ", s).lower().split()
    out = []
    for w in s:
        out += ABBREV.get(w, w).split()
    return out


def _has(tokens: list[str], w: str) -> bool:
    return any(t == w or (len(w) >= 5 and len(t) >= 5 and fuzz.ratio(t, w) >= 90) for t in tokens)


def score(header_words: list[str], name: str, negatives=()) -> float:
    n = name.split()
    if not header_words or not n:
        return 0.0
    if header_words == n:
        s = 100.0
    else:
        hit = sum(_has(header_words, w) for w in n)
        if not hit:
            return 0.0
        explained = sum(_has(n, w) for w in header_words)
        s = 100 * (0.75 * hit / len(n) + 0.25 * explained / len(header_words))
    joined = " ".join(header_words)
    if any(neg in joined if " " in neg else _has(header_words, neg) for neg in negatives):
        s *= 0.5
    return s


def suggest(headers: list, table: str, fixed: set[str] = frozenset()) -> tuple[dict, list[str]]:
    """({our column: (lender header, score)}, lender headers left over). `fixed` columns are set by a person."""
    cols = [c for c in TABLES[table] if c.synonyms and c.name not in fixed]
    hw = {i: words(h) for i, h in enumerate(headers) if convert.text(h)}
    pairs = []
    for c in cols:
        for i, w in hw.items():
            s = max(score(w, name, c.negatives) for name in c.synonyms)
            if s >= SCORE_MIN:
                pairs.append((-s, [x.name for x in cols].index(c.name), i, c.name))
    pairs.sort()
    taken_c, taken_h, out = set(), set(), {}
    for neg, _, i, name in pairs:
        if name in taken_c or i in taken_h:
            continue
        taken_c.add(name)
        taken_h.add(i)
        out[name] = (convert.text(headers[i]), round(-neg, 1))
    left = [convert.text(headers[i]) for i in hw if i not in taken_h]
    return out, left


def guess_formats(table: str, mapped: dict, header: list, data: list[list]) -> dict:
    """From the values themselves: are days late counted in days or buckets, is a rate a percent, which way round
    are dates written. A guess for the person to confirm: a file where no loan is more than 4 days late reads as
    buckets, so the format is shown in the draft and in every report."""
    idx = {convert.text(h): i for i, h in enumerate(header)}
    kinds = {c.name: c.kind for c in TABLES[table]}

    def sample(col):
        i = idx[mapped[col][0]]
        return [r[i] for r in data if i < len(r) and not convert.is_empty(r[i])]

    f = {"dates": "MDY", "dpd": "days", "rate": "decimal"}
    for col in mapped:
        vals = sample(col)
        if not vals:
            continue
        if kinds[col] == "dpd":
            nums = []
            for v in vals:
                try:
                    nums.append(convert.integer(v))
                except convert.Bad:
                    f["dpd"] = "text"
                    break
            else:
                f["dpd"] = "bucket" if max(nums) <= 4 else "days"
        elif kinds[col] == "rate":
            if any(isinstance(v, str) and v.strip().endswith("%") for v in vals):
                f["rate"] = "percent"
            else:
                try:
                    f["rate"] = "percent" if statistics.median(convert.money(v) for v in vals) > 1 else "decimal"
                except convert.Bad:
                    pass
        elif kinds[col] in ("month", "date_split"):
            for v in vals:
                m = re.fullmatch(r"\s*(\d{1,2})[/-](\d{1,2})[/-]\d{2,4}\s*", str(v)) if isinstance(v, str) else None
                if m and int(m.group(1)) > 12:
                    f["dates"] = "DMY"
                    break
    return f
