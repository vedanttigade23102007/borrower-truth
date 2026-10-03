"""S4 Invoice authenticity: is this receivable real?

Mechanism: First Brands submitted "fake invoices, fraudulently inflated invoices,
and double-pledged invoices"; "the dollar amounts on invoices were altered"
(VERIFY F1).

  ALTERED_INVOICE      same invoice number re-submitted with a different amount
  UNPAID_BY_DEBTOR     invoices well past due that the named customer never paid
  IMPLAUSIBLE_AMOUNT   far larger than anything that customer normally pays
  DILUTION_JUMP        customers now pay well short of the invoice amounts, against the
                       borrower's own first quarter on the facility (inflated invoices: the
                       customer pays what it really owes). Dilution is a standard field-exam
                       number; the comparison is with the borrower itself, never one fixed line.
                       Both the last six months together and any single month's invoices
  CUSTOMER_NEVER_PAID  a customer with several invoices past due has never paid the borrower
                       anything: no payment for any of its invoices, and none from it at all,
                       reached the collection account (the bank's own cash records). A customer
                       paying the borrower directly looks the same, so the case asks where it
                       pays, and it needs another source to reach likely fraud

Evidence stays in view while the collateral is still pledged (red team round 3, Vedant 3 Oct 2026): an invoice that
is still unpaid is checked however old it is, not only within the last few months.

A fine-tuned document model (design §6a) plugs in here to read the invoice
images; these rule checks run first so the model only reads what they flag.
"""
import statistics

from bt.systems.base import Ctx, sig

ALTERED = """
SELECT borrower_id, count(*) AS n, min(first_m) AS first_m, list(invoice_number ORDER BY invoice_number)[1:3] AS ex,
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
       list(d.invoice_number ORDER BY d.invoice_number) FILTER (WHERE p.ref IS NULL)[1:3] AS ex
FROM due d LEFT JOIN paid p ON p.borrower_id = d.borrower_id AND p.ref = d.invoice_number
GROUP BY 1
"""

IMPLAUSIBLE = """
WITH paid AS (SELECT DISTINCT ref FROM payments WHERE ref <> ''),
     got AS (SELECT borrower_id, ref, sum(amount) AS p FROM payments WHERE ref <> '' GROUP BY 1, 2),
     med AS (SELECT i.debtor_id, median(i.amount) AS md FROM invoices i JOIN paid ON paid.ref = i.invoice_number
             GROUP BY 1 HAVING count(*) >= 5)
SELECT i.borrower_id, count(*) AS n, min(i.pledged_month) AS first_m, list(i.invoice_id ORDER BY i.invoice_id)[1:3] AS ex
FROM invoices i JOIN med USING (debtor_id)
LEFT JOIN got ON got.borrower_id = i.borrower_id AND got.ref = i.invoice_number
WHERE i.amount > 5 * med.md AND (i.pledged_month >= ? OR coalesce(got.p, 0) < 0.99 * i.amount)
GROUP BY 1 ORDER BY 1
"""  # recent ones, plus any still not paid in full: a fake invoice stays in view while it is still owed

# a customer that has never paid anything: several of its invoices past due, none paid, and no payment from it at all
NEVER_PAID = """
WITH inv AS (SELECT borrower_id, debtor_id, any_value(debtor_name) AS name, invoice_number, min(issue_month) AS im,
                    min(due_days) AS due, max(amount) AS face
             FROM invoices GROUP BY 1, 2, 4),
     due AS (SELECT * FROM inv WHERE im + CAST(ceil(due / 30.0) AS INTEGER) + 1 <= ?),
     by_ref AS (SELECT DISTINCT borrower_id, ref FROM payments WHERE ref <> ''),
     by_payer AS (SELECT DISTINCT borrower_id, payer_id FROM payments)
SELECT d.borrower_id, d.debtor_id, any_value(d.name) AS name, count(*) AS n, sum(d.face) AS face, min(d.im) AS first_m,
       list(d.invoice_number ORDER BY d.invoice_number)[1:3] AS ex
FROM due d
WHERE NOT EXISTS (SELECT 1 FROM by_ref r WHERE r.borrower_id = d.borrower_id AND r.ref = d.invoice_number)
  AND NOT EXISTS (SELECT 1 FROM by_payer p WHERE p.borrower_id = d.borrower_id AND p.payer_id = d.debtor_id)
  AND NOT EXISTS (SELECT 1 FROM by_ref r JOIN inv i2 ON i2.borrower_id = r.borrower_id AND i2.invoice_number = r.ref
                  WHERE i2.borrower_id = d.borrower_id AND i2.debtor_id = d.debtor_id)
GROUP BY 1, 2 HAVING count(*) >= ?
ORDER BY 1, 2
"""
NEVER_PAID_MIN = 3

