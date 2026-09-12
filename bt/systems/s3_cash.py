"""S3 Cash provenance: who actually paid?

Mechanism: First Brands routed lender money so it "appeared to be ordinary
customer receipts" (VERIFY F4). A collections-vs-reported check passes this,
because the cash really arrives. The question is *who sent it*.

Every inflow to the collection account is matched to a known payer (a loan
obligor on the tape, or an invoice debtor). Unknown payers are resolved against
the company registry and S6's relationship graph. Publishes verified collections
per quarter for S7.

CIRCULAR_FLOW: money that leaves the borrower's operating account for a company
and comes back from the same company, days later, as a "customer" payment of
almost the same amount that settles no invoice or loan, again and again. The
middleman can look completely unrelated in the registry; the round trip itself
is the evidence. A customer that is also a supplier doesn't trigger it: its
payments settle invoices.
"""
from rapidfuzz import fuzz, process

from bt.systems.base import Ctx, sig

CLASSIFY = """
CREATE OR REPLACE TEMP TABLE pay_class AS
WITH ko AS (SELECT DISTINCT borrower_id, obligor_id FROM tape),
     kd AS (SELECT DISTINCT borrower_id, norm(debtor_name) AS dn FROM invoices)
SELECT p.borrower_id, p.txn_id, p.month, p.amount, p.payer_id, p.payer_name, norm(p.payer_name) AS pn,
       (ko.obligor_id IS NOT NULL OR kd.dn IS NOT NULL) AS known
FROM payments p
LEFT JOIN ko ON ko.borrower_id = p.borrower_id AND ko.obligor_id = p.payer_id
LEFT JOIN kd ON kd.borrower_id = p.borrower_id AND kd.dn = norm(p.payer_name)
"""

UNKNOWN = """
SELECT borrower_id, pn, min(payer_name) AS name, sum(amount) AS amt, count(*) AS n,
       min(month) AS first_m, list(txn_id ORDER BY txn_id)[1:3] AS ex
FROM pay_class WHERE NOT known GROUP BY 1, 2
"""


ROUND_TRIPS = """
WITH o AS (SELECT borrower_id, txn_id, month, month * 30 + day AS d, amount, norm(payee_name) AS pn, payee_name
           FROM outflows),
     -- only payments that settle nothing: a real customer's payment is applied to an invoice or a loan
     i AS (SELECT borrower_id, txn_id, month * 30 + day AS d, amount, norm(payer_name) AS pn FROM payments
           WHERE coalesce(ref, '') = ''
              OR (ref NOT LIKE 'A-%' AND ref NOT IN (SELECT invoice_number FROM invoices))),
     pairs AS (
        SELECT o.borrower_id, o.pn, o.payee_name, o.txn_id AS out_id, o.month, o.amount, i.txn_id AS in_id
        FROM o JOIN i ON i.borrower_id = o.borrower_id AND i.pn = o.pn
                     AND i.d BETWEEN o.d + 1 AND o.d + ? AND abs(i.amount - o.amount) <= ? * o.amount)
SELECT borrower_id, pn, min(payee_name) AS name, count(DISTINCT out_id) AS n, sum(DISTINCT amount) AS amt,
       min(month) AS first_m, list(DISTINCT out_id ORDER BY out_id)[1:2] AS outs, list(DISTINCT in_id ORDER BY in_id)[1:2] AS ins
FROM pairs GROUP BY 1, 2
"""
ROUND_TRIP_DAYS, ROUND_TRIP_TOLERANCE, ROUND_TRIP_MIN = 35, 0.02, 3


