"""S1 Collateral integrity: is this collateral unique and clean?

Mechanism: the same collateral pledged to several lenders (Tricolor T1/T2,
First Brands F1).

1. Ingests the (simulated) Setpoint PledgeCheck result, which WF backs (S1/S3 in
   VERIFY). We do not rebuild it; its FAILs become signals.
2. Checks uniqueness INSIDE Wells Fargo across all WF facilities. Matching is by
   VIN / obligor fingerprint, not only asset ID, because a second pledge can
   relabel the ID.
3. The same invoice (same number, same amount) pledged to two WF facilities.
4. PLEDGECHECK_ABSENT: the borrower isn't enrolled in PledgeCheck, so nobody can
   see whether its collateral is also pledged at *other* lenders. Context for the
   officer (a coverage gap), never evidence of fraud: it doesn't move the verdict
   or the queue.
5. PUBLIC_POOL_OVERLAP: a lender that sells loans into public securitizations reports
   every one of them to investors each month (SEC Form ABS-EE). Loans on the Wells
   Fargo tape that match, field for field, loans in the borrower's own public pool,
   two months running, may be pledged twice. ABS-EE has no VIN, so the match is a
   fingerprint (origination month, amount, term, rate, make, model, year, state,
   credit score). Measured on 787,944 real public loans, that fingerprint pointed at
   a single loan 99.99% of the time. It opens a question (ask for the VINs), never
   closes one. Since 2 Oct 2026 the match allows the small differences one loan shows
   in two reports (amount within 2%, credit score within 10 points): an exact match
   was beaten by nudging those two fields (blind red team). On the same real loans,
   that tolerance joined no two different loans of the same lender held in different
   trusts.
6. PLEDGECHECK_LEFT: the borrower was enrolled in PledgeCheck and then left it. Being
   absent from the start is a coverage note; leaving mid-facility is a change worth
   asking about, because from then on nobody can see whether the collateral is
   pledged elsewhere.
7. The same vehicle, or the same loan contract (customer, origination month and amount), listed twice in ONE facility
   under different loan numbers: one vehicle, one contract, one pledge (red team round 3: "participations" split off
   real loans). Reported as DUPLICATE_ASSET, like a vehicle pledged in two facilities.
"""
from bt.common import bank
from bt.systems.base import Ctx, sig

OVERLAP = """
WITH t AS (
    SELECT DISTINCT borrower_id, asset_id, month, orig_month, round(orig_amount, 2) AS amt, term, round(rate, 4) AS rate,
           upper(make) AS make, upper(model) AS model, model_year, obligor_state, credit_score
    FROM tape WHERE month BETWEEN ? AND ? AND coalesce(make, '') <> '' AND facility_id LIKE '%A'
), p AS (
    SELECT DISTINCT issuer_borrower_id AS borrower_id, pool_id, month, orig_month, round(orig_amount, 2) AS amt, term,
           round(rate, 4) AS rate, upper(make) AS make, upper(model) AS model, model_year, obligor_state, credit_score
    FROM public_abs WHERE month BETWEEN ? AND ?
), m AS (
    SELECT t.borrower_id, t.asset_id, t.month, p.pool_id FROM t JOIN p
      ON t.borrower_id = p.borrower_id AND t.month = p.month AND t.orig_month = p.orig_month AND t.term = p.term
     AND t.rate = p.rate AND t.make = p.make AND t.model = p.model AND t.model_year = p.model_year
     AND t.obligor_state = p.obligor_state
     AND abs(t.amt - p.amt) <= ? * greatest(t.amt, p.amt) AND abs(t.credit_score - p.credit_score) <= ?
), runs AS (
    SELECT a.borrower_id, a.asset_id, a.pool_id, a.month FROM m a
    JOIN m b ON b.asset_id = a.asset_id AND b.pool_id = a.pool_id AND b.month = a.month + 1
)
SELECT borrower_id, any_value(pool_id) AS pool, count(DISTINCT asset_id) AS n, min(month) AS first_m,
       list(DISTINCT asset_id ORDER BY asset_id)[1:3] AS ex, list(DISTINCT asset_id) AS assets
FROM runs GROUP BY 1
"""
UNPAID = """
SELECT count(*) AS n FROM (SELECT UNNEST(?::VARCHAR[]) AS asset_id) m
WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.ref = m.asset_id AND p.month BETWEEN ? AND ?)
"""
OVERLAP_MIN, OVERLAP_WINDOW = 3, 3
# one loan reported twice can differ a little (servicing exports round amounts, refresh scores); measured on real
# ABS-EE pools, this tolerance joined no two different loans across trusts of the same lender
OVERLAP_AMOUNT_TOL, OVERLAP_SCORE_TOL = 0.02, 10
LEFT_MIN_MONTHS = 3  # enrolled at least this long before leaving

