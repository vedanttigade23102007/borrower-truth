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
                            disagrees with the tape. A loan that rolled from 30-59 to 60-89
                            days late this month while the tape (cut a few days earlier) still
                            says 30-59 is a timing difference: shown as "timing, unconfirmed"
                            and excused for one month. Still behind next month, or 3 or more
                            at once in one pull, and it counts.
  TARGETED_SOURCE_MISMATCH  the pull a sharp auditor makes: loans the tape calls
                            current but that paid nothing (bank-payment evidence)
                            are pulled from the servicer system, and are 60+ late
                            or gone. A random sample misses a small dress-up; a
                            cash-targeted pull of the same size does not. A second
                            pull takes loans that went straight from 30-59 days late
                            to current: that catches dress-up even when the borrower
                            pays the hidden loans itself, so the cash looks fine.
                            A third pull takes the largest loans that first appeared on the
                            tape in the last year, the way a field examiner tests the biggest
                            new items first: a few large invented loans that are kept paying
                            can slip past a random sample and past the unpaid-loan pull.
  ATTRIBUTE_REWRITE         a loan's credit score at origination should never change;
                            several were rewritten from below the 600 eligibility line
                            to above it (Tricolor, as alleged: ineligible collateral
                            made to meet lender requirements)
  ELIGIBILITY_EDGE_CLUSTER  far more eligible loans sit just above the line than the
                            rest of the book would predict (statistical, weaker)
  ROLL_RATE_TOO_LOW         late loans almost never get later: of loans 30-59 days late,
                            hardly any are 60+ late the next month. Hiding 60+ day loans
                            does exactly that. Judged against 28 real public auto pools
                            (SEC ABS-EE), where the lowest honest rate is 13.9%.

Thresholds checked against real servicer data (SEC ABS-EE, 28 public auto-loan pools, 22
lenders, April-May 2026; bt/sec/calibrate.py -> data/calibration/absee_auto.json):
  - loans reported current with no payment in two consecutive months: at most 1.96% in any
    real pool, so CURRENT_WITHOUT_PAYMENT's 3% line leaves honest servicers below it;
  - 60+ days late -> current next month with no payment and no extension/modification: up to
    12.2% of late loans in one real prime pool, so IMPOSSIBLE_TRANSITION now needs a share
    above 20% as well as a count (a count alone would flag that honest pool);
  - a loan's credit score at origination changed between monthly reports: 0 of 774,975 real
    loans, so ATTRIBUTE_REWRITE has no honest base rate to hide in.
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
SELECT j.borrower_id, count(DISTINCT j.asset_id) AS n, min(j.month) AS first_m,
       list(DISTINCT j.asset_id ORDER BY j.asset_id)[1:3] AS ex
FROM jump j LEFT JOIN p ON p.asset_id = j.asset_id AND p.month BETWEEN j.month AND j.month + 1
WHERE p.asset_id IS NULL
GROUP BY 1
"""

LATE60 = """
SELECT borrower_id, count(DISTINCT asset_id) AS n FROM tape
WHERE asset_id LIKE 'A-%' AND month BETWEEN ? AND ? AND dpd_bucket_reported >= 2 GROUP BY 1
"""

ROLL = """
WITH a AS (
    SELECT borrower_id, asset_id, month, dpd_bucket_reported AS r FROM tape
    WHERE asset_id LIKE 'A-%' AND facility_id LIKE '%A' AND month BETWEEN ? AND ?
)
SELECT p.borrower_id, count(*) AS late30, count(*) FILTER (WHERE c.r >= 2) AS rolled
FROM a p JOIN a c ON c.asset_id = p.asset_id AND c.month = p.month + 1
WHERE p.r = 1
GROUP BY 1
"""

SAMPLE = """
WITH elig AS (
    SELECT borrower_id, asset_id, month, dpd_bucket_reported AS r,
           row_number() OVER (PARTITION BY borrower_id ORDER BY hash(asset_id || CAST(month AS VARCHAR) || 'audit')) AS k
    FROM tape WHERE month = ? AND asset_id LIKE 'A-%' AND eligible_reported
)
SELECT e.borrower_id, e.asset_id, e.r, s.dpd_bucket_true AS tr, sp.dpd_bucket_true AS prev_tr, s.asset_id IS NULL AS gone
FROM elig e LEFT JOIN source_truth s ON s.asset_id = e.asset_id AND s.month = e.month
LEFT JOIN source_truth sp ON sp.asset_id = e.asset_id AND sp.month = e.month - 1
WHERE e.k <= ?
ORDER BY 1, 2
"""

TARGETED = """
WITH cur AS (
    SELECT borrower_id, asset_id, month FROM tape
    WHERE month = ? AND asset_id LIKE 'A-%' AND dpd_bucket_reported = 0 AND eligible_reported
), paid AS (
    SELECT DISTINCT ref AS asset_id FROM payments WHERE ref LIKE 'A-%' AND month BETWEEN ? AND ?
), cand AS (
    SELECT c.*, row_number() OVER (PARTITION BY c.borrower_id ORDER BY hash(c.asset_id || 'targeted')) AS k
    FROM cur c LEFT JOIN paid p USING (asset_id) WHERE p.asset_id IS NULL
)
SELECT c.borrower_id, count(*) AS pulled,
       count(*) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2) AS mismatches,
       list(c.asset_id ORDER BY c.asset_id) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2)[1:3] AS ex
