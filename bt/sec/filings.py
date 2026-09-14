"""Real SEC filings for public non-bank lenders: XBRL financials, 8-K debt events, Exhibit 21.

This is the real-data side of the "what they tell the SEC vs what they tell the bank" check.
The bank's own file on these companies is private, so here we measure what the public side
looks like in practice: how often lenders file new-debt 8-Ks (the alert volume an officer
would see), how many subsidiaries they list (what an Exhibit 21 cross-check must cope with),
and whether their reported numbers can be pulled cleanly quarter by quarter.

    uv run python -m bt.sec.filings            # writes data/calibration/sec_filers.json
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

from bt.sec import edgar

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "calibration", "sec_filers.json")

# public non-bank lenders across the kinds Wells Fargo lends to (CIKs from SEC company_tickers.json)
COMPANIES = {
    "CACC": (885550, "Credit Acceptance", "auto finance"),
    "CPSS": (889609, "Consumer Portfolio Services", "auto finance"),
    "KMX": (1170010, "CarMax", "auto finance"),
    "OMF": (1584207, "OneMain Holdings", "consumer finance"),
    "ENVA": (1529864, "Enova International", "consumer finance"),
    "OPRT": (1538716, "Oportun Financial", "consumer finance"),
    "RM": (1519401, "Regional Management", "consumer finance"),
    "WRLD": (108385, "World Acceptance", "consumer finance"),
    "UPST": (1647639, "Upstart Holdings", "consumer finance"),
    "AFRM": (1820953, "Affirm Holdings", "consumer finance"),
    "ATLC": (1464343, "Atlanticus Holdings", "consumer finance"),
    "NAVI": (1593538, "Navient", "consumer finance"),
    "PFSI": (1745916, "PennyMac Financial Services", "mortgage"),
    "RKT": (1805284, "Rocket Companies", "mortgage"),
    "UWMC": (1783398, "UWM Holdings", "mortgage"),
    "LDI": (1831631, "loanDepot", "mortgage"),
    "ARCC": (1287750, "Ares Capital", "business development company"),
    "FSK": (1422183, "FS KKR Capital", "business development company"),
    "MAIN": (1396440, "Main Street Capital", "business development company"),
    "HTGC": (1280784, "Hercules Capital", "business development company"),
    "BXSL": (1736035, "Blackstone Secured Lending", "business development company"),
    "OBDC": (1655888, "Blue Owl Capital Corp", "business development company"),
    "PSEC": (1287032, "Prospect Capital", "business development company"),
    "GBDC": (1476765, "Golub Capital BDC", "business development company"),
}
# XBRL concepts, first one reported wins (companies tag the same idea differently)
REVENUE = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "InterestAndDividendIncomeOperating",
           "GrossInvestmentIncomeOperating", "InvestmentIncomeInterestAndDividend", "InterestIncomeOperating",
           "FinanceAndOtherIncome", "InterestAndFeeIncomeLoansAndLeases")
RECEIVABLES = ("LoansAndLeasesReceivableNetReportedAmount", "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
               "FinancingReceivableAfterAllowanceForCreditLoss", "NotesReceivableNet", "LoansReceivableNet",
               "InvestmentOwnedAtFairValue", "LoansHeldForSaleFairValueDisclosure")
DEBT = ("DebtInstrumentCarryingAmount", "LongTermDebt", "SecuredDebt", "DebtLongtermAndShorttermCombinedAmount",
        "LongTermDebtNoncurrent", "NotesPayable", "OtherBorrowings")


def quarterly(facts: dict, concepts, instant: bool) -> tuple[str | None, list]:
    """Quarterly values of the first concept the company actually reports (10-Q/10-K, USD)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for c in concepts:
        units = gaap.get(c, {}).get("units", {}).get("USD")
        if not units:
            continue
        pts = {}
        for u in units:
            if u.get("form") not in ("10-Q", "10-K") or not u.get("end"):
                continue
            if not instant:  # durations: keep 3-month periods only
                if not u.get("start"):
                    continue
                days = (date.fromisoformat(u["end"]) - date.fromisoformat(u["start"])).days
                if not 80 <= days <= 100:
                    continue
            pts[u["end"]] = u["val"]
        if len(pts) >= 4:
            return c, sorted(pts.items())[-12:]
    return None, []


def exhibit21_count(cik: int, subs: dict) -> tuple[int | None, str | None]:
    """Number of subsidiaries listed in the latest 10-K's Exhibit 21 (rows or lines that name a company)."""
    rec = subs["filings"]["recent"]
    for form, acc in zip(rec["form"], rec["accessionNumber"]):
        if form != "10-K":
            continue
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        items = edgar.get_json(base + "/index.json")["directory"]["item"]
        ex21 = [i["name"] for i in items if re.search(r"ex-?21|exhibit-?21|ex21", i["name"], re.I)
                and i["name"].lower().endswith((".htm", ".html", ".txt"))]
        if not ex21:
            return None, base
        html = edgar.get(f"{base}/{ex21[0]}").decode("utf-8", "ignore")
        text = re.sub(r"<[^>]+>", "\n", html)
        text = re.sub(r"&nbsp;|&#160;", " ", text)
        names = [l.strip() for l in text.splitlines()
                 if re.search(r"\b(LLC|L\.L\.C\.|Inc\.?|Corp|Corporation|LP|L\.P\.|Ltd|Limited|Trust|Company|Co\.)\b", l)
                 and 3 < len(l.strip()) < 160 and not re.search(r"subsidiaries of|jurisdiction", l, re.I)]
        return len(set(names)), f"{base}/{ex21[0]}"
    return None, None


def eight_k_items(subs: dict, since: date) -> dict:
    rec = subs["filings"]["recent"]
    out = {"8-K": 0, "2.03": 0, "2.04": 0, "examples": []}
    for form, d, items, acc in zip(rec["form"], rec["filingDate"], rec["items"], rec["accessionNumber"]):
        if form != "8-K" or date.fromisoformat(d) < since:
            continue
        out["8-K"] += 1
        its = {i.strip() for i in (items or "").split(",")}
        for k in ("2.03", "2.04"):
            if k in its:
                out[k] += 1
                if len(out["examples"]) < 3:
                    out["examples"].append(dict(date=d, item=k, accession=acc))
    return out


def run():
    since = date.today() - timedelta(days=365)
    res = {}
    for t, (cik, name, kind) in COMPANIES.items():
        cik10 = f"{cik:010d}"
        subs = edgar.get_json(f"https://data.sec.gov/submissions/CIK{cik10}.json")
        facts = edgar.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")
        rc, rev = quarterly(facts, REVENUE, instant=False)
        kc, rcv = quarterly(facts, RECEIVABLES, instant=True)
        dc, debt = quarterly(facts, DEBT, instant=True)
        n21, src21 = exhibit21_count(cik, subs)
        res[t] = dict(name=name, kind=kind, cik=cik, eight_k_last_12m=eight_k_items(subs, since),
                      exhibit21_subsidiaries=n21, exhibit21_source=src21,
                      revenue=dict(concept=rc, quarters=rev), receivables=dict(concept=kc, quarters=rcv),
                      debt=dict(concept=dc, quarters=debt))
        e = res[t]["eight_k_last_12m"]
        print(f"{t:5} {name:30} 8-K {e['8-K']:3} (2.03: {e['2.03']}, 2.04: {e['2.04']}) · Ex21 {n21} · "
              f"rev {rc} ({len(rev)}q) · rcv {kc} ({len(rcv)}q) · debt {dc} ({len(debt)}q)", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(pulled=str(date.today()), window_since=str(since), companies=res), open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    run()
