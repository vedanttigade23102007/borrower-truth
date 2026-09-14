"""Peer benchmark: is a loan tape's delinquency believable next to real public pools?

For each loan on the tape we know its credit-score band and its age. Real public auto pools
(SEC ABS-EE, measured by bt.sec.calibrate) tell us what share of loans with that band and age
are 30+ days late. Summed over the tape, that gives the number of late loans an honest lender
with this exact mix would report. A tape reporting far fewer is "too good to be true": the
Tricolor allegation was exactly that defaulted loans were made to look current.

It is a statistical clue, never proof on its own. Its threshold is set on REAL pools: every
public pool is tested against the others (leaving out its own lender), and the threshold sits
below the lowest honest pool, so real honest lenders don't trip it.

    uv run python -m bt.sec.benchmark      # the real-pool test
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from functools import lru_cache

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAL = os.path.join(ROOT, "data", "calibration", "absee_auto.json")
BANDS = [(580, "<580"), (620, "580-619"), (660, "620-659"), (720, "660-719"), (10_000, "720+")]
AGES = [(12, "0-11m"), (24, "12-23m"), (10_000, "24m+")]
MIN_CELL = 200  # a band x age cell thinner than this borrows its band's overall rate
MIN_LOANS = 150  # too few loans on the tape: no benchmark
RATIO_MAX = 0.40  # reported late share below 40% of what peers with the same mix report...
Z_MAX = -4.0  # ...and far outside chance for a tape this size


def band(score) -> str | None:
    if score is None:
        return None
    for hi, name in BANDS:
        if score < hi:
            return name
    return None


def age_bucket(age) -> str:
    for hi, name in AGES:
        if age < hi:
            return name
    return AGES[-1][1]


@lru_cache(maxsize=1)
def calibration() -> dict | None:
    return json.load(open(CAL)) if os.path.exists(CAL) else None


def peer_rates(cal: dict, exclude_family: str | None = None) -> dict:
    cell, by_band = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for c in cal["cells"]:
        if c["family"] == exclude_family or c["band"] == "unknown":
            continue
        for d, k in ((cell, (c["band"], c["age_b"])), (by_band, c["band"])):
            d[k][0] += c["late"]
            d[k][1] += c["n"]
    rates = {}
    for (b, a), (late, n) in cell.items():
        bl, bn = by_band[b]
        rates[(b, a)] = late / n if n >= MIN_CELL else (bl / bn if bn else 0.0)
    return rates


def assess(counts: dict, late: int, rates: dict) -> dict | None:
    """counts: (band, age) -> loans on the tape. late: loans the tape reports 30+ days late."""
    n = sum(counts.values())
    if n < MIN_LOANS:
        return None
    exp = sum(k * rates.get(cell, 0.0) for cell, k in counts.items())
    if exp <= 0:
        return None
    p = exp / n
    z = (late - exp) / math.sqrt(max(n * p * (1 - p), 1e-9))
    return dict(n=n, late=late, expected=round(exp, 1), ratio=round(late / exp, 3), z=round(z, 2),
                too_good=late / exp < RATIO_MAX and z < Z_MAX)


def real_pool_test(cal: dict | None = None) -> list[dict]:
    """Each real public pool against the others, leaving out its own lender."""
    cal = cal or calibration()
    per_trust = defaultdict(lambda: dict(counts=defaultdict(int), late=0, family=None))
    for c in cal["cells"]:
        if c["band"] == "unknown":
            continue
        t = per_trust[c["trust"]]
        t["family"] = c["family"]
        t["counts"][(c["band"], c["age_b"])] += c["n"]
        t["late"] += c["late"]
    out = []
    for trust, t in sorted(per_trust.items()):
        r = assess(t["counts"], t["late"], peer_rates(cal, exclude_family=t["family"]))
        if r:
            out.append(dict(trust=trust, family=t["family"], **r))
    return out


if __name__ == "__main__":
    res = real_pool_test()
    for r in sorted(res, key=lambda r: r["ratio"]):
        print(f"{r['trust']:58} n={r['n']:>7,} late={r['late']:>6,} expected={r['expected']:>8,.0f} "
              f"ratio={r['ratio']:.2f} z={r['z']:>7.1f} {'TOO GOOD' if r['too_good'] else ''}")
    print(f"{sum(r['too_good'] for r in res)} of {len(res)} real public pools flagged")
