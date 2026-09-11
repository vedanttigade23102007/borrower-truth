"""S5 Hidden-debt finder: who else has a claim on this borrower?

Mechanisms: First Brands concealed "substantial liabilities" and off-sheet
lenders (VERIFY F1, F3). Tricolor-style double pledging to another lender shows
up as a competing lien on the same collateral (T1, T2).

Real lien registers and court dockets hold NAMES, not IDs, and filers misspell
them. So matching is by normalised name with a fuzzy fallback, against the
borrower AND every entity S6 linked to it. Some misfiled liens will still be
missed; that is reported, not hidden.

Old undisclosed liens that pre-date onboarding are often stale (debt repaid,
filing never terminated). They are reported at lower confidence and asked
about, not treated as proof.
"""
import re

from rapidfuzz import fuzz, process

from bt.systems.base import Ctx, sig

COLLATERAL_OVERLAP = re.compile(r"receivable|chattel|inventory|all assets", re.I)
SUFFIXES = {"LLC", "L L C", "INC", "CORP", "CORPORATION", "LP", "CO", "COMPANY", "LTD"}
FUZZY_CUTOFF = 88


def norm_addr(a) -> str:
    return re.sub(r"[^A-Z0-9]", "", (a or "").upper())


def core(name: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", "", (name or "").upper().replace(".", ""))
    toks = [t for t in s.split() if t not in SUFFIXES]
    return " ".join(toks)


def run(ctx: Ctx):
    scope = ctx.rows("""
        SELECT b.borrower_id, b.entity_id, e.name, e.address, 'borrower' AS role
        FROM borrowers b JOIN entities e USING (entity_id)
        UNION ALL
        SELECT r.borrower_id, r.entity_id, r.name, e.address, 'related' AS role
        FROM related r JOIN entities e USING (entity_id)""")
    index: dict[str, list[dict]] = {}
    for r in scope:
        index.setdefault(core(r["name"]), []).append(r)
    keys = list(index)
    registry = {core(r["name"]): r["entity_id"] for r in ctx.rows("SELECT entity_id, name FROM entities")}
    disclosed = {(r["borrower_id"], r["counterparty_entity_id"]) for r in ctx.rows(
        "SELECT borrower_id, counterparty_entity_id FROM disclosures WHERE kind = 'debt'")}

    def match(name):
        k = core(name)
        if k in index:
            return index[k], 100
        hit = process.extractOne(k, keys, scorer=fuzz.token_sort_ratio, score_cutoff=FUZZY_CUTOFF)
        return (index[hit[0]], hit[1]) if hit else ([], 0)

    out, undisclosed = [], {}
    for u in ctx.rows("SELECT * FROM ucc ORDER BY filed_month"):
        if "WELLS FARGO" in u["secured_party_name"].upper():
            continue
        targets, score = match(u["debtor_name"])
        # names collide (two unrelated "Apex Credit" firms); the filing's debtor address settles which one it is
        addr = norm_addr(u.get("debtor_address"))
        if addr:
            targets = [t for t in targets if norm_addr(t["address"]) == addr]
        lender = registry.get(core(u["secured_party_name"]))
        for t in targets:
            b = t["borrower_id"]
            if (b, lender) in disclosed:
                continue
            overlap = bool(COLLATERAL_OVERLAP.search(u["collateral_desc"]))
            stale = u["filed_month"] < 0
            typ = "COMPETING_LIEN" if overlap else "UNDISCLOSED_SECURED_PARTY"
            on = "a related company" if t["role"] == "related" else "the borrower"
            conf = (0.5 if stale else 0.85) * (1.0 if score == 100 else 0.9)
            note = " (filed before onboarding: may be a stale filing)" if stale else ""
            fuzzy = "" if score == 100 else f" [name matched at {score:.0f}%: '{u['debtor_name']}']"
            s = sig("S5", b, typ, 0.9 if t["role"] == "related" else 0.8, conf,
                    [f"ucc:{u['state']}-{u['filing_id']}", f"disclosures:{b}#debt"],
                    f"'{u['secured_party_name']}' holds a lien on {on} ('{t['name']}': {u['collateral_desc']}) "
                    f"that the borrower never disclosed{note}{fuzzy}", u["filed_month"],
                    [x for x in (lender, t["entity_id"]) if x])
            out.append(s)
            if not stale:
                undisclosed.setdefault(b, []).append(s.signal_id)
    for c in ctx.rows("SELECT * FROM courts"):
        targets, score = match(c["defendant_name"])
        for t in targets:
            big = c["amount"] > 1_000_000
            out.append(sig("S5", t["borrower_id"], "JUDGMENT", 0.5 if big else 0.15, 0.9 if score == 100 else 0.8,
                           [f"court:{c['case_id']}"],
                           f"Judgment of ${c['amount']:,.0f} against '{c['defendant_name']}' in favour of {c['plaintiff']}",
                           c["month"], [t["entity_id"]]))
    ctx.shared["s5_undisclosed"] = undisclosed
    return out