FROM cand c LEFT JOIN source_truth s ON s.asset_id = c.asset_id AND s.month = c.month
WHERE c.k <= ?
GROUP BY 1
"""

LARGEST_RECENT = """
WITH seen AS (SELECT asset_id, min(month) AS m0 FROM tape WHERE asset_id LIKE 'A-%' GROUP BY 1),
cand AS (
    SELECT t.borrower_id, t.asset_id, t.month, t.dpd_bucket_reported AS r,
           row_number() OVER (PARTITION BY t.borrower_id ORDER BY t.balance DESC, t.asset_id) AS k
    FROM tape t JOIN seen USING (asset_id)
    WHERE t.month = ? AND t.asset_id LIKE 'A-%' AND t.eligible_reported AND seen.m0 >= ?
)
SELECT c.borrower_id, c.asset_id, c.r, s.dpd_bucket_true AS tr, sp.dpd_bucket_true AS prev_tr, s.asset_id IS NULL AS gone
FROM cand c LEFT JOIN source_truth s ON s.asset_id = c.asset_id AND s.month = c.month
LEFT JOIN source_truth sp ON sp.asset_id = c.asset_id AND sp.month = c.month - 1
WHERE c.k <= ?
ORDER BY 1, 2
"""

# last month's timing differences, looked up again this month: did the tape catch up?
FOLLOW_UP = """
SELECT t.asset_id, t.eligible_reported AS el, t.dpd_bucket_reported AS r, s.dpd_bucket_true AS tr, s.asset_id IS NULL AS gone
FROM tape t LEFT JOIN source_truth s ON s.asset_id = t.asset_id AND s.month = t.month
WHERE t.month = ? AND list_contains(?::VARCHAR[], t.asset_id)
ORDER BY 1
"""

CURED = """
WITH a AS (
    SELECT borrower_id, asset_id, month, dpd_bucket_reported AS r FROM tape
    WHERE asset_id LIKE 'A-%' AND facility_id LIKE '%A' AND month BETWEEN ? AND ?
), c AS (
    SELECT cur.borrower_id, cur.asset_id, cur.month,
           row_number() OVER (PARTITION BY cur.borrower_id ORDER BY hash(cur.asset_id || 'cure')) AS k
    FROM a cur JOIN a prev ON prev.asset_id = cur.asset_id AND prev.month = cur.month - 1
    WHERE prev.r = 1 AND cur.r = 0 AND cur.month >= ?
)
SELECT c.borrower_id, count(*) AS pulled,
       count(*) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2) AS mismatches,
       list(c.asset_id ORDER BY c.asset_id) FILTER (WHERE s.asset_id IS NULL OR s.dpd_bucket_true >= 2)[1:3] AS ex
FROM c LEFT JOIN source_truth s ON s.asset_id = c.asset_id AND s.month = c.month
WHERE c.k <= ?
GROUP BY 1
"""

REWRITE = """
WITH a AS (
    SELECT borrower_id, vin, arg_min(credit_score, month) AS first_s, arg_max(credit_score, month) AS last_s,
           min(month) FILTER (WHERE credit_score >= ?) AS m_over
    FROM tape WHERE credit_score IS NOT NULL GROUP BY 1, 2
)
SELECT borrower_id, count(*) AS loans,
       count(*) FILTER (WHERE first_s < ? AND last_s >= ?) AS crossed,
       min(m_over) FILTER (WHERE first_s < ? AND last_s >= ?) AS first_m,
       list(vin ORDER BY vin) FILTER (WHERE first_s < ? AND last_s >= ?)[1:3] AS ex