PLEDGECHECK = """
SELECT borrower_id,
       count(*) FILTER (WHERE uniqueness = 'FAIL') AS u_n, min(month) FILTER (WHERE uniqueness = 'FAIL') AS u_first,
       count(*) FILTER (WHERE completeness = 'FAIL') AS c_n, min(month) FILTER (WHERE completeness = 'FAIL') AS c_first
FROM pledgecheck GROUP BY 1
"""

TAPE_DUP = """
SELECT borrower_id, count(DISTINCT vin) AS n_dup, min(month) AS first_m, list(DISTINCT vin ORDER BY vin)[1:3] AS ex
FROM (SELECT borrower_id, month, vin FROM tape
      WHERE month BETWEEN ? AND ?
      GROUP BY 1, 2, 3 HAVING count(DISTINCT facility_id) > 1)
GROUP BY 1
"""

# the same vehicle or the same contract twice in one facility, in the same month, under different loan numbers
TAPE_DUP_IN = """
WITH k AS (
    SELECT borrower_id, facility_id, month, 'vin ' || vin AS item FROM tape
    WHERE month BETWEEN ? AND ? AND coalesce(vin, '') <> ''
    GROUP BY 1, 2, 3, 4 HAVING count(DISTINCT asset_id) > 1
    {contract}
)
SELECT borrower_id, count(DISTINCT item) AS n_dup, min(month) AS first_m, list(DISTINCT item ORDER BY item)[1:3] AS ex
FROM k GROUP BY 1 ORDER BY 1
"""
TAPE_DUP_CONTRACT = """
    UNION ALL
    SELECT borrower_id, facility_id, month,
           'contract ' || obligor_id || ' ' || CAST(orig_month AS VARCHAR) || ' ' || CAST(round(orig_amount, 2) AS VARCHAR)
    FROM tape WHERE month BETWEEN ? AND ? AND coalesce(obligor_id, '') <> '' AND orig_amount IS NOT NULL
    GROUP BY 1, 2, 3, 4 HAVING count(DISTINCT asset_id) > 1"""

INV_DUP = """
SELECT borrower_id, count(*) AS n_dup, min(first_m) AS first_m, list(invoice_number ORDER BY invoice_number)[1:3] AS ex
FROM (SELECT borrower_id, invoice_number, max(pledged_month) AS first_m FROM invoices
      GROUP BY 1, 2 HAVING count(DISTINCT facility_id) > 1 AND count(DISTINCT amount) = 1)
GROUP BY 1
"""


