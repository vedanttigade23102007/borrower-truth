"""Real SEC ABS-EE pools: can the public-pool overlap check's tolerance join two DIFFERENT real loans?

Trusts of the same lender hold different loans, so any match between them is a false one. Run after changing
OVERLAP_AMOUNT_TOL or OVERLAP_SCORE_TOL in bt/systems/s1_collateral.py (needs the cached ABS-EE files):

    uv run python -m bt.sec.overlap_check
"""
from bt.sec.calibrate import con
from bt.systems.s1_collateral import OVERLAP_AMOUNT_TOL, OVERLAP_MIN, OVERLAP_SCORE_TOL

SETTINGS = (("exact match (before 2 Oct 2026)", 0.0, 0, 0), ("the check's tolerance", OVERLAP_AMOUNT_TOL, OVERLAP_SCORE_TOL, 0),
            ("looser, for comparison: amount 3%, score 10, origination month +-1", 0.03, 10, 1))


def main():
    c = con()
    c.execute("""CREATE TABLE L AS SELECT trust, family, asset, orig_ym, round(orig_amt, 2) amt, term, round(rate, 4) rate,
                 upper(make) make, upper(model) model, model_year, state, score_ok FROM p2
                 WHERE coalesce(end_bal, 0) > 0 AND make IS NOT NULL AND orig_amt > 0""")
    n, trusts, fams = c.execute("SELECT count(*), count(DISTINCT trust), count(DISTINCT family) FROM L").fetchone()
    multi = c.execute("SELECT count(*) FROM (SELECT family FROM L GROUP BY 1 HAVING count(DISTINCT trust) > 1)").fetchone()[0]
    lines = ["# Public-pool overlap: the tolerance against real loans", "",
             f"Real SEC ABS-EE data: {n:,} open loans in {trusts} trusts of {fams} lenders; {multi} lenders have two or "
             "more trusts. Different trusts of one lender hold different loans, so every match below is a false one. "
             f"The check needs {OVERLAP_MIN} or more matched loans, two months running, before it notes anything.", "",
             "| Matching rule | Trust pairs with any match | Pairs with enough matches to trip the check | Largest |",
             "|---|---|---|---|"]
    for name, a, s, mo in SETTINGS:
        month = "x.orig_ym = y.orig_ym" if mo == 0 else (
            "abs((CAST(left(x.orig_ym,4) AS INT)*12+CAST(right(x.orig_ym,2) AS INT))"
            "-(CAST(left(y.orig_ym,4) AS INT)*12+CAST(right(y.orig_ym,2) AS INT))) <= 1")
        r = c.execute(f"""
          SELECT x.trust, y.trust, count(DISTINCT x.asset) FROM L x JOIN L y
            ON x.family = y.family AND x.trust < y.trust AND x.term = y.term AND x.rate = y.rate AND x.make = y.make
           AND x.model = y.model AND x.model_year = y.model_year AND x.state = y.state AND {month}
           AND abs(x.amt - y.amt) <= {a} * greatest(x.amt, y.amt) AND abs(x.score_ok - y.score_ok) <= {s}
          GROUP BY 1, 2 ORDER BY 3 DESC""").fetchall()
        lines.append(f"| {name} | {len(r)} | {sum(1 for x in r if x[2] >= OVERLAP_MIN)} | {r[0][2] if r else 0} loans |")
    lines += ["", f"The check uses amount within {OVERLAP_AMOUNT_TOL:.0%} and credit score within {OVERLAP_SCORE_TOL} points, "
                  "all other fields exact. Limit: only 6 lenders have two trusts here, so this tests cross-trust "
                  "near-duplicates, not every way a match could go wrong."]
    open("proof/REAL_DATA_overlap.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
