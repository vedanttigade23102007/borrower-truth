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

Who the borrower pays (added 2 Oct 2026, after the blind red team; each is a mechanism
a credit officer knows, never one attack):
  UNDISCLOSED_DEBT_SERVICE  a company first paid after the bank started lending, paid
                            month after month in amounts that only rise, like interest
                            on a growing loan, and not a lender the borrower disclosed
  NEW_PAYEES_DRAIN_CASH     companies first paid after the bank started lending now take a
                            large share of everything the borrower spends (cash leakage)
  MONTH_END_CURES           loan payments started bunching in the last days of the month,
                            just before the reporting date, compared with the borrower's
                            own earlier months (window dressing)
Real borrowers do add vendors, so none of these rests on "new" alone: the first two need a
recurring payee and a shape or a size, and say what the registry knows about the payee.
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
              OR (ref NOT IN (SELECT asset_id FROM tape WHERE asset_id IS NOT NULL)
                  AND ref NOT IN (SELECT invoice_number FROM invoices))),
     pairs AS (
        SELECT o.borrower_id, o.pn, o.payee_name, o.txn_id AS out_id, o.month, o.amount, i.txn_id AS in_id
        FROM o JOIN i ON i.borrower_id = o.borrower_id AND i.pn = o.pn
                     AND i.d BETWEEN o.d + 1 AND o.d + ? AND abs(i.amount - o.amount) <= ? * o.amount)
SELECT borrower_id, pn, min(payee_name) AS name, count(DISTINCT out_id) AS n, sum(DISTINCT amount) AS amt,
       min(month) AS first_m, list(DISTINCT out_id ORDER BY out_id)[1:2] AS outs, list(DISTINCT in_id ORDER BY in_id)[1:2] AS ins
FROM pairs GROUP BY 1, 2
"""
ROUND_TRIP_DAYS, ROUND_TRIP_TOLERANCE, ROUND_TRIP_MIN = 35, 0.02, 3

PAYEES = """
WITH b0 AS (SELECT borrower_id, min(month) AS b0 FROM outflows GROUP BY 1),
     pm AS (SELECT borrower_id, payee_id, any_value(payee_name) AS name, month, sum(amount) AS amt,
                   min(txn_id) AS txn FROM outflows GROUP BY 1, 2, 4)
SELECT pm.borrower_id, pm.payee_id, any_value(pm.name) AS name, norm(any_value(pm.name)) AS pn, min(pm.month) AS first_m,
       count(*) AS n_m, sum(pm.amt) AS amt, list(pm.amt ORDER BY pm.month) AS series,
       list(pm.txn ORDER BY pm.month)[1:3] AS ex