FROM a GROUP BY 1
"""

EDGE = """
WITH e AS (
    SELECT borrower_id, vin, any_value(credit_score) AS s FROM tape
    WHERE month = ? AND credit_score BETWEEN ? AND ? GROUP BY 1, 2
)
SELECT borrower_id, count(*) FILTER (WHERE s < ?) AS a1, count(*) FILTER (WHERE s >= ?) AS a2 FROM e GROUP BY 1
"""
# Just above the line, a lender's own score curve keeps the two bands 600-612 and 613-625 close. Across 28 real public
# auto pools the first band is at most 1.18x the second (Drive Auto 2024-1). Comparing a tape with itself, not with the
# book, keeps prime and subprime lenders (different curves) from being judged against each other.
EDGE_RATIO_REAL, EDGE_FACTOR, EDGE_MIN, EDGE_Z = 1.18, 1.5, 40, 3.0

SAMPLE_SIZE = 60
TARGETED_SIZE = 30
CURE_SIZE = 30  # loans that went from 30-59 days late to current, looked up in the servicer system
LARGEST_SIZE, LARGEST_NEW_MONTHS = 30, 12  # the largest loans first seen on the tape in the last year
# a tape cut a few days before the servicer's month end catches only a handful of loans rolling into 60+ days late:
# honest dev pulls never held more than 1 at once. From 3 in one pull, it's not timing (set knowing that the one honest
# case on fresh seeds 804 had 2, so the next fresh set is the real test of this line)
TIMING_MANY = 3


def _state(x) -> str:
    if x["gone"]:
        return "gone"
    if x["tr"] >= 2:
        # 30-59 on the tape, 60-89 in the servicer, 30-59 there last month: it rolled between the two cut-off dates
        return "timing" if x["r"] == 1 and x["tr"] == 2 and x["prev_tr"] == 1 else "late"
    return "ok"


def judge_pull(ctx: Ctx, sql: str, now_args: list, prev_args: list | None) -> dict:
    """One servicer-system pull, per borrower: loans that disagree, this month's timing differences, and last month's
    timing differences the tape still hasn't caught up with (looked up again this month)."""
    a = ctx.as_of
    now: dict[str, list] = {}
    for x in ctx.rows(sql, now_args):
        now.setdefault(x["borrower_id"], []).append(x)
    prev: dict[str, list] = {}
    if prev_args is not None:
        for x in ctx.rows(sql, prev_args):
            if _state(x) == "timing":
                prev.setdefault(x["borrower_id"], []).append(x["asset_id"])
    ids = sorted(i for v in prev.values() for i in v)
    behind = {x["asset_id"] for x in (ctx.rows(FOLLOW_UP, [a, ids]) if ids else [])
              if x["el"] and x["r"] <= 1 and (x["gone"] or x["tr"] >= 2)}
    out = {}
    for b in sorted(set(now) | set(prev)):
        loans = now.get(b, [])
        here = {x["asset_id"] for x in loans}
        still = [i for i in prev.get(b, []) if i in behind and i not in here]
        out[b] = dict(pulled=len(loans) + len(still), still=still,
                      mism=[x["asset_id"] for x in loans if _state(x) in ("gone", "late")],
                      timing=[x["asset_id"] for x in loans if _state(x) == "timing"])
    return out


def settle_timing(*pulls: dict) -> dict:
    """A timing difference is excused for one month only. It counts as a mismatch if the tape hasn't caught up by the
    next month, or if many loans are behind at once (counted per borrower across every pull)."""
    timing: dict[str, set] = {}
    for pull in pulls:
        for b, p in pull.items():
            timing.setdefault(b, set()).update(p["timing"])
    many = {b for b, t in timing.items() if len(t) >= TIMING_MANY}
    for pull in pulls:
        for b, p in pull.items():
            p["many"] = b in many
            p["mism"] = sorted(p["mism"] + p["still"] + (p["timing"] if b in many else []))
    return {b: sorted(t) for b, t in timing.items() if t and b not in many}