# per borrower: invoices past due, payments, and how many payments name one of its invoice numbers. If none does, the
# checks that match payments to invoices would see every invoice as unpaid: "not run" for that borrower, not a flood
INVOICE_SCOPE = """
WITH inv AS (SELECT DISTINCT borrower_id, invoice_number FROM invoices),
due AS (SELECT borrower_id, count(*) AS n
        FROM (SELECT borrower_id, invoice_number, min(issue_month) AS im, min(due_days) AS d FROM invoices GROUP BY 1, 2)
        WHERE im + CAST(ceil(d / 30.0) AS INTEGER) + 1 <= ? GROUP BY 1),
p AS (SELECT p.borrower_id, count(*) AS pays, count(inv.invoice_number) AS pays_inv
      FROM payments p LEFT JOIN inv ON inv.borrower_id = p.borrower_id AND inv.invoice_number = p.ref GROUP BY 1)
SELECT due.borrower_id, due.n AS past_due, coalesce(p.pays, 0) AS pays, coalesce(p.pays_inv, 0) AS pays_inv
FROM due LEFT JOIN p USING (borrower_id) ORDER BY 1
"""
MATCHING = "the checks that match payments to invoices"

# dilution: the share of a paid invoice's face value that never arrived as cash, by issue month. Only invoices old
# enough to have been paid, and only paid ones: never-paid invoices are UNPAID_BY_DEBTOR's job
DILUTION = """
WITH inv AS (
    SELECT borrower_id, invoice_number, min(issue_month) AS im, min(due_days) AS due, max(amount) AS face
    FROM invoices GROUP BY 1, 2
), paid AS (SELECT borrower_id, ref, sum(amount) AS paid FROM payments WHERE ref <> '' GROUP BY 1, 2)
SELECT i.borrower_id, i.im, sum(i.face * greatest(0, least(1, 1 - p.paid / i.face))) / sum(i.face) AS dil,
       count(*) AS n
FROM inv i JOIN paid p ON p.borrower_id = i.borrower_id AND p.ref = i.invoice_number
WHERE i.face > 0 AND i.im + CAST(ceil(i.due / 30.0) AS INTEGER) + 1 <= ?
GROUP BY 1, 2 ORDER BY 1, 2
"""
SHORT_PAID = """
WITH inv AS (SELECT borrower_id, invoice_number, min(issue_month) AS im, max(amount) AS face FROM invoices GROUP BY 1, 2),
     paid AS (SELECT borrower_id, ref, sum(amount) AS paid FROM payments WHERE ref <> '' GROUP BY 1, 2)
SELECT i.invoice_number FROM inv i JOIN paid p ON p.borrower_id = i.borrower_id AND p.ref = i.invoice_number
WHERE i.borrower_id = ? AND i.im BETWEEN ? AND ? AND p.paid < i.face
ORDER BY i.face - p.paid DESC, 1 LIMIT 3
"""
# the borrower's own first quarter is the yardstick: the closest to the field exam that approved the facility
DILUTION_BASE_MONTHS, DILUTION_RECENT_MONTHS = 3, 6
DILUTION_MIN_JUMP = 0.01  # below a point of invoice value the jump doesn't change what the receivables are worth
DILUTION_SPREAD_K = 3  # and it must stand well clear of how much the borrower's own early months moved
DILUTION_MIN_INVOICES = 30
# one month's invoices on their own: a single burst of inflated invoices ages out of a six-month average. A month is
# noisier than six, so the line is higher: honest dev months moved at most 3.5 points (tuned on dev books only)
DILUTION_COHORT_MIN_JUMP, DILUTION_COHORT_MIN_INVOICES = 0.05, 20


