"""S2 Tape-vs-source: does the loan tape match the system it came from?

Mechanism: Tricolor made "non-paying or defaulted loans appear current" and
manipulated collateral so ineligible assets met lender requirements (VERIFY T3,
T6). Its CEO, on a recorded call, said the problem would come if an auditor
asked to "pull this up on your screen" (T7), and proposed blaming discrepancies
on "fictitious deferment policies". This system automates that auditor.

Checks (window = the three most recent complete months):
  CURRENT_WITHOUT_PAYMENT   reported current, but no payment arrived for that loan
  DEFERMENT_WITHOUT_PROGRAM deferral flags with no disclosed deferment programme
  IMPOSSIBLE_TRANSITION     60+ days late one month, current the next, no payment
  SOURCE_MISMATCH           risk-weighted sample pulled from the servicer system
                            disagrees with the tape
"""
from bt.systems.base import Ctx, sig

CURRENT_NO_PAY = """
WITH t AS (
    SELECT borrower_id, month, asset_id, deferred_flag FROM tape
    WHERE dpd_bucket_reported = 0 AND month BETWEEN ? AND ? AND asset_id LIKE 'A-%'
), p AS (
    SELECT DISTINCT ref AS asset_id, month FROM payments WHERE ref LIKE 'A-%'
), prog AS (
    SELECT borrower_id, start_month FROM disclosures WHERE kind = 'deferment_program'
), x AS (
    SELECT t.borrower_id, t.month, t.asset_id, any_value(t.deferred_flag) AS deferred_flag,
           bool_or(p.asset_id IS NOT NULL) AS paid
    FROM t LEFT JOIN p ON p.asset_id = t.asset_id AND p.month BETWEEN t.month AND t.month + 1
    GROUP BY 1, 2, 3
), y AS (
    SELECT x.*, EXISTS (SELECT 1 FROM prog WHERE prog.borrower_id = x.borrower_id
                        AND x.month BETWEEN prog.start_month AND prog.start_month + 2) AS in_prog
    FROM x
)
SELECT borrower_id, count(*) AS n,
       count(*) FILTER (WHERE NOT paid AND NOT (deferred_flag = 1 AND in_prog)) AS nopay,
       count(*) FILTER (WHERE deferred_flag = 1 AND NOT in_prog) AS def_noprog,
       count(*) FILTER (WHERE deferred_flag = 1 AND in_prog) AS def_prog
FROM y GROUP BY 1
"""

TRANSITIONS = """
WITH a AS (
    SELECT borrower_id, asset_id, month, dpd_bucket_reported AS r FROM tape
    WHERE asset_id LIKE 'A-%' AND month BETWEEN ? AND ?
), jump AS (
    SELECT cur.borrower_id, cur.asset_id, cur.month FROM a cur
    JOIN a prev ON prev.asset_id = cur.asset_id AND prev.month = cur.month - 1
    WHERE prev.r >= 2 AND cur.r = 0 AND cur.month >= ?
), p AS (SELECT DISTINCT ref AS asset_id, month FROM payments WHERE ref LIKE 'A-%')
SELECT j.borrower_id, count(DISTINCT j.asset_id) AS n, min(j.month) AS first_m, list(DISTINCT j.asset_id)[1:3] AS ex
FROM jump j LEFT JOIN p ON p.asset_id = j.asset_id AND p.month BETWEEN j.month AND j.month + 1
WHERE p.asset_id IS NULL
GROUP BY 1
"""

SAMPLE = """
WITH elig AS (
    SELECT borrower_id, asset_id, month, dpd_bucket_reported AS r,
           row_number() OVER (PARTITION BY borrower_id ORDER BY hash(asset_id || CAST(month AS VARCHAR) || 'audit')) AS k
    FROM tape WHERE month = ? AND asset_id LIKE 'A-%' AND eligible_reported
)
SELECT e.borrower_id, count(*) AS sampled,
       count(*) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2) AS mismatches,
       list(e.asset_id) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2)[1:3] AS ex
FROM elig e LEFT JOIN source_truth s ON s.asset_id = e.asset_id AND s.month = e.month
WHERE e.k <= ?
GROUP BY 1
"""

SAMPLE_SIZE = 60


def run(ctx: Ctx):
    out = []
    a = ctx.as_of
    lo, hi = max(0, a - 3), a - 1
    if hi >= lo:
        for r in ctx.rows(CURRENT_NO_PAY, [lo, hi]):
            b, n = r["borrower_id"], r["n"]
            if r["def_prog"]:
                ctx.explain(b, f"{r['def_prog']} deferred loans are covered by a disclosed deferment programme")
            if n >= 50 and r["nopay"] / n > 0.03:
                rate = r["nopay"] / n
                out.append(sig("S2", b, "CURRENT_WITHOUT_PAYMENT", min(1.0, rate * 5), 0.8,
                               [f"tape:{b}:months={lo}-{hi}", f"payments:{b}:no_match={r['nopay']}/{n}"],
                               f"{rate:.1%} of loans reported current had no payment arrive ({r['nopay']} of {n})", hi))
            if n >= 50 and r["def_noprog"] / n > 0.01:
                out.append(sig("S2", b, "DEFERMENT_WITHOUT_PROGRAM", 0.7, 0.85,
                               [f"tape:{b}:deferred_flag:months={lo}-{hi}", f"disclosures:{b}#deferment_program:none"],
                               f"{r['def_noprog']} loans flagged 'deferred' with no disclosed deferment programme", hi))
    if a >= 1:
        for r in ctx.rows(TRANSITIONS, [max(0, lo - 1), a, max(1, lo)]):
            if r["n"] >= 3:
                out.append(sig("S2", r["borrower_id"], "IMPOSSIBLE_TRANSITION", 0.75, 0.85,
                               [f"tape:asset:{x}" for x in r["ex"]] + [f"count:{r['n']}"],
                               f"{r['n']} loans jumped from 60+ days late to current with no payment", r["first_m"]))
    for r in ctx.rows(SAMPLE, [a, SAMPLE_SIZE]):
        if r["mismatches"] >= 2 and r["mismatches"] / r["sampled"] > 0.02:
            out.append(sig("S2", r["borrower_id"], "SOURCE_MISMATCH", 0.9, 0.8 if r["mismatches"] == 2 else 0.92,
                           [f"source_pull:{r['borrower_id']}:month={a}"] + [f"tape:asset:{x}" for x in r["ex"]],
                           f"Servicer-system pull: {r['mismatches']} of {r['sampled']} sampled 'eligible' loans are "
                           f"actually 60+ days late or no longer active", a))
    return out