FROM pm JOIN b0 USING (borrower_id) GROUP BY 1, 2, b0.b0 HAVING min(pm.month) > b0.b0
ORDER BY 1, 2
"""
DEBT_SERVICE_MIN_MONTHS, DEBT_SERVICE_DIP, DEBT_SERVICE_RISE = 4, 0.9, 1.3  # never down >10%, up >=30% overall
DRAIN_MIN_MONTHS, DRAIN_SHARE = 3, 0.20  # recurring new payees taking >=20% of spend since they appeared
DRAIN_SHARE_SHELL = 0.05  # ... or >=5% when one of them looks like a shell (formed after lending began, no operations, unregistered)
MONTH_END_DAY, MONTH_END_MIN_PAYMENTS, MONTH_END_JUMP = 23, 200, 0.10  # last 6 days of a 28-day month


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

    round_trips = set()
    for r in ctx.rows(ROUND_TRIPS, [ROUND_TRIP_DAYS, ROUND_TRIP_TOLERANCE]):
        if r["n"] < ROUND_TRIP_MIN:
            continue
        round_trips.add((r["borrower_id"], r["pn"]))
        ent = ents.get(r["pn"])
        out.append(sig("S3", r["borrower_id"], "CIRCULAR_FLOW", 0.85, 0.85,
                       [f"outflow:{t}" for t in r["outs"]] + [f"payment:{t}" for t in r["ins"]]
                       + [f"counterparty:{r['name']}", f"round_trips:{r['n']}"],
                       f"{r['n']} times, money sent to '{r['name']}' came back from '{r['name']}' within "
                       f"{ROUND_TRIP_DAYS} days as a 'customer' payment of almost the same amount that settles no invoice "
                       f"(${r['amt']:,.0f} in total)", r["first_m"], [ent["entity_id"]] if ent else []))

    out += payees(ctx, round_trips) + month_end_cures(ctx)

    if rescued:
        con.execute("CREATE OR REPLACE TEMP TABLE rescued (borrower_id VARCHAR, pn VARCHAR)")
        con.executemany("INSERT INTO rescued VALUES (?, ?)", rescued)
        con.execute("UPDATE pay_class SET known = true FROM rescued r "
                    "WHERE pay_class.borrower_id = r.borrower_id AND pay_class.pn = r.pn")
    ctx.shared["known_q"] = {(r["borrower_id"], r["q"]): r["amt"] for r in ctx.rows(
        "SELECT borrower_id, month // 3 AS q, sum(amount) AS amt FROM pay_class WHERE known GROUP BY 1, 2")}
    return out



def _flags(e) -> list[str]:
    """What the company register says that a credit officer would want to know about a payee."""
    if e is None:
        return ["not in the company register"]
    out = []
    if e["formed_month"] is not None and e["formed_month"] >= 0:
        out.append(f"formed in month {e['formed_month'] + 1}, after the bank started lending")
    if not e["has_operations"]:
        out.append("shows no business operations")
    return out


def payees(ctx: Ctx, round_trips: set = frozenset()) -> list:
    """Who the borrower pays, from its operating account: undisclosed debt service, and cash leakage. Leakage is money
    that leaves and doesn't come back, paid to someone other than a lender: money that returns as a 'customer' payment
    is a round trip (CIRCULAR_FLOW), and payments to a lender are debt service, not leakage."""
    if ctx.as_of < DRAIN_MIN_MONTHS:
        return []
    ents = {r["entity_id"]: r for r in ctx.rows("SELECT entity_id, name, kind, formed_month, has_operations FROM entities")}
    lenders = {(r["borrower_id"], r["counterparty_entity_id"]) for r in ctx.rows(
        "SELECT borrower_id, counterparty_entity_id FROM disclosures WHERE kind = 'debt'")}
    related = {(r["borrower_id"], r["counterparty_entity_id"]) for r in ctx.rows(
        "SELECT borrower_id, counterparty_entity_id FROM disclosures WHERE kind = 'related_party'")}
    monthly = {}
    for r in ctx.rows("SELECT borrower_id, month, sum(amount) AS amt FROM outflows GROUP BY 1, 2"):
        monthly.setdefault(r["borrower_id"], {})[r["month"]] = r["amt"]
    out, new = [], {}
    for r in ctx.rows(PAYEES):
        b, pid = r["borrower_id"], r["payee_id"]
        if (b, pid) in lenders or (ents.get(pid) or {}).get("kind") == "bank":
            continue
        e, series = ents.get(pid), r["series"]
        flags = _flags(e)
        if r["n_m"] >= DRAIN_MIN_MONTHS and (b, r["pn"]) not in round_trips and (e or {}).get("kind") != "lender":
            new.setdefault(b, []).append((r, flags))
        rising = all(x >= DEBT_SERVICE_DIP * y for y, x in zip(series, series[1:])) and series[-1] >= DEBT_SERVICE_RISE * series[0]
        if e is not None and r["n_m"] >= DEBT_SERVICE_MIN_MONTHS and rising:
            out.append(sig("S3", b, "UNDISCLOSED_DEBT_SERVICE", 0.75, 0.75 if flags else 0.6,
                           [f"outflow:{t}" for t in r["ex"]] + [f"payee:{r['name']}", f"months_paid:{r['n_m']}"],
                           f"'{r['name']}' has been paid in {r['n_m']} months since month {r['first_m'] + 1}, in amounts "
                           f"that only rise (${series[0]:,.0f} to ${series[-1]:,.0f}), the shape of interest on a growing "
                           f"loan, and it isn't a lender the borrower disclosed" + (f" ({'; '.join(flags)})" if flags else ""),
                           r["first_m"], [pid]))
    for b, rows in new.items():
        start = min(r["first_m"] for r, _ in rows)
        spend = sum(v for m, v in monthly.get(b, {}).items() if m >= start)
        amt = sum(r["amt"] for r, _ in rows)
        flagged = [f for _, fl in rows for f in fl]
        if not spend or amt / spend < (DRAIN_SHARE_SHELL if flagged else DRAIN_SHARE):
            continue
        names = ", ".join(f"'{r['name']}'" + (" (disclosed as a related party)" if (b, r["payee_id"]) in related else "")
                          for r, _ in sorted(rows, key=lambda x: -x[0]["amt"])[:3])
        out.append(sig("S3", b, "NEW_PAYEES_DRAIN_CASH", 0.7, 0.75 if flagged else 0.6,
                       [f"outflow:{t}" for r, _ in rows for t in r["ex"][:1]] + [f"share:{amt / spend:.2f}"],
                       f"{len(rows)} payee(s) first paid after the bank started lending now take {amt / spend:.0%} of "
                       f"everything the borrower has spent since month {start + 1} (${amt:,.0f}): {names}"
                       + (f"; the register shows: {'; '.join(sorted(set(flagged)))}" if flagged else ""),
                       start, [r["payee_id"] for r, _ in rows]))
    return out


def month_end_cures(ctx: Ctx) -> list:
    """Loan payments that started bunching just before the reporting date, against the borrower's own early months."""
    a = ctx.as_of
    if a < 11:
        return []
    for b, s in ctx.loan_scope().items():  # an empty starting list is "not run" for that borrower, never "ok"
        if s["rows_any"] and s["pays"] and not s["pays_loans"]:
            ctx.not_run("S3", b, "the month-end payment check",
                        f"none of its {s['pays']:,} payments names one of its loan numbers")
    out = []
    for r in ctx.rows(f"""
        SELECT borrower_id,
               count(*) FILTER (WHERE month BETWEEN 1 AND 6) AS n0,
               avg(CASE WHEN day >= {MONTH_END_DAY} THEN 1 ELSE 0 END) FILTER (WHERE month BETWEEN 1 AND 6) AS s0,
               count(*) FILTER (WHERE month BETWEEN {a - 5} AND {a}) AS n1,
               avg(CASE WHEN day >= {MONTH_END_DAY} THEN 1 ELSE 0 END) FILTER (WHERE month BETWEEN {a - 5} AND {a}) AS s1
        FROM payments WHERE ref IN (SELECT asset_id FROM tape) AND month <= {a} GROUP BY 1 ORDER BY 1"""):
        if min(r["n0"], r["n1"]) < MONTH_END_MIN_PAYMENTS or r["s1"] - r["s0"] < MONTH_END_JUMP:
            continue
        out.append(sig("S3", r["borrower_id"], "MONTH_END_CURES", 0.7, 0.6,
                       [f"payments:{r['borrower_id']}:month_end_share={r['s0']:.2f}->{r['s1']:.2f}"],
                       f"{r['s1']:.0%} of loan payments in the last six months arrived in the last days of the month, "
                       f"against {r['s0']:.0%} in the first months: payments started bunching just before the "
                       f"reporting date", a - 5))
    return out