def dilution(ctx: Ctx) -> list:
    by_b: dict[str, list] = {}
    for r in ctx.rows(DILUTION, [ctx.as_of]):
        by_b.setdefault(r["borrower_id"], []).append(r)
    out = []
    for b, months in by_b.items():
        if ctx.skipped("S4", b, MATCHING):
            continue
        base, recent = months[:DILUTION_BASE_MONTHS], months[-DILUTION_RECENT_MONTHS:]
        if len(months) < DILUTION_BASE_MONTHS + DILUTION_RECENT_MONTHS:
            continue  # not enough history to have both an early yardstick and a separate recent window
        nb, nr = sum(m["n"] for m in base), sum(m["n"] for m in recent)
        if nb < DILUTION_MIN_INVOICES or nr < DILUTION_MIN_INVOICES:
            continue
        b_dil = sum(m["dil"] * m["n"] for m in base) / nb
        r_dil = sum(m["dil"] * m["n"] for m in recent) / nr
        spread = statistics.pstdev([m["dil"] for m in base])
        jump = r_dil - b_dil
        r0, r1, b0, b1 = recent[0]["im"], recent[-1]["im"], base[0]["im"], base[-1]["im"]
        if jump < max(DILUTION_MIN_JUMP, DILUTION_SPREAD_K * spread):
            # no recent drift: is any single later month's batch far off, however long ago it was issued?
            worst = max((m for m in months[DILUTION_BASE_MONTHS:] if m["n"] >= DILUTION_COHORT_MIN_INVOICES),
                        key=lambda m: m["dil"], default=None)
            if worst is None or worst["dil"] - b_dil < max(DILUTION_COHORT_MIN_JUMP, DILUTION_SPREAD_K * spread):
                continue
            r0 = r1 = worst["im"]
            r_dil, nr = worst["dil"], worst["n"]
        ex = [x["invoice_number"] for x in ctx.rows(SHORT_PAID, [b, r0, r1])]
        out.append(sig("S4", b, "DILUTION_JUMP", 0.6, 0.75,
                       [f"invoice:{x}" for x in ex]
                       + [f"invoices:{b}:dilution:months={r0}-{r1}:{r_dil:.4f}",
                          f"invoices:{b}:dilution:baseline_months={b0}-{b1}:{b_dil:.4f}"],
                       f"Customers paid {r_dil:.1%} less than the invoice amounts on invoices issued in "
                       f"{f'month {r0 + 1}' if r0 == r1 else f'months {r0 + 1}-{r1 + 1}'}, against {b_dil:.1%} in the borrower's own first three months ({nr} paid "
                       f"invoices). Invoices that collect short are worth less than the borrowing base says: confirm a "
                       f"sample of them with the customers", r0))
    return out


DOC_READS = "doc_reads.parquet"


