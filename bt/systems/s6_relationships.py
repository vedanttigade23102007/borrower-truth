"""S6 Relationship mapper: who is really connected to this borrower?

Mechanism (DOJ First Brands release, VERIFY F3): related "James Entities" that
"had no independent business operations" carried hidden debt.

Finds entities sharing the borrower's officer or address, checks whether each was
disclosed, and scores how shell-like it is. Publishes the `related` table that
S1, S3 and S5 use to widen their search.
"""
from bt.systems.base import Ctx, sig

RELATED_SQL = """
CREATE OR REPLACE TABLE related AS
WITH b AS (
    SELECT b.borrower_id, b.entity_id, e.officer_person_id AS owner, e.address
    FROM borrowers b JOIN entities e USING (entity_id)
), rel AS (
    SELECT b.borrower_id, e.entity_id, e.name, e.kind, e.has_operations, e.formed_month,
           e.officer_person_id = b.owner AS same_owner, e.address = b.address AS same_address
    FROM b JOIN entities e
      ON e.entity_id <> b.entity_id AND (e.officer_person_id = b.owner OR e.address = b.address)
    WHERE e.kind NOT IN ('bank', 'lender', 'debtor', 'borrower')
)
SELECT rel.*,
       d.counterparty_entity_id IS NOT NULL AS disclosed,
       g.entity_id IS NOT NULL AS in_gleif
FROM rel
LEFT JOIN (SELECT DISTINCT borrower_id, counterparty_entity_id FROM disclosures WHERE kind = 'related_party') d
       ON d.borrower_id = rel.borrower_id AND d.counterparty_entity_id = rel.entity_id
LEFT JOIN (SELECT DISTINCT entity_id FROM gleif) g ON g.entity_id = rel.entity_id
"""


def run(ctx: Ctx):
    ctx.con.execute(RELATED_SQL)
    out = []
    for r in ctx.rows("SELECT * FROM related ORDER BY borrower_id, entity_id"):
        if r["disclosed"]:  # a disclosed affiliate is normal; nothing to explain away
            continue
        indicators = []
        if not r["has_operations"]:
            indicators.append("no operations")
        if r["same_address"]:
            indicators.append("same address as borrower")
        if ctx.as_of - r["formed_month"] <= 12:
            indicators.append(f"formed {ctx.as_of - r['formed_month']} months ago")
        if not r["in_gleif"]:
            indicators.append("no LEI / not in GLEIF")
        month = max(int(r["formed_month"]), 0)
        ev = [f"registry:{r['entity_id']}", f"officer_match:{r['same_owner']}", f"address_match:{r['same_address']}"]
        out.append(sig("S6", r["borrower_id"], "RELATED_ENTITY", 0.35, 0.9, ev,
                       f"Undisclosed related company '{r['name']}' shares the borrower's "
                       f"{'officer' if r['same_owner'] else 'address'}", month, [r["entity_id"]]))
        if len(indicators) >= 3:
            out.append(sig("S6", r["borrower_id"], "SHELL_INDICATORS", 0.6, 0.5 + 0.1 * len(indicators), ev,
                           f"'{r['name']}' looks like a shell: " + ", ".join(indicators), month, [r["entity_id"]]))
    return out
