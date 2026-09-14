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

When the borrower (or its parent) files with the SEC, its own filings are a second
source: the 10-K debt footnote and 8-K Item 2.03 ("creation of a direct financial
obligation") name its lenders. A lender named there, but never disclosed to Wells
Fargo two months after the filing, is FILED_DEBT_UNDISCLOSED: a checkable fact that
needs no lien (unsecured debt leaves no UCC filing). 8-K Item 2.04 (a lender sped up
repayment) is shown as context: a credit event, not fraud.
"""
import re

from rapidfuzz import fuzz, process

from bt.systems.base import Ctx, sig

COLLATERAL_OVERLAP = re.compile(r"receivable|chattel|inventory|all assets", re.I)
SUFFIXES = {"LLC", "L L C", "INC", "CORP", "CORPORATION", "LP", "CO", "COMPANY", "LTD"}
# how filers shorten company names on lien forms; expanded before any comparison
ABBREV = {"INDS": "INDUSTRIES", "IND": "INDUSTRIES", "GRP": "GROUP", "HLDGS": "HOLDINGS", "HLDG": "HOLDINGS",
          "CAP": "CAPITAL", "INTL": "INTERNATIONAL", "MFG": "MANUFACTURING", "SVCS": "SERVICES", "SVC": "SERVICES",
          "DIST": "DISTRIBUTION", "FINL": "FINANCIAL", "MGMT": "MANAGEMENT", "PTNRS": "PARTNERS", "ASSOC": "ASSOCIATES"}
FUZZY_CUTOFF = 88
FILING_GRACE = 2  # months a borrower has to tell the bank about debt it announced to the SEC

FILED_DEBT = """
SELECT borrower_id, counterparty_entity_id AS lender, any_value(counterparty_name) AS name, min(filed_month) AS first_m,
       list(DISTINCT form || ' ' || item ORDER BY form || ' ' || item) AS forms
FROM sec_filings WHERE item IN ('debt', '2.03') AND coalesce(counterparty_entity_id, '') NOT IN ('', 'E_WF')
GROUP BY 1, 2
"""
ADDRESS_NAME_FLOOR = 60  # a filing at a company's exact registered address still needs a broadly similar name


def norm_addr(a) -> str:
    return re.sub(r"[^A-Z0-9]", "", (a or "").upper())


def core(name: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", "", (name or "").upper().replace(".", ""))
    toks = [ABBREV.get(t, t) for t in s.split()]
    return " ".join(t for t in toks if t not in SUFFIXES)


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
    by_addr: dict[str, list[dict]] = {}
    for r in scope:
        by_addr.setdefault(norm_addr(r["address"]), []).append(r)
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
        by_address = False
        # names collide (two unrelated "Apex Credit" firms); the filing's debtor address settles which one it is
        addr = norm_addr(u.get("debtor_address"))
        if addr:
            targets = [t for t in targets if norm_addr(t["address"]) == addr]
            if not targets:  # a mangled name filed at the exact registered address of a company in scope
                k = core(u["debtor_name"])
                targets = [t for t in by_addr.get(addr, []) if k.split()[:1] == core(t["name"]).split()[:1]
                           and fuzz.token_set_ratio(k, core(t["name"])) >= ADDRESS_NAME_FLOOR]
                by_address, score = bool(targets), 90
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
            fuzzy = (f" [matched by its registered address; filed as '{u['debtor_name']}']" if by_address else
                     "" if score == 100 else f" [name matched at {score:.0f}%: '{u['debtor_name']}']")
            s = sig("S5", b, typ, 0.9 if t["role"] == "related" else 0.8, conf,
                    [f"ucc:{u['state']}-{u['filing_id']}", f"disclosures:{b}#debt"],
                    f"'{u['secured_party_name']}' holds a lien on {on} ('{t['name']}': {u['collateral_desc']}) "
                    f"that the borrower never disclosed{note}{fuzzy}", u["filed_month"],
                    [x for x in (lender, t["entity_id"]) if x])
            out.append(s)
            if not stale:
                undisclosed.setdefault(b, []).append(s.signal_id)
    exact: dict[str, set] = {}  # full legal name, suffix included -> registry entities
    for r in ctx.rows("SELECT entity_id, name FROM entities"):
        exact.setdefault(norm_addr(r["name"]), set()).add(r["entity_id"])
    for c in ctx.rows("SELECT * FROM courts"):
        targets, score = match(c["defendant_name"])
        owners = exact.get(norm_addr(c["defendant_name"]), set())
        if owners:  # the judgment names a registered company exactly: it belongs to that one, not a look-alike
            targets = [t for t in targets if t["entity_id"] in owners]
        for t in targets:
            big = c["amount"] > 1_000_000
            out.append(sig("S5", t["borrower_id"], "JUDGMENT", 0.5 if big else 0.15, 0.9 if score == 100 else 0.8,
                           [f"court:{c['case_id']}"],
                           f"Judgment of ${c['amount']:,.0f} against '{c['defendant_name']}' in favour of {c['plaintiff']}",
                           c["month"], [t["entity_id"]]))
    if not ctx.shared.get("sec_off"):
        for f in ctx.rows(FILED_DEBT):
            b = f["borrower_id"]
            if (b, f["lender"]) in disclosed or f["first_m"] > ctx.as_of - FILING_GRACE:
                continue
            forms = ", ".join(x.replace(" debt", " debt footnote").replace("8-K 2.03", "8-K Item 2.03") for x in f["forms"])
            s = sig("S5", b, "FILED_DEBT_UNDISCLOSED", 0.85, 0.9,
                    [f"sec_filing:{b}:{x.replace(' ', '_')}" for x in f["forms"]] + [f"disclosures:{b}#debt"],
                    f"The borrower's own SEC filings ({forms}) name '{f['name']}' as a lender, but that debt was never "
                    f"disclosed to Wells Fargo", f["first_m"], [f["lender"]])
            out.append(s)
            undisclosed.setdefault(b, []).append(s.signal_id)
        for e in ctx.rows("SELECT * FROM sec_filings WHERE item = '2.04' ORDER BY filed_month"):
            out.append(sig("S5", e["borrower_id"], "DEBT_ACCELERATION_FILED", 0.2, 1.0,
                           [f"sec_filing:{e['borrower_id']}:8-K_2.04:month={e['filed_month']}"],
                           f"8-K Item 2.04: '{e['counterparty_name']}' accelerated or increased the borrower's debt "
                           f"(a credit event to review, not a sign of fraud)", e["filed_month"],
                           [e["counterparty_entity_id"]] if e["counterparty_entity_id"] else []))
    ctx.shared["s5_undisclosed"] = undisclosed
    return out
