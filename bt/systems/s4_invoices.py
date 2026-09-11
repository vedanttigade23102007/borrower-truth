"""S4 Invoice authenticity: is this receivable real?

Mechanism: First Brands submitted "fake invoices, fraudulently inflated invoices,
and double-pledged invoices"; "the dollar amounts on invoices were altered"
(VERIFY F1).

  ALTERED_INVOICE      same invoice number re-submitted with a different amount
  UNPAID_BY_DEBTOR     invoices well past due that the named customer never paid
  IMPLAUSIBLE_AMOUNT   far larger than anything that customer normally pays

A fine-tuned document model (design §6a) plugs in here to read the invoice
images; these rule checks run first so the model only reads what they flag.
"""
from bt.systems.base import Ctx, sig

ALTERED = """
SELECT borrower_id, count(*) AS n, min(first_m) AS first_m, list(invoice_number)[1:3] AS ex,
       max(ratio) AS max_ratio
FROM (SELECT borrower_id, invoice_number, max(pledged_month) AS first_m, max(amount) / min(amount) AS ratio
      FROM invoices GROUP BY 1, 2 HAVING count(DISTINCT amount) > 1)
GROUP BY 1
"""

UNPAID = """
WITH first AS (
    SELECT borrower_id, invoice_number, min(issue_month) AS im, min(due_days) AS due
    FROM invoices GROUP BY 1, 2
), due AS (
    SELECT * FROM first WHERE im + CAST(ceil(due / 30.0) AS INTEGER) + 1 <= ? AND im >= ?
), paid AS (SELECT DISTINCT borrower_id, ref FROM payments WHERE ref <> '')
SELECT d.borrower_id, count(*) AS n, count(*) FILTER (WHERE p.ref IS NULL) AS unpaid,
       list(d.invoice_number) FILTER (WHERE p.ref IS NULL)[1:3] AS ex
FROM due d LEFT JOIN paid p ON p.borrower_id = d.borrower_id AND p.ref = d.invoice_number
GROUP BY 1
"""

IMPLAUSIBLE = """
WITH paid AS (SELECT DISTINCT ref FROM payments WHERE ref <> ''),
     med AS (SELECT i.debtor_id, median(i.amount) AS md FROM invoices i JOIN paid ON paid.ref = i.invoice_number
             GROUP BY 1 HAVING count(*) >= 5)
SELECT i.borrower_id, count(*) AS n, min(i.pledged_month) AS first_m, list(i.invoice_id)[1:3] AS ex
FROM invoices i JOIN med USING (debtor_id)
WHERE i.amount > 5 * med.md AND i.pledged_month >= ?
GROUP BY 1
"""


def run(ctx: Ctx):
    out, a = [], ctx.as_of
    for r in ctx.rows(ALTERED):
        out.append(sig("S4", r["borrower_id"], "ALTERED_INVOICE", 0.9, 0.95,
                       [f"invoice:{x}" for x in r["ex"]] + [f"count:{r['n']}"],
                       f"{r['n']} invoice numbers were submitted more than once with different amounts "
                       f"(up to {r['max_ratio']:.1f}x the original)", r["first_m"]))
    for r in ctx.rows(UNPAID, [a, max(0, a - 9)]):
        if r["n"] >= 20 and r["unpaid"] / r["n"] > 0.06:
            rate = r["unpaid"] / r["n"]
            out.append(sig("S4", r["borrower_id"], "UNPAID_BY_DEBTOR", min(1.0, rate * 3), 0.8,
                           [f"invoice:{x}" for x in r["ex"]] + [f"unpaid:{r['unpaid']}/{r['n']}"],
                           f"{rate:.1%} of invoices past due were never paid by the named customer "
                           f"({r['unpaid']} of {r['n']})", a))
    for r in ctx.rows(IMPLAUSIBLE, [max(0, a - 9)]):
        if r["n"] >= 2:
            out.append(sig("S4", r["borrower_id"], "IMPLAUSIBLE_AMOUNT", 0.6, 0.7,
                           [f"invoice:{x}" for x in r["ex"]] + [f"count:{r['n']}"],
                           f"{r['n']} invoices are over 5x what the named customer normally pays", r["first_m"]))
    return out