def run(ctx: Ctx):
    out = []
    invoice_borrowers = {r["borrower_id"] for r in ctx.rows("SELECT DISTINCT borrower_id FROM invoices")}
    for r in ctx.rows(PLEDGECHECK):
        if r["u_n"]:
            out.append(sig("S1", r["borrower_id"], "PLEDGECHECK_UNIQUENESS_FAIL", 0.9, 0.9,
                           [f"pledgecheck:{r['borrower_id']}:uniqueness:first_month={r['u_first']}"],
                           "Setpoint PledgeCheck: collateral appears in more than one active facility",
                           r["u_first"]))
        if r["c_n"]:
            typ = ("PLEDGECHECK_COMPLETENESS_FAIL_RECEIVABLES" if r["borrower_id"] in invoice_borrowers
                   else "PLEDGECHECK_COMPLETENESS_FAIL")
            out.append(sig("S1", r["borrower_id"], typ, 0.7, 0.85,
                           [f"pledgecheck:{r['borrower_id']}:completeness:first_month={r['c_first']}"],
                           "Setpoint PledgeCheck: actual collections don't match what the borrower reported",
                           r["c_first"]))
    enrolled = {r["borrower_id"] for r in ctx.rows("SELECT DISTINCT borrower_id FROM pledgecheck")}
    for r in ctx.rows("SELECT borrower_id FROM borrowers ORDER BY 1"):
        if r["borrower_id"] not in enrolled:
            out.append(sig("S1", r["borrower_id"], "PLEDGECHECK_ABSENT", 0.1, 1.0,
                           [f"pledgecheck:{r['borrower_id']}:not_enrolled"],
                           "Not enrolled in Setpoint PledgeCheck: whether this collateral is also pledged at other "
                           "lenders can't be verified", ctx.as_of))
    # leaving the registry mid-facility is a change, not a gap: from then on nobody sees a second pledge. Only while
    # the feed itself is current: a feed that stopped updating would make every borrower look as if it had left
    feed_current = (ctx.rows("SELECT max(month) AS m FROM pledgecheck")[0]["m"] or -1) >= ctx.as_of - 1
    for r in ctx.rows("""SELECT borrower_id, min(month) AS first_m, max(month) AS last_m, count(DISTINCT month) AS n
                         FROM pledgecheck WHERE enrolled GROUP BY 1 ORDER BY 1""") if feed_current else []:
        if r["n"] >= LEFT_MIN_MONTHS and r["last_m"] < ctx.as_of - 1:
            out.append(sig("S1", r["borrower_id"], "PLEDGECHECK_LEFT", 0.6, 0.6,
                           [f"pledgecheck:{r['borrower_id']}:enrolled_months={r['first_m']}-{r['last_m']}"],
                           f"Left Setpoint PledgeCheck after month {r['last_m'] + 1}, having been enrolled since month "
                           f"{r['first_m'] + 1}: from then on, whether this collateral is also pledged at other lenders "
                           f"can't be verified", r["last_m"] + 1))
    lo = max(0, ctx.as_of - 2)
    for r in ctx.rows(TAPE_DUP, [lo, ctx.as_of]):
        out.append(sig("S1", r["borrower_id"], "DUPLICATE_ASSET", 0.9, min(0.99, 0.6 + 0.05 * r["n_dup"]),
                       [f"tape:vin:{v}" for v in r["ex"]] + [f"count:{r['n_dup']}"],
                       f"{r['n_dup']} vehicles (matched by VIN) are pledged in two {bank.NAME} facilities at once",
                       r["first_m"]))
    tape_cols = {c[0] for c in ctx.con.execute("DESCRIBE tape").fetchall()}
    has_contract = {"orig_month", "orig_amount"} <= tape_cols  # older books lack loan attributes
    args = [lo, ctx.as_of] * (2 if has_contract else 1)
    for r in ctx.rows(TAPE_DUP_IN.format(contract=TAPE_DUP_CONTRACT if has_contract else ""), args):
        out.append(sig("S1", r["borrower_id"], "DUPLICATE_ASSET", 0.9, min(0.99, 0.6 + 0.05 * r["n_dup"]),
                       [f"tape:{x.replace(' ', ':', 1)}" for x in r["ex"]] + [f"count:{r['n_dup']}", "same_facility"],
                       f"{r['n_dup']} vehicles or loan contracts appear twice in the same facility under different loan "
                       f"numbers: one vehicle, one contract, one pledge", r["first_m"]))
    for r in ctx.rows(INV_DUP):
        out.append(sig("S1", r["borrower_id"], "DUPLICATE_ASSET", 0.9, min(0.99, 0.6 + 0.05 * r["n_dup"]),
                       [f"invoice:{n}" for n in r["ex"]] + [f"count:{r['n_dup']}"],
                       f"{r['n_dup']} identical invoices are pledged in two {bank.NAME} facilities at once",
                       r["first_m"]))
    if not ctx.shared.get("sec_off") and {"make", "credit_score"} <= tape_cols:  # older books lack loan attributes
        a = ctx.as_of
        for r in ctx.rows(OVERLAP, [max(0, a - OVERLAP_WINDOW), a, max(0, a - OVERLAP_WINDOW), a,
                                    OVERLAP_AMOUNT_TOL, OVERLAP_SCORE_TOL]):
            if r["n"] < OVERLAP_MIN:
                continue
            out.append(sig("S1", r["borrower_id"], "PUBLIC_POOL_OVERLAP", 0.85, 0.8,
                           [f"tape:asset:{x}" for x in r["ex"]] + [f"public_abs:{r['pool']}", f"count:{r['n']}"],
                           f"{r['n']} loans pledged to {bank.NAME} match loans that the borrower's own public "
                           f"securitization ({r['pool']}) reports to investors, on every field allowing for small "
                           f"reporting differences, two months running. The SEC data has no VIN: ask for the VINs and "
                           f"titles to settle it", r["first_m"]))
            # a loan can only pay one servicer account: if the matched loans stopped paying Wells Fargo, the trust collects them
            u = ctx.rows(UNPAID, [r["assets"], max(0, a - 2), a])[0]["n"]
            if u >= OVERLAP_MIN and u / r["n"] >= 0.5:
                out.append(sig("S1", r["borrower_id"], "POOL_LOANS_PAID_ELSEWHERE", 0.85, 0.9,
                               [f"payments:{r['borrower_id']}:months={max(0, a - 2)}-{a}:unpaid={u}/{r['n']}",
                                f"public_abs:{r['pool']}"],
                               f"{u} of the {r['n']} loans that also sit in the public trust paid nothing into the {bank.NAME} "
                               f"collection account in the last three months, though they are still on the tape: their "
                               f"payments are going somewhere else", r["first_m"]))
    return out
