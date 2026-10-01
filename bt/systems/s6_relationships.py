"""S6 Relationship mapper: who is really connected to this borrower?

Mechanism (DOJ First Brands release, VERIFY F3): related "James Entities" that
"had no independent business operations" carried hidden debt.

Finds entities sharing the borrower's officer, address, phone number or
registered agent, checks whether each was disclosed, and scores how shell-like
it is. A company registered to someone else (a nominee) at another address can
still give itself away through the borrower's phone number or the borrower's
owner acting as its registered agent. A registered agent that serves many
companies is a commercial agent service, not a link, and is ignored.

Publishes the `related` table that S1, S3 and S5 use to widen their search.

Borrowers that file with the SEC list their subsidiaries in 10-K Exhibit 21. A listed
subsidiary joins `related` even when the registry shows no shared officer, address,
phone or agent (a nominee can hide those; an audited filing can't leave it out). Being
publicly listed is not concealment, so a listing alone is never scored as shell-like:
it matters when that company also pays the borrower or holds a lien.
"""
from bt.common import bank
from bt.systems.base import Ctx, sig

PERSONAL_AGENT_MAX = 3  # an agent serving more companies than this is a commercial registered-agent service


def related_sql(has_contact: bool) -> str:
    ph = (lambda t: f"{t}.phone") if has_contact else (lambda t: "CAST(NULL AS VARCHAR)")
    ag = (lambda t: f"{t}.registered_agent") if has_contact else (lambda t: "CAST(NULL AS VARCHAR)")
    return f"""
CREATE OR REPLACE TABLE related AS
WITH ent AS (
    SELECT e.*, {ph('e')} AS phone_, {ag('e')} AS agent_ FROM entities e
), personal AS (
    SELECT agent_ AS agent FROM ent WHERE agent_ IS NOT NULL GROUP BY 1 HAVING count(*) <= {PERSONAL_AGENT_MAX}
), b AS (
    SELECT b.borrower_id, b.entity_id, e.officer_person_id AS owner, e.address, e.phone_ AS phone,
           CASE WHEN e.agent_ IN (SELECT agent FROM personal) THEN e.agent_ END AS agent
    FROM borrowers b JOIN ent e USING (entity_id)
), rel AS (
    SELECT b.borrower_id, e.entity_id, e.name, e.kind, e.has_operations, e.formed_month,
           coalesce(e.officer_person_id = b.owner, false) AS same_owner,
           coalesce(e.address = b.address, false) AS same_address,
           coalesce(e.phone_ = b.phone, false) AS same_phone,
           coalesce(e.agent_ = b.agent, false) AS same_agent
    FROM b JOIN ent e
      ON e.entity_id <> b.entity_id
     AND (e.officer_person_id = b.owner OR e.address = b.address OR e.phone_ = b.phone OR e.agent_ = b.agent)
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


EXHIBIT21 = """
INSERT INTO related BY NAME
SELECT f.borrower_id, e.entity_id, e.name, e.kind, e.has_operations, e.formed_month,
       false AS same_owner, false AS same_address, false AS same_phone, false AS same_agent, true AS via_filing,
       d.counterparty_entity_id IS NOT NULL AS disclosed, g.entity_id IS NOT NULL AS in_gleif
FROM (SELECT DISTINCT borrower_id, counterparty_entity_id FROM sec_filings WHERE item = 'subsidiary') f
JOIN entities e ON e.entity_id = f.counterparty_entity_id
LEFT JOIN (SELECT DISTINCT borrower_id, counterparty_entity_id FROM disclosures WHERE kind = 'related_party') d
       ON d.borrower_id = f.borrower_id AND d.counterparty_entity_id = f.counterparty_entity_id
LEFT JOIN (SELECT DISTINCT entity_id FROM gleif) g ON g.entity_id = e.entity_id
WHERE NOT EXISTS (SELECT 1 FROM related r WHERE r.borrower_id = f.borrower_id AND r.entity_id = f.counterparty_entity_id)
"""


def run(ctx: Ctx):
    cols = {r[0] for r in ctx.con.execute("DESCRIBE entities").fetchall()}
    ctx.con.execute(related_sql({"phone", "registered_agent"} <= cols))
    ctx.con.execute("ALTER TABLE related ADD COLUMN via_filing BOOLEAN DEFAULT false")
    if not ctx.shared.get("sec_off"):
        ctx.con.execute(EXHIBIT21)
    listed = {(r["borrower_id"], r["counterparty_entity_id"]) for r in ctx.rows(
        "SELECT DISTINCT borrower_id, counterparty_entity_id FROM sec_filings WHERE item = 'subsidiary'")}
    out = []
    for r in ctx.rows("SELECT * FROM related ORDER BY borrower_id, entity_id"):
        if r["disclosed"]:  # a disclosed affiliate is normal; nothing to explain away
            continue
        in_ex21 = (r["borrower_id"], r["entity_id"]) in listed and not ctx.shared.get("sec_off")
        links = [w for w, k in (("officer", "same_owner"), ("address", "same_address"),
                                ("phone number", "same_phone"), ("registered agent", "same_agent")) if r[k]]
        if r["via_filing"]:
            month = max(int(r["formed_month"]), 0)
            out.append(sig("S6", r["borrower_id"], "RELATED_ENTITY", 0.35, 0.9,
                           [f"registry:{r['entity_id']}", f"sec_filing:{r['borrower_id']}:10-K_exhibit_21"],
                           f"'{r['name']}' is listed as a subsidiary in the borrower's 10-K (Exhibit 21) but was not "
                           f"disclosed to {bank.NAME} as a related party", month, [r["entity_id"]]))
            continue  # publicly listed: not concealment, so never scored as shell-like on its own
        indicators = []
        if not r["has_operations"]:
            indicators.append("no operations")
        if r["same_address"]:
            indicators.append("same address as borrower")
        if ctx.as_of - r["formed_month"] <= 12:
            indicators.append(f"formed {ctx.as_of - r['formed_month']} months ago")
        if not r["in_gleif"]:
            indicators.append("no LEI / not in GLEIF")
        if not (r["same_owner"] or r["same_address"]):
            indicators.append("registered to a different person and address, linked only by " + " and ".join(links))
        month = max(int(r["formed_month"]), 0)
        ev = [f"registry:{r['entity_id']}", f"officer_match:{r['same_owner']}", f"address_match:{r['same_address']}"]
        if r["same_phone"] or r["same_agent"]:
            ev += [f"phone_match:{r['same_phone']}", f"agent_match:{r['same_agent']}"]
        out.append(sig("S6", r["borrower_id"], "RELATED_ENTITY", 0.35, 0.9, ev,
                       f"Undisclosed related company '{r['name']}' shares the borrower's {' and '.join(links)}",
                       month, [r["entity_id"]]))
        if in_ex21:
            ev.append(f"sec_filing:{r['borrower_id']}:10-K_exhibit_21")
        if len(indicators) >= 3:
            out.append(sig("S6", r["borrower_id"], "SHELL_INDICATORS", 0.6, min(1.0, 0.5 + 0.1 * len(indicators)), ev,
                           f"'{r['name']}' looks like a shell: " + ", ".join(indicators), month, [r["entity_id"]]))
    return out
