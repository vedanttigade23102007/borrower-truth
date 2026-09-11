"""S1 Collateral integrity: is this collateral unique and clean?

Mechanism: the same collateral pledged to several lenders (Tricolor T1/T2,
First Brands F1).

1. Ingests the (simulated) Setpoint PledgeCheck result, which WF backs (S1/S3 in
   VERIFY). We do not rebuild it; its FAILs become signals.
2. Checks uniqueness INSIDE Wells Fargo across all WF facilities. Matching is by
   VIN / obligor fingerprint, not only asset ID, because a second pledge can
   relabel the ID.
3. The same invoice (same number, same amount) pledged to two WF facilities.
"""
from bt.systems.base import Ctx, sig

PLEDGECHECK = """
SELECT borrower_id,
       count(*) FILTER (WHERE uniqueness = 'FAIL') AS u_n, min(month) FILTER (WHERE uniqueness = 'FAIL') AS u_first,
       count(*) FILTER (WHERE completeness = 'FAIL') AS c_n, min(month) FILTER (WHERE completeness = 'FAIL') AS c_first
FROM pledgecheck GROUP BY 1
"""

TAPE_DUP = """
SELECT borrower_id, count(DISTINCT vin) AS n_dup, min(month) AS first_m, list(DISTINCT vin)[1:3] AS ex
FROM (SELECT borrower_id, month, vin FROM tape
      WHERE month BETWEEN ? AND ?
      GROUP BY 1, 2, 3 HAVING count(DISTINCT facility_id) > 1)
GROUP BY 1
"""

INV_DUP = """
SELECT borrower_id, count(*) AS n_dup, min(first_m) AS first_m, list(invoice_number)[1:3] AS ex
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
    lo = max(0, ctx.as_of - 2)
    for r in ctx.rows(TAPE_DUP, [lo, ctx.as_of]):
        out.append(sig("S1", r["borrower_id"], "DUPLICATE_ASSET", 0.9, min(0.99, 0.6 + 0.05 * r["n_dup"]),
                       [f"tape:vin:{v}" for v in r["ex"]] + [f"count:{r['n_dup']}"],
                       f"{r['n_dup']} vehicles (matched by VIN) are pledged in two Wells Fargo facilities at once",
                       r["first_m"]))
    for r in ctx.rows(INV_DUP):
        out.append(sig("S1", r["borrower_id"], "DUPLICATE_ASSET", 0.9, min(0.99, 0.6 + 0.05 * r["n_dup"]),
                       [f"invoice:{n}" for n in r["ex"]] + [f"count:{r['n_dup']}"],
                       f"{r['n_dup']} identical invoices are pledged in two Wells Fargo facilities at once",
                       r["first_m"]))
    return out
