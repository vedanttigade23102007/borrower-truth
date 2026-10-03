"""Measure how real auto loans behave, from the ABS-EE files pulled by bt.sec.absee.

Writes data/calibration/absee_auto.json (committed; small) with:
  - monthly transition rates between delinquency buckets, by credit-score band and lender tier
  - how often an honest servicer shows a loan as current with no payment that month
  - how often a loan 60+ days late is current the next month without paying
  - how often a loan's credit score at origination changes between monthly reports
  - the credit-score distribution near common eligibility lines
  - how unique a loan's public "fingerprint" is (no VIN in ABS-EE)
  - per-pool metrics, used to test the peer benchmark on real pools
and data/calibration/absee_auto_sample.parquet: real loan attributes (no identity) that the
generator draws synthetic loans from.

    uv run python -m bt.sec.calibrate
"""
from __future__ import annotations

import glob
import json
import os

import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "data", "cache", "sec", "absee")
OUT = os.path.join(ROOT, "data", "calibration")
BANDS = [(0, 580, "<580"), (580, 620, "580-619"), (620, 660, "620-659"), (660, 720, "660-719"), (720, 900, "720+")]
AGE = [(0, 12, "0-11m"), (12, 24, "12-23m"), (24, 999, "24m+")]
STATES = ["current", "30-59", "60-89", "90+", "charged_off", "paid_off"]

BAND_SQL = "CASE " + " ".join(f"WHEN score < {hi} THEN '{name}'" for _, hi, name in BANDS) + " ELSE 'unknown' END"
AGE_SQL = "CASE " + " ".join(f"WHEN age < {hi} THEN '{name}'" for _, hi, name in AGE) + " END"


def con():
    c = duckdb.connect()
    files = sorted(glob.glob(os.path.join(SRC, "*.parquet")))
    if not files:
        raise SystemExit("no ABS-EE parquet yet: run `python -m bt.sec.absee fetch` first")
    c.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet({files!r}, union_by_name=true)")
    # some servicers report delinquency in months, not days: detect per trust and convert
    c.execute("""CREATE TABLE unit AS
        SELECT trust, CASE WHEN max(dpd) <= 12 AND max(dpd) > 0 THEN 30 ELSE 1 END AS mult FROM raw GROUP BY 1""")
    c.execute(f"""
        CREATE TABLE loans AS
        SELECT r.*, r.dpd * u.mult AS dpd_days,
               (CAST(split_part(period_end, '-', 1) AS INT) * 12 + CAST(split_part(period_end, '-', 2) AS INT))
             - (CAST(split_part(orig_ym, '-', 1) AS INT) * 12 + CAST(split_part(orig_ym, '-', 2) AS INT)) AS age,
               CASE WHEN r.score IS NULL OR r.score < 300 OR r.score > 900 THEN NULL ELSE r.score END AS score_ok
        FROM raw r JOIN unit u USING (trust)
        WHERE r.period_end IS NOT NULL AND r.asset IS NOT NULL""")
    c.execute(f"""
        CREATE TABLE s AS
        SELECT *, CASE WHEN score_ok IS NULL THEN 'unknown' ELSE ({BAND_SQL.replace('score', 'score_ok')}) END AS band,
               {AGE_SQL} AS age_b,
               CASE WHEN coalesce(chargeoff, 0) > 0 OR zb_code IN ('4', '04') THEN 'charged_off'
                    WHEN zb_code IN ('1', '01') THEN 'paid_off'
                    WHEN zb_code IS NOT NULL AND coalesce(end_bal, 0) = 0 THEN 'other_exit'
                    WHEN dpd_days < 30 THEN 'current' WHEN dpd_days < 60 THEN '30-59'
                    WHEN dpd_days < 90 THEN '60-89' ELSE '90+' END AS status
        FROM loans""")  # 'status', not 'state': ABS-EE's own 'state' is the obligor's US state
    # the two monthly reports of each trust
    c.execute("""CREATE TABLE per AS SELECT trust, min(period_end) AS p1, max(period_end) AS p2
                 FROM s GROUP BY 1 HAVING count(DISTINCT period_end) >= 2""")
    # a loan is open at the end of a month when it still has a balance and hasn't exited
    c.execute("""CREATE TABLE open1 AS SELECT s.* FROM s JOIN per ON s.trust = per.trust AND s.period_end = per.p1
                 WHERE coalesce(end_bal, 0) > 0 AND status IN ('current', '30-59', '60-89', '90+')""")
    c.execute("""CREATE TABLE p2 AS SELECT s.* FROM s JOIN per ON s.trust = per.trust AND s.period_end = per.p2""")
    c.execute("""CREATE TABLE tr AS
        SELECT a.trust, a.family, a.tier, a.band, a.age_b, a.status AS s1, b.status AS s2, b.paid AS paid2,
               b.sched AS sched2, b.extended AS ext2, b.modified AS mod2, a.score_ok AS score1, b.score_ok AS score2
        FROM open1 a JOIN p2 b ON a.trust = b.trust AND a.asset = b.asset
        WHERE b.status <> 'other_exit'""")
    return c