def _why(p: dict) -> str:
    s = ""
    if p["still"]:
        s += f"; {len(p['still'])} were noted last month as a timing difference and the tape still hasn't caught up"
    if p["many"] and p["timing"]:
        s += "; several had just rolled from 30-59 to 60+ days late, but that many at once is not a cut-off timing difference"
    return s
JUMP_SHARE = 0.20  # real honest pools reach 12.2% (bt/sec/calibrate.py); a count alone isn't enough
ROLL_MIN_REAL = 0.139  # lowest 30->60+ roll-forward rate among 28 real public auto pools (Ford Credit 2024-A)
ROLL_FACTOR, ROLL_WINDOW, ROLL_MIN_N, ROLL_Z = 0.5, 6, 30, -2.5
ELIGIBLE_SCORE, EDGE_BAND = 600, 13  # the facility's eligibility rule, and "just above it"  # same order of cost as the random sample: a handful of loans looked up by hand


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
        late60 = {r["borrower_id"]: r["n"] for r in ctx.rows(LATE60, [max(0, lo - 1), a - 1])}
        for r in ctx.rows(TRANSITIONS, [max(0, lo - 1), a, max(1, lo)]):
            share = r["n"] / max(late60.get(r["borrower_id"], 0), 1)
            if r["n"] >= 3 and share >= JUMP_SHARE:
                out.append(sig("S2", r["borrower_id"], "IMPOSSIBLE_TRANSITION", 0.75, 0.85,
                               [f"tape:asset:{x}" for x in r["ex"]] + [f"count:{r['n']}", f"share_of_60plus:{share:.2f}"],
                               f"{r['n']} loans jumped from 60+ days late to current with no payment "
                               f"({share:.0%} of loans that were 60+ late)", r["first_m"]))
    if a >= 2:
        for r in ctx.rows(ROLL, [max(0, a - ROLL_WINDOW), a]):
            n, k = r["late30"], r["rolled"]
            if n < ROLL_MIN_N:
                continue
            rate = k / n
            z = (rate - ROLL_MIN_REAL) / (ROLL_MIN_REAL * (1 - ROLL_MIN_REAL) / n) ** 0.5
            if rate < ROLL_MIN_REAL * ROLL_FACTOR and z < ROLL_Z:
                out.append(sig("S2", r["borrower_id"], "ROLL_RATE_TOO_LOW", 0.6, 0.7,
                               [f"tape:{r['borrower_id']}:months={max(0, a - ROLL_WINDOW)}-{a}:rolled={k}/{n}",
                                f"public_abs:min_roll_forward={ROLL_MIN_REAL}"],
                               f"Only {k} of {n} loans reported 30-59 days late were 60+ late a month later ({rate:.0%}). "
                               f"In 28 real public auto-loan pools the lowest rate is {ROLL_MIN_REAL:.0%}: "
                               f"late loans here seem to vanish instead of getting later", a))
    sample = judge_pull(ctx, SAMPLE, [a, SAMPLE_SIZE], [a - 1, SAMPLE_SIZE] if a >= 1 else None)
    largest = judge_pull(ctx, LARGEST_RECENT, [a, a - LARGEST_NEW_MONTHS + 1, LARGEST_SIZE],
                         [a - 1, a - LARGEST_NEW_MONTHS, LARGEST_SIZE] if a >= 1 else None)
    unconfirmed = settle_timing(sample, largest)
    for b, p in sample.items():
        n = len(p["mism"])
        if n >= 2 and n / p["pulled"] > 0.02:
            out.append(sig("S2", b, "SOURCE_MISMATCH", 0.9, 0.8 if n == 2 else 0.92,
                           [f"source_pull:{b}:month={a}"] + [f"tape:asset:{x}" for x in p["mism"][:3]],
                           f"Servicer-system pull: {n} of {p['pulled']} sampled 'eligible' loans are actually 60+ days "
                           f"late or no longer active{_why(p)}", a))
    if a >= 1:
        for r in ctx.rows(TARGETED, [a, a - 1, a, TARGETED_SIZE]):
            if r["mismatches"] >= 2:
                out.append(sig("S2", r["borrower_id"], "TARGETED_SOURCE_MISMATCH", 0.9, 0.92,
                               [f"source_pull:{r['borrower_id']}:month={a}:targeted_by=no_payment"]
                               + [f"tape:asset:{x}" for x in r["ex"]],
                               f"Loans reported current but with no payment for two months were pulled from the "
                               f"servicer system: {r['mismatches']} of {r['pulled']} are actually 60+ days late or "
                               f"no longer active", a))
    for b, p in largest.items():
        if len(p["mism"]) >= 2:
            out.append(sig("S2", b, "TARGETED_SOURCE_MISMATCH", 0.9, 0.92,
                           [f"source_pull:{b}:month={a}:targeted_by=largest_new"]
                           + [f"tape:asset:{x}" for x in p["mism"][:3]],
                           f"The largest loans added to the tape in the last year were pulled from the servicer system: "
                           f"{len(p['mism'])} of {p['pulled']} are 60+ days late or not there at all{_why(p)}", a))
    for b, ids in unconfirmed.items():  # this month's timing differences can only be confirmed next month
        out.append(sig("S2", b, "TIMING_UNCONFIRMED", 0.1, 1.0,
                       [f"source_pull:{b}:month={a}:timing"] + [f"tape:asset:{x}" for x in ids[:3]],
                       f"Timing, unconfirmed: {len(ids)} pulled loan(s) are 60-89 days late in the servicer system "
                       f"but 30-59 on the tape. Each rolled into 60+ this month, which a tape cut a few days before "
                       f"month end explains. If the tape hasn't caught up next month, they count as mismatches", a))
    if a >= 2:
        # the pull a sharp auditor makes when late loans seem to vanish: the loans that went straight from 30-59 days
        # late to current. Real cures are current in the servicer system; a hidden 60+ day loan is not.
        for r in ctx.rows(CURED, [a - 2, a, a - 1, CURE_SIZE]):
            if r["mismatches"] >= 2:
                out.append(sig("S2", r["borrower_id"], "TARGETED_SOURCE_MISMATCH", 0.9, 0.92,
                               [f"source_pull:{r['borrower_id']}:month={a}:targeted_by=cure_from_30"]
                               + [f"tape:asset:{x}" for x in r["ex"]],
                               f"Loans the tape shows going from 30-59 days late to current were pulled from the servicer "
                               f"system: {r['mismatches']} of {r['pulled']} are actually 60+ days late or no longer active",
                               a))
    if "credit_score" in {r[0] for r in ctx.con.execute("DESCRIBE tape").fetchall()}:  # older books lack it
        L = ELIGIBLE_SCORE
        for r in ctx.rows(REWRITE, [L, L, L, L, L, L, L]):
            if r["crossed"] >= 3:
                out.append(sig("S2", r["borrower_id"], "ATTRIBUTE_REWRITE", 0.85, 0.9,
                               [f"tape:vin:{v}" for v in r["ex"]] + [f"count:{r['crossed']}"],
                               f"{r['crossed']} loans' credit scores at origination were rewritten after the fact, "
                               f"from below the {L} eligibility line to above it", r["first_m"]))
        p = EDGE_RATIO_REAL / (1 + EDGE_RATIO_REAL)  # the first band's share of both, at the real maximum
        for r in ctx.rows(EDGE, [a, L, L + 2 * EDGE_BAND - 1, L + EDGE_BAND, L + EDGE_BAND]):
            a1, a2 = r["a1"], r["a2"]
            n = a1 + a2
            if n < EDGE_MIN:
                continue
            ratio = a1 / max(a2, 1)
            z = (a1 - n * p) / (n * p * (1 - p)) ** 0.5
            if ratio > EDGE_RATIO_REAL * EDGE_FACTOR and z > EDGE_Z:
                out.append(sig("S2", r["borrower_id"], "ELIGIBILITY_EDGE_CLUSTER", 0.5, 0.6,
                               [f"tape:{r['borrower_id']}:month={a}:score_{L}-{L + EDGE_BAND - 1}={a1}",
                                f"tape:{r['borrower_id']}:month={a}:score_{L + EDGE_BAND}-{L + 2 * EDGE_BAND - 1}={a2}",
                                f"public_abs:max_ratio={EDGE_RATIO_REAL}"],
                               f"{a1} loans sit at {L}-{L + EDGE_BAND - 1}, just over the eligibility line, against {a2} at "
                               f"{L + EDGE_BAND}-{L + 2 * EDGE_BAND - 1} ({ratio:.1f}x). In 28 real public auto pools the "
                               f"highest is {EDGE_RATIO_REAL}x: scores look nudged over the line", a))
    return out