def run(ctx: Ctx):
    con = ctx.con
    con.execute(CLASSIFY)
    totals = {r["borrower_id"]: r["t"] for r in ctx.rows("SELECT borrower_id, sum(amount) AS t FROM pay_class GROUP BY 1")}
    ents = {r["pn"]: r for r in ctx.rows("SELECT norm(name) AS pn, entity_id, kind, name FROM entities")}
    related = {(r["borrower_id"], r["entity_id"]): r for r in ctx.rows("SELECT * FROM related")}
    debtors = {}
    for r in ctx.rows("SELECT DISTINCT borrower_id, norm(debtor_name) AS dn FROM invoices"):
        debtors.setdefault(r["borrower_id"], []).append(r["dn"])

    out, rescued = [], []
    for r in ctx.rows(UNKNOWN):
        b = r["borrower_id"]
        # a near-miss on a known customer's name is a typo, not a stranger
        if b in debtors and process.extractOne(r["pn"], debtors[b], scorer=fuzz.ratio, score_cutoff=92):
            rescued.append((b, r["pn"]))
            continue
        share = r["amt"] / max(totals.get(b, 1.0), 1.0)
        ent = ents.get(r["pn"])
        ev = [f"payment:{t}" for t in r["ex"]] + [f"payer:{r['name']}", f"total:${r['amt']:,.0f} in {r['n']} payments"]
        if ent and (b, ent["entity_id"]) in related:
            rel = related[(b, ent["entity_id"])]
            if rel["disclosed"]:
                ctx.explain(b, f"payments from {rel['name']} are from a disclosed related party")
                continue
            out.append(sig("S3", b, "RELATED_PARTY_INFLOW", 0.8, 0.85, ev,
                           f"${r['amt']:,.0f} ({share:.1%} of inflows) arrived as 'customer' cash from "
                           f"'{r['name']}', an undisclosed company linked to the borrower", r["first_m"],
                           [ent["entity_id"]]))
        elif ent and ent["kind"] == "lender":
            out.append(sig("S3", b, "LENDER_FUNDS_AS_RECEIPTS", 0.85, 0.9, ev,
                           f"${r['amt']:,.0f} ({share:.1%} of inflows) came from '{r['name']}', a finance company, "
                           f"not a customer", r["first_m"], [ent["entity_id"]]))
        elif share >= 0.01:
            out.append(sig("S3", b, "NON_OBLIGOR_PAYER", 0.5, 0.6, ev,
                           f"${r['amt']:,.0f} ({share:.1%} of inflows) came from '{r['name']}', who is not a known "
                           f"customer or obligor", r["first_m"], [ent["entity_id"]] if ent else []))

    for r in ctx.rows(ROUND_TRIPS, [ROUND_TRIP_DAYS, ROUND_TRIP_TOLERANCE]):
        if r["n"] < ROUND_TRIP_MIN:
            continue
        ent = ents.get(r["pn"])
        out.append(sig("S3", r["borrower_id"], "CIRCULAR_FLOW", 0.85, 0.85,
                       [f"outflow:{t}" for t in r["outs"]] + [f"payment:{t}" for t in r["ins"]]
                       + [f"counterparty:{r['name']}", f"round_trips:{r['n']}"],
                       f"{r['n']} times, money sent to '{r['name']}' came back from '{r['name']}' within "
                       f"{ROUND_TRIP_DAYS} days as a 'customer' payment of almost the same amount that settles no invoice "
                       f"(${r['amt']:,.0f} in total)", r["first_m"], [ent["entity_id"]] if ent else []))

    if rescued:
        con.execute("CREATE OR REPLACE TEMP TABLE rescued (borrower_id VARCHAR, pn VARCHAR)")
        con.executemany("INSERT INTO rescued VALUES (?, ?)", rescued)
        con.execute("UPDATE pay_class SET known = true FROM rescued r "
                    "WHERE pay_class.borrower_id = r.borrower_id AND pay_class.pn = r.pn")
    ctx.shared["known_q"] = {(r["borrower_id"], r["q"]): r["amt"] for r in ctx.rows(
        "SELECT borrower_id, month // 3 AS q, sum(amount) AS amt FROM pay_class WHERE known GROUP BY 1, 2")}
    return out