def rows(c, sql):
    cur = c.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run():
    c = con()
    out = dict(source="SEC Form ABS-EE (Reg AB II Schedule AL Item 3), public auto-loan securitizations",
               note="Real public data. Loans have no VIN and no borrower identity. Measured, not assumed.")
    man = json.load(open(os.path.join(SRC, "manifest.json")))
    out["pools"] = sorted({(v["family"], v["tier"], v["trust"]) for v in man.values()})
    out["files"] = len(man)
    out["loan_rows"] = c.execute("SELECT count(*) FROM s").fetchone()[0]
    out["open_loans_month1"] = c.execute("SELECT count(*) FROM open1").fetchone()[0]
    out["pairs"] = c.execute("SELECT count(*) FROM tr").fetchone()[0]
    out["periods"] = rows(c, "SELECT trust, p1, p2 FROM per ORDER BY 1")
    out["dpd_unit_months"] = [r["trust"] for r in rows(c, "SELECT trust FROM unit WHERE mult = 30")]

    # 1. monthly transitions by tier x band (and by band alone), from bucket to bucket
    def matrix(where=""):
        res = {}
        for r in rows(c, f"SELECT s1, s2, count(*) AS n FROM tr {where} GROUP BY 1, 2"):
            res.setdefault(r["s1"], {})[r["s2"]] = r["n"]
        return {s1: dict(n=sum(d.values()), p={s2: round(d.get(s2, 0) / sum(d.values()), 5) for s2 in STATES})
                for s1, d in res.items()}
    out["transitions"] = {"all": matrix()}
    for tier in ("subprime", "prime", "near-prime"):
        out["transitions"][tier] = matrix(f"WHERE tier = '{tier}'")
    for _, _, band in BANDS:
        out["transitions"][f"band {band}"] = matrix(f"WHERE band = '{band}'")
    # the generator's honest loans move month to month by these: credit band x loan age
    out["transitions_band_age"] = {f"{band}|{age}": matrix(f"WHERE band = '{band}' AND age_b = '{age}'")
                                   for _, _, band in BANDS for _, _, age in AGE}

    # 2. current with no payment in the month (honest servicers), and paid / scheduled when paying
    r = rows(c, """SELECT tier, count(*) AS n,
                          count(*) FILTER (WHERE coalesce(paid2, 0) = 0) AS nopay,
                          count(*) FILTER (WHERE coalesce(paid2, 0) = 0 AND coalesce(sched2, 0) > 0) AS nopay_due,
                          quantile_cont(paid2 / nullif(sched2, 0), [0.1, 0.25, 0.5, 0.75, 0.9])
                              FILTER (WHERE paid2 > 0 AND sched2 > 0) AS ratio_q
                   FROM tr WHERE s1 = 'current' AND s2 = 'current' GROUP BY 1 ORDER BY 1""")
    out["current_no_payment"] = {x["tier"]: dict(n=x["n"], share=round(x["nopay"] / x["n"], 5),
                                                 share_with_payment_due=round(x["nopay_due"] / x["n"], 5),
                                                 paid_over_scheduled_q10_25_50_75_90=[round(v, 3) for v in x["ratio_q"]])
                                 for x in r}
    per_pool = rows(c, """SELECT trust, count(*) AS n, count(*) FILTER (WHERE coalesce(paid2, 0) = 0) AS nopay
                          FROM tr WHERE s1 = 'current' AND s2 = 'current' GROUP BY 1""")
    out["current_no_payment_by_pool"] = sorted(round(x["nopay"] / x["n"], 4) for x in per_pool)

    # 3. 60+ days late one month, current the next: how often with no payment (and explained by an extension)
    r = rows(c, """SELECT count(*) AS n,
                          count(*) FILTER (WHERE coalesce(paid2, 0) = 0) AS nopay,
                          count(*) FILTER (WHERE coalesce(paid2, 0) = 0 AND (coalesce(ext2, 0) > 0 OR mod2)) AS nopay_ext
                   FROM tr WHERE s1 IN ('60-89', '90+') AND s2 = 'current'""")[0]
    base = c.execute("SELECT count(*) FROM tr WHERE s1 IN ('60-89', '90+')").fetchone()[0]
    out["late_to_current"] = dict(late_loans=base, became_current=r["n"], without_payment=r["nopay"],
                                  without_payment_but_extended_or_modified=r["nopay_ext"])

    # 4. credit score at origination should never change between reports
    r = rows(c, """SELECT count(*) AS n, count(*) FILTER (WHERE score1 <> score2) AS changed,
                          count(*) FILTER (WHERE score1 < 600 AND score2 >= 600) AS crossed_600
                   FROM tr WHERE score1 IS NOT NULL AND score2 IS NOT NULL""")[0]
    out["score_changes"] = dict(loans=r["n"], changed=r["changed"], crossed_600_upward=r["crossed_600"])

    # 5. the score distribution around common eligibility lines (a natural 'edge' share to compare against)
    edges = {}
    for line in (550, 575, 600, 620, 640, 660):
        x = rows(c, f"""SELECT tier, count(*) FILTER (WHERE score_ok >= {line}) AS above,
                               count(*) FILTER (WHERE score_ok >= {line} AND score_ok < {line + 13}) AS edge,
                               count(*) FILTER (WHERE score_ok >= {line - 13} AND score_ok < {line}) AS below
                        FROM open1 GROUP BY 1""")
        edges[str(line)] = {y["tier"]: dict(edge_share_of_eligible=round(y["edge"] / max(y["above"], 1), 4),
                                            ratio_just_above_to_just_below=round(y["edge"] / max(y["below"], 1), 3))
                            for y in x}
    out["score_edges"] = edges
    out["score_hist"] = {t: {str(int(k)): v for k, v in
                             c.execute(f"""SELECT floor(score_ok / 20) * 20 AS b, count(*) FROM open1
                                          WHERE tier = '{t}' AND score_ok IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()}
                         for t in ("subprime", "near-prime", "prime")}

    # 6. fingerprint uniqueness: without a VIN, how often does a loan's public profile point at one loan only?
    fp = """concat_ws('|', orig_ym, CAST(round(orig_amt, 2) AS VARCHAR), CAST(term AS VARCHAR),
                      CAST(round(rate, 4) AS VARCHAR), upper(make), upper(model), CAST(model_year AS VARCHAR),
                      state, CAST(score_ok AS VARCHAR))"""
    r = rows(c, f"""WITH f AS (SELECT trust, family, {fp} AS k FROM p2 WHERE coalesce(end_bal, 0) > 0),
                         g AS (SELECT k, count(*) AS n, count(DISTINCT trust) AS trusts, count(DISTINCT family) AS fams
                               FROM f GROUP BY 1)
                    SELECT count(*) AS loans,
                           count(*) FILTER (WHERE g.n = 1) AS unique_loans,
                           count(*) FILTER (WHERE g.trusts > 1) AS in_two_pools,
                           count(*) FILTER (WHERE g.fams > 1) AS across_lenders
                    FROM f JOIN g USING (k)""")[0]
    r2 = rows(c, f"""WITH f AS (SELECT trust, {fp.replace("state, CAST(score_ok AS VARCHAR)", "state")} AS k FROM p2
                                WHERE coalesce(end_bal, 0) > 0),
                          g AS (SELECT k, count(*) AS n FROM f GROUP BY 1)
                     SELECT count(*) FILTER (WHERE g.n = 1) AS unique_without_score FROM f JOIN g USING (k)""")[0]
    out["fingerprint"] = dict(fields="origination month, original amount, term, rate, make, model, model year, state, credit score",
                              **r, unique_share=round(r["unique_loans"] / r["loans"], 5),
                              unique_share_without_score=round(r2["unique_without_score"] / r["loans"], 5))

    # 7. per-pool metrics, and expected 30+ share from credit-band x loan-age cells (for the benchmark)
    cells = rows(c, """SELECT trust, family, band, age_b, count(*) AS n,
                              count(*) FILTER (WHERE status IN ('30-59', '60-89', '90+')) AS late
                       FROM open1 GROUP BY 1, 2, 3, 4 ORDER BY 1, 3, 4""")
    out["cells"] = cells
    pools = rows(c, """SELECT trust, family, tier, count(*) AS open_loans,
                              avg(CASE WHEN status IN ('30-59', '60-89', '90+') THEN 1 ELSE 0 END) AS late30,
                              avg(CASE WHEN status IN ('60-89', '90+') THEN 1 ELSE 0 END) AS late60,
                              avg(score_ok) AS avg_score, avg(age) AS avg_age
                       FROM open1 GROUP BY 1, 2, 3 ORDER BY 3, 1""")
    out["pool_metrics"] = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in pools]

    # 8. behaviour per pool: what honest servicers' tapes look like month to month. These set S2's thresholds.
    c.execute("""CREATE TABLE tr2 AS
        SELECT a.trust, a.family, a.tier, a.status AS s1, b.status AS s2, coalesce(a.paid, 0) AS paid1,
               coalesce(b.paid, 0) AS paid2, coalesce(b.extended, 0) AS ext2, coalesce(b.modified, false) AS mod2
        FROM open1 a JOIN p2 b ON a.trust = b.trust AND a.asset = b.asset WHERE b.status <> 'other_exit'""")
    beh = rows(c, """SELECT trust, family, tier,
        count(*) FILTER (WHERE s1 = 'current' AND s2 = 'current') AS current_both,
        count(*) FILTER (WHERE s1 = 'current' AND s2 = 'current' AND paid1 = 0 AND paid2 = 0) AS current_no_pay_2m,
        count(*) FILTER (WHERE s1 = '30-59') AS late30,
        count(*) FILTER (WHERE s1 = '30-59' AND s2 IN ('60-89', '90+', 'charged_off')) AS rolled_forward,
        count(*) FILTER (WHERE s1 = '30-59' AND s2 = 'current') AS cured,
        count(*) FILTER (WHERE s1 = '30-59' AND s2 = 'current' AND paid2 = 0 AND ext2 = 0 AND NOT mod2) AS cured_no_pay,
        count(*) FILTER (WHERE s1 IN ('60-89', '90+')) AS late60,
        count(*) FILTER (WHERE s1 IN ('60-89', '90+') AND s2 = 'current' AND paid2 = 0 AND ext2 = 0 AND NOT mod2)
            AS late60_current_no_pay
        FROM tr2 GROUP BY 1, 2, 3 ORDER BY 3, 1""")
    for b in beh:
        b["current_no_pay_2m_share"] = round(b["current_no_pay_2m"] / max(b["current_both"], 1), 5)
        b["roll_forward_rate"] = round(b["rolled_forward"] / max(b["late30"], 1), 4)
        b["late60_current_no_pay_share"] = round(b["late60_current_no_pay"] / max(b["late60"], 1), 4)
    out["pool_behaviour"] = beh
    # 9. just above the 600 line: loans at 600-612 vs 613-625, both eligible. A lender's natural score curve keeps
    #    these close; scores rewritten to clear the line pile up in the first band.
    edge = rows(c, """SELECT trust, tier, count(*) FILTER (WHERE score_ok BETWEEN 600 AND 612) AS a1,
                             count(*) FILTER (WHERE score_ok BETWEEN 613 AND 625) AS a2
                      FROM open1 GROUP BY 1, 2 ORDER BY 1""")
    out["edge_600"] = [dict(e, ratio=round(e["a1"] / e["a2"], 3)) for e in edge if e["a2"] > 0]
    out["real_extremes"] = dict(
        max_edge_ratio_600=max(e["ratio"] for e in out["edge_600"] if e["a1"] + e["a2"] >= 40),
        max_current_no_pay_2m_share=max(b["current_no_pay_2m_share"] for b in beh),
        min_roll_forward_rate=min(b["roll_forward_rate"] for b in beh if b["late30"] >= 50),
        max_late60_current_no_pay_share=max(b["late60_current_no_pay_share"] for b in beh if b["late60"] >= 40),
        pools=len(beh))

    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "absee_auto.json"), "w"), indent=1, default=str)

    # real loan attributes for the generator (no identity: no asset number, no servicer, no dates beyond month)
    c.execute(f"""COPY (SELECT tier, band, orig_amt, term, rate, make, model, model_year, new_used, score_ok AS score,
                               pti, state
                        FROM open1 WHERE score_ok IS NOT NULL AND orig_amt > 0 AND term > 0 AND make IS NOT NULL
                        USING SAMPLE 30000 ROWS (reservoir, 7))
                  TO '{os.path.join(OUT, "absee_auto_sample.parquet")}' (FORMAT parquet, COMPRESSION zstd)""")
    return out


# months a loan can sit on one of our books' tapes: the rule counts any month of its life there
BOOK_MONTHS = 24


def balance_rises(c) -> dict:
    """How often an honest servicer shows a current, paid, unmodified loan's balance going UP within a month: what
    S2's BALANCE_ROSE_WHILE_PAID must stay clear of. Same rise test as the check: over max($1, 0.1%).
    The check counts a loan once if it rose in any month of its life on the tape, so each pool's monthly rate is
    projected over BOOK_MONTHS: 1 - (1 - p)^24."""
    pools = rows(c, """
        SELECT trust, family, tier,
               count(*) AS loan_months,
               count(*) FILTER (WHERE end_bal - beg_bal > greatest(1.0, 0.001 * beg_bal)) AS rose,
               count(*) FILTER (WHERE end_bal - beg_bal > 1.0) AS rose_1usd,
               max(end_bal - beg_bal) AS max_rise
        FROM s
        WHERE status = 'current' AND coalesce(paid, 0) > 0 AND NOT coalesce(modified, false)
          AND coalesce(extended, 0) = 0 AND coalesce(beg_bal, 0) > 0 AND end_bal IS NOT NULL
        GROUP BY 1, 2, 3 ORDER BY 3, 1""")
    for p in pools:
        p["monthly_rate"] = p["rose"] / max(p["loan_months"], 1)
        p["projected_share"] = round(1 - (1 - p["monthly_rate"]) ** BOOK_MONTHS, 5)
        p["monthly_rate"] = round(p["monthly_rate"], 6)
        p["max_rise"] = round(p["max_rise"] or 0.0, 2)
    return dict(pools=pools, book_months=BOOK_MONTHS,
                max_monthly_rate=max(p["monthly_rate"] for p in pools),
                max_projected_share=max(p["projected_share"] for p in pools),
                pools_with_a_rise_over_1usd=sum(p["rose_1usd"] > 0 for p in pools), n_pools=len(pools))


def contract_collisions(c) -> dict:
    """S1's same-facility check calls two loan numbers one contract when they share the customer, the origination
    month and the amount. ABS-EE has no customer ID, so this measures the key WITHOUT it, within each pool and report:
    an upper bound on how often two different real loans could collide. With the lender's own customer ID added, two
    loans collide only if one customer took out two loans in the same month for the same amount."""
    keys = {"month+amount": "orig_ym, orig_amt",
            "month+amount+term+rate+state": "orig_ym, orig_amt, term, rate, state",
            "month+amount+term+rate+state+make+model+year": "orig_ym, orig_amt, term, rate, state, make, model, model_year"}
    out = {}
    for name, cols in keys.items():
        r = c.execute(f"""
            WITH o AS (SELECT * FROM s WHERE coalesce(end_bal, 0) > 0 AND orig_amt > 0 AND orig_ym IS NOT NULL),
            g AS (SELECT trust, period_end, {cols}, count(DISTINCT asset) AS n FROM o GROUP BY ALL)
            SELECT (SELECT count(*) FROM o), coalesce(sum(n) FILTER (WHERE n > 1), 0), count(*) FILTER (WHERE n > 1)
            FROM g""").fetchone()
        out[name] = dict(open_loan_rows=r[0], loans_sharing_the_key=int(r[1]), shared_keys=int(r[2]),
                         share=round(r[1] / max(r[0], 1), 6))
    return out


def patch(fields: dict) -> None:
    """Add measurements to absee_auto.json without rebuilding the rest (the sample the generator draws from stays)."""
    p = os.path.join(OUT, "absee_auto.json")
    o = json.load(open(p))
    o.update(fields)
    json.dump(o, open(p, "w"), indent=1, default=str)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--round3-facts"]:
        cc = con()
        f = dict(balance_rises=balance_rises(cc), contract_collisions=contract_collisions(cc))
        patch(f)
        print(json.dumps({"balance_rises": {k: v for k, v in f["balance_rises"].items() if k != "pools"},
                          "contract_collisions": f["contract_collisions"]}, indent=1))
        sys.exit(0)
    o = run()
    print(json.dumps({k: o[k] for k in ("files", "loan_rows", "open_loans_month1", "pairs", "current_no_payment",
                                        "late_to_current", "score_changes", "fingerprint")}, indent=1, default=str))