def document_check(ctx: Ctx) -> list:
    """Document vs data: the fine-tuned reader's total (after its second look) vs the
    borrower's invoice record. An optional module, off by default (BT_DOCUMENT_MODEL=on turns
    it on): the rules work without it, and it helps only a little (proof/model/MODEL.md).
    Reads come from the document batch job (model/kaggle_score); if the module is on and they
    are missing, S4 runs on rules alone and every case says so (fallback, design §12)."""
    import os
    if not ctx.shared.get("document_model"):
        return []
    path = os.path.join(ctx.data_dir, DOC_READS)
    if not os.path.exists(path):
        ctx.shared["documents"] = "unavailable (module on, but no document reads were delivered)"
        return []
    rows = ctx.rows(f"""
        SELECT d.borrower_id, count(*) AS n, count(*) FILTER (WHERE d.doc_mismatch) AS bad,
               count(*) FILTER (WHERE d.doc_mismatch AND d.reads_agree) AS bad_agree,
               list(d.invoice_id ORDER BY d.invoice_id) FILTER (WHERE d.doc_mismatch)[1:3] AS ex, min(i.pledged_month) AS first_m
        FROM read_parquet('{path}') d JOIN invoices i USING (invoice_id)
        GROUP BY 1""")
    ctx.shared["documents"] = f"ok ({sum(r['n'] for r in rows)} documents read)"
    out = []
    for r in rows:
        if r["bad"] == 0:
            continue
        # two independent reads agreeing on a different total is stronger than one read
        conf = 0.85 if r["bad_agree"] == r["bad"] else 0.6
        out.append(sig("S4", r["borrower_id"], "DOC_DATA_MISMATCH", 0.8, conf,
                       [f"document:{x}" for x in r["ex"]] + [f"mismatched:{r['bad']}/{r['n']}"],
                       f"{r['bad']} of {r['n']} invoice documents show a different total from the borrower's data "
                       f"(read twice by the document model)", r["first_m"] or ctx.as_of))
    return out


def run(ctx: Ctx):
    for r in ctx.rows(INVOICE_SCOPE, [ctx.as_of]):  # an empty starting list is "not run" for that borrower, never "ok"
        if r["past_due"] and r["pays"] and not r["pays_inv"]:
            ctx.not_run("S4", r["borrower_id"], MATCHING,
                        f"none of its {r['pays']:,} payments names one of its invoice numbers")
    out, a = document_check(ctx) + dilution(ctx), ctx.as_of
    for r in ctx.rows(ALTERED):
        out.append(sig("S4", r["borrower_id"], "ALTERED_INVOICE", 0.9, 0.95,
                       [f"invoice:{x}" for x in r["ex"]] + [f"count:{r['n']}"],
                       f"{r['n']} invoice numbers were submitted more than once with different amounts "
                       f"(up to {r['max_ratio']:.1f}x the original)", r["first_m"]))
    for r in ctx.rows(UNPAID, [a, max(0, a - 9)]):
        if ctx.skipped("S4", r["borrower_id"], MATCHING):
            continue
        if r["n"] >= 20 and r["unpaid"] / r["n"] > 0.06:
            rate = r["unpaid"] / r["n"]
            out.append(sig("S4", r["borrower_id"], "UNPAID_BY_DEBTOR", min(1.0, rate * 3), 0.8,
                           [f"invoice:{x}" for x in r["ex"]] + [f"unpaid:{r['unpaid']}/{r['n']}"],
                           f"{rate:.1%} of invoices past due were never paid by the named customer "
                           f"({r['unpaid']} of {r['n']})", a))
    for r in ctx.rows(IMPLAUSIBLE, [max(0, a - 9)]):
        if r["n"] >= 2 and not ctx.skipped("S4", r["borrower_id"], MATCHING):
            out.append(sig("S4", r["borrower_id"], "IMPLAUSIBLE_AMOUNT", 0.6, 0.7,
                           [f"invoice:{x}" for x in r["ex"]] + [f"count:{r['n']}"],
                           f"{r['n']} invoices are over 5x what the named customer normally pays", r["first_m"]))
    for r in ctx.rows(NEVER_PAID, [a, NEVER_PAID_MIN]):
        if ctx.skipped("S4", r["borrower_id"], MATCHING):
            continue
        out.append(sig("S4", r["borrower_id"], "CUSTOMER_NEVER_PAID", 0.8, 0.9,
                       [f"invoice:{x}" for x in r["ex"]] + [f"debtor:{r['debtor_id']}", f"count:{r['n']}"],
                       f"'{r['name']}' has {r['n']} invoices past due (${r['face']:,.0f}) and no payment from it, or for "
                       f"any of its invoices, has reached the collection account. Either the invoices aren't real, or the "
                       f"customer pays somewhere else (to the borrower directly or another account), which breaks the "
                       f"cash-dominion terms: ask where it pays, and confirm the invoices with the customer",
                       r["first_m"], [r["debtor_id"]]))
    return out
