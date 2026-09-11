"""Synthetic NDFI loan book with planted, labelled fraud mechanisms.

EVERYTHING THIS WRITES IS SYNTHETIC. No real company, person, vehicle or loan is
represented. VINs start with "SYN" so they can never be mistaken for real ones.

The fraud mechanisms mirror allegations in the DOJ/SEC documents behind the
deck (research/VERIFY.md T1-T8 Tricolor, F1-F5 First Brands). Innocent
look-alikes are planted too, so false alarms can be measured honestly.

The answer key goes to labels.json. Detection systems must never read it;
only bt/eval does.

    uv run python -m bt.datagen.generate --borrowers 120 --scale 1.0 --out data/out/demo
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

MONTHS = 24
FRAUD_MECHS = (
    "DOUBLE_PLEDGE", "TAPE_DRESSUP", "DISGUISED_RECEIPTS", "FAKE_INVOICES",
    "HIDDEN_DEBT", "RELATED_SHELLS", "FIN_MANIPULATION",
)
PATTERNS = {
    "tricolor_like": ("DOUBLE_PLEDGE", "TAPE_DRESSUP", "FIN_MANIPULATION"),
    "first_brands_like": ("FAKE_INVOICES", "HIDDEN_DEBT", "RELATED_SHELLS",
                          "DISGUISED_RECEIPTS", "FIN_MANIPULATION"),
}
BENIGN = ("DEFERMENT_PROGRAM", "DISCLOSED_RELATED_LEASE", "LATE_TAPE",
          "NAME_TYPO", "DISCLOSED_EQUIPMENT_LIEN", "SEASONAL_REVENUE",
          # honest look-alikes that real books are full of
          "STALE_LIEN",            # old lien never released after the debt was repaid
          "THIRD_PARTY_PAYER",     # relatives, employers or insurers paying an obligor's loan
          "UNDISCLOSED_DEFERRAL",  # a small hardship deferral nobody told the bank about
          "NEW_AFFILIATE")         # a new operating affiliate not yet disclosed
TAPE_ONLY_BENIGN = ("DEFERMENT_PROGRAM", "LATE_TAPE", "THIRD_PARTY_PAYER", "UNDISCLOSED_DEFERRAL")
BTYPES = ("auto_finance", "consumer_finance", "real_estate_finance", "receivables_finance")
BTYPE_P = (0.35, 0.20, 0.15, 0.30)
TAPE_TYPES = BTYPES[:3]
RISK = {"auto_finance": 1.0, "consumer_finance": 1.4, "real_estate_finance": 0.6}
BAL = {"auto_finance": 18_000, "consumer_finance": 6_000, "real_estate_finance": 240_000}
REV_FACTOR = {"auto_finance": 0.35, "consumer_finance": 0.45, "real_estate_finance": 0.25}

W1 = ["Apex", "Summit", "Harbor", "Crescent", "Granite", "Beacon", "Pioneer", "Keystone",
      "Meridian", "Sterling", "Cobalt", "Juniper", "Redwood", "Lakeshore", "Ironwood",
      "Silverline", "Northstar", "Bluebonnet", "Prairie", "Tidewater", "Canyon", "Magnolia"]
W2 = ["Auto", "Motor", "Credit", "Capital", "Finance", "Lending", "Funding", "Holdings",
      "Parts", "Supply", "Trade", "Distribution", "Industries", "Partners", "Realty"]
SUFFIX = ["LLC", "Inc", "Corp", "LP", "Group LLC"]
FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Priya", "David", "Aisha", "Carlos",
         "Emily", "Wei", "Sofia", "Daniel", "Grace", "Omar", "Hannah", "Luis", "Nora", "Ethan", "Mei"]
LAST = ["Smith", "Garcia", "Johnson", "Patel", "Brown", "Nguyen", "Lopez", "Kim", "Davis",
        "Martinez", "Wilson", "Chen", "Anderson", "Thomas", "Moore", "Jackson", "Lee", "Clark"]
STREETS = ["Commerce St", "Main St", "Industrial Pkwy", "Market Ave", "Oak Blvd", "Center Dr",
           "Harbor Rd", "Elm St", "Park Ave", "Gateway Blvd"]
STATES = ["TX", "FL", "OH", "NY", "CA", "GA", "IL", "NC", "AZ", "NJ"]
PRODUCTS = ["brake assemblies", "oil filters", "wiper blades", "LED lamps", "spark plugs",
            "fuel pumps", "batteries", "air filters", "rotors", "belts and hoses"]
VIN_CHARS = np.array(list("ABCDEFGHJKLMNPRSTUVWXYZ0123456789"))

SMALL = ("borrowers", "facilities", "entities", "persons", "gleif", "disclosures",
         "ucc_filings", "court_records", "financials", "pledgecheck")
BIG = ("tape", "source_truth", "payments", "invoices")


class Book:
    def __init__(self, seed: int, n_borrowers: int, scale: float, fraud_rate: float):
        self.rng = np.random.default_rng(seed)
        self.seed, self.n, self.scale, self.fraud_rate = seed, n_borrowers, scale, fraud_rate
        self.small = {k: [] for k in SMALL}
        self.big = {k: [] for k in BIG}
        self.labels: dict[str, dict] = {}
        self._names: set[str] = set()
        self._ename: dict[str, str] = {"E_WF": "Wells Fargo Bank, N.A. (as lender in this simulation)"}
        self._eaddr: dict[str, str] = {"E_WF": "(n/a)"}
        self._n_ent = self._n_person = self._n_addr = self._n_txn = self._n_inv = 0
        self.lenders = [self.entity("lender", self.company_name(lender=True), None, self.address(),
                                    formed=-240, ops=True) for _ in range(14)]
        self.wf = "E_WF"
        self.small["entities"].append(dict(entity_id=self.wf, name="Wells Fargo Bank, N.A. (as lender in this simulation)",
                                           kind="bank", officer_person_id=None, address="(n/a)", state="SD",
                                           formed_month=-1800, has_operations=True))
        self.debtors = [self.entity("debtor", self.company_name(), None, self.address(),
                                    formed=int(self.rng.integers(-400, -60)), ops=True) for _ in range(300)]
        self.debtor_size = {d: float(self.rng.lognormal(np.log(40_000), 0.9)) for d in self.debtors}

    # ---------- small helpers ----------
    def company_name(self, lender=False) -> str:
        rng = self.rng
        for _ in range(1000):
            if lender:
                n = f"{rng.choice(W1)} {rng.choice(['Capital Partners', 'Credit Fund', 'Specialty Finance', 'Asset Finance'])} {rng.choice(['LLC', 'LP'])}"
            else:
                n = f"{rng.choice(W1)} {rng.choice(W2)} {rng.choice(SUFFIX)}"
            if n not in self._names:
                self._names.add(n)
                return n
        n = f"{rng.choice(W1)} {rng.choice(W2)} {self._n_ent} LLC"
        self._names.add(n)
        return n

    def person(self) -> str:
        self._n_person += 1
        pid = f"P{self._n_person:05d}"
        self.small["persons"].append(dict(person_id=pid, name=f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"))
        return pid

    def address(self) -> str:
        self._n_addr += 1
        return f"{int(self.rng.integers(10, 9999))} {self.rng.choice(STREETS)}, Suite {self._n_addr}"

    def entity(self, kind, name, officer, address, formed, ops, state=None) -> str:
        self._n_ent += 1
        eid = f"E{self._n_ent:06d}"
        self.small["entities"].append(dict(entity_id=eid, name=name, kind=kind, officer_person_id=officer,
                                           address=address, state=state or str(self.rng.choice(STATES)),
                                           formed_month=int(formed), has_operations=bool(ops)))
        self._ename[eid] = name
        self._eaddr[eid] = address
        return eid

    def ename(self, eid) -> str:
        return self._ename[eid]

    def name_variant(self, name: str) -> str:
        """How filers actually misspell debtor names: dropped suffix, abbreviations, odd spacing."""
        r = self.rng.random()
        parts = name.split()
        base = " ".join(parts[:-1]) if parts[-1] in ("LLC", "Inc", "Corp", "LP") else name
        if r < 0.4:
            return base
        if r < 0.7:
            return (base.replace("Group", "Grp").replace("Holdings", "Hldgs").replace("Capital", "Cap")
                    .replace("Industries", "Inds") + " L.L.C.")
        return name.upper().replace(" ", "  ", 1)

    def ucc(self, debtor, secured, collateral, month, variant=False):
        """Lien registers hold NAMES, not IDs; systems must match on names (and misspellings)."""
        dname = self.ename(debtor)
        self.small["ucc_filings"].append(dict(
            filing_id=f"UCC-{len(self.small['ucc_filings']) + 1:06d}", state=str(self.rng.choice(STATES)),
            debtor_name=self.name_variant(dname) if variant else dname,
            debtor_address=self._eaddr[debtor],  # UCC-1 forms carry the debtor's mailing address
            secured_party_name=self.ename(secured) if secured != self.wf else "Wells Fargo Bank, N.A.",
            collateral_desc=collateral, filed_month=int(month)))

    def txn_ids(self, k):
        ids = np.char.add("T", np.char.zfill((np.arange(k) + self._n_txn).astype(str), 9))
        self._n_txn += k
        return ids

    # ---------- plan who is fraudulent ----------
    def plan(self):
        rng = self.rng
        n_f = int(round(self.n * self.fraud_rate))
        plans = []
        n_tri = max(1, round(n_f * 0.18))
        n_fb = max(1, round(n_f * 0.18))
        for _ in range(n_tri):
            plans.append(("tricolor_like", list(PATTERNS["tricolor_like"]), str(rng.choice(TAPE_TYPES))))
        for _ in range(n_fb):
            plans.append(("first_brands_like", list(PATTERNS["first_brands_like"]),
                          "receivables_finance" if rng.random() < 0.7 else str(rng.choice(TAPE_TYPES))))
        singles = [m for m in FRAUD_MECHS if m != "RELATED_SHELLS"]
        for i in range(n_f - n_tri - n_fb):
            m = singles[i % len(singles)]
            if m == "TAPE_DRESSUP":
                bt = str(rng.choice(TAPE_TYPES))
            elif m == "FAKE_INVOICES":
                bt = "receivables_finance"
            else:
                bt = str(rng.choice(BTYPES, p=BTYPE_P))
            mechs = [m] + (["RELATED_SHELLS"] if m in ("HIDDEN_DEBT", "DISGUISED_RECEIPTS") and rng.random() < 0.6 else [])
            plans.append(("single", mechs, bt))
        for _ in range(self.n - len(plans)):
            plans.append((None, [], str(rng.choice(BTYPES, p=BTYPE_P))))
        order = rng.permutation(len(plans))
        return [plans[i] for i in order]

    # ---------- one borrower ----------
    def borrower(self, i, plan):
        rng = self.rng
        pattern, mechs, btype = plan
        fraud = bool(mechs)
        start = int(rng.integers(6, 17)) if fraud else None
        bid = f"B{i:04d}"
        owner = self.person()
        addr = self.address()
        name = self.company_name()
        state = str(rng.choice(STATES))
        ent = self.entity("borrower", name, owner, addr, formed=int(rng.integers(-150, -24)), ops=True, state=state)
        tape_based = btype in TAPE_TYPES
        # the answer key may only list tricks this kind of business can actually carry
        mechs = [m for m in mechs if not (m == "FAKE_INVOICES" and tape_based)
                 and not (m == "TAPE_DRESSUP" and not tape_based)]
        benign = [b for b in BENIGN if rng.random() < 0.16 and
                  (b not in TAPE_ONLY_BENIGN or tape_based) and
                  (b != "SEASONAL_REVENUE" or not tape_based)]

        # ownership: a benign, disclosed holding company for many borrowers (GLEIF-visible)
        holding = None
        if rng.random() < 0.55:
            holding = self.entity("holding", name.split()[0] + " Holdings Group LLC", owner, addr,
                                  formed=-200, ops=True, state=state)
            self.small["gleif"].append(dict(lei=f"SYNLEI{len(self.small['gleif']):014d}", entity_id=holding,
                                            legal_name=self.ename(holding), parent_entity_id=None))
            self.small["disclosures"].append(dict(borrower_id=bid, kind="related_party", counterparty_entity_id=holding,
                                                  start_month=0, note="parent holding company"))
        self.small["gleif"].append(dict(lei=f"SYNLEI{len(self.small['gleif']):014d}", entity_id=ent,
                                        legal_name=name, parent_entity_id=holding))

        # facilities
        limit = float(rng.lognormal(np.log(150e6 * max(self.scale, 0.05)), 0.6))
        f1 = f"F{i:04d}A"
        facs = [f1]
        self.small["facilities"].append(dict(facility_id=f1, borrower_id=bid, lender_entity_id=self.wf,
                                             kind="warehouse", limit=limit, advance_rate=0.85))
        if rng.random() < 0.35:
            f2 = f"F{i:04d}B"
            facs.append(f2)
            self.small["facilities"].append(dict(facility_id=f2, borrower_id=bid, lender_entity_id=self.wf,
                                                 kind="term", limit=limit * 0.4, advance_rate=0.75))
        self.ucc(ent, self.wf, "all assets, including receivables and chattel paper", -12)

        # disclosed debt
        disclosed_lenders = []
        if rng.random() < 0.5:
            L = str(rng.choice(self.lenders))
            disclosed_lenders.append(L)
            self.small["disclosures"].append(dict(borrower_id=bid, kind="debt", counterparty_entity_id=L,
                                                  start_month=0, note="disclosed subordinated facility"))
            self.ucc(ent, L, "second-priority lien on all assets", -10)
        if "DISCLOSED_EQUIPMENT_LIEN" in benign:
            L = str(rng.choice(self.lenders))
            disclosed_lenders.append(L)  # never reuse a disclosed lessor as a "hidden" lender
            self.small["disclosures"].append(dict(borrower_id=bid, kind="debt", counterparty_entity_id=L,
                                                  start_month=4, note="equipment lease"))
            self.ucc(ent, L, "specific equipment: servers, forklifts and related leases", 4)
        if "STALE_LIEN" in benign:  # repaid years ago; the filing was never terminated
            L = str(rng.choice([l for l in self.lenders if l not in disclosed_lenders]))
            disclosed_lenders.append(L)
            self.ucc(ent, L, "all assets of the debtor", int(rng.integers(-40, -8)))

        planted = {}
        # shells (fraud) — same owner, often same address, recently formed, no operations
        shells = []
        if "RELATED_SHELLS" in mechs:
            for _ in range(int(rng.integers(1, 4))):
                sname = name.split()[0] + " " + str(rng.choice(["Customer Collections", "Inventory Holdings",
                                                                "Trade Services", "Receivables"])) + " LLC"
                base = sname
                for extra in ("II", "III", "IV", "V", "VI"):
                    if sname not in self._names:
                        break
                    sname = base.replace(" LLC", f" {extra} LLC")
                self._names.add(sname)
                shells.append(self.entity("company", sname, owner, addr if rng.random() < 0.7 else self.address(),
                                          formed=start - int(rng.integers(1, 5)), ops=False, state=state))
            planted["shells"] = shells
        if "NEW_AFFILIATE" in benign:  # a real operating affiliate, just not disclosed yet
            self.entity("company", name.split()[0] + " " + str(rng.choice(["Services", "Logistics", "Insurance Agency"])) + " LLC",
                        owner, addr if rng.random() < 0.6 else self.address(), formed=int(rng.integers(2, 20)),
                        ops=True, state=state)
        # benign related entity paying disclosed rent
        lease_payer = None
        if "DISCLOSED_RELATED_LEASE" in benign:
            lease_payer = self.entity("company", name.split()[0] + " Property Partners LLC", owner, self.address(),
                                      formed=-90, ops=True, state=state)
            self.small["disclosures"].append(dict(borrower_id=bid, kind="related_party", counterparty_entity_id=lease_payer,
                                                  start_month=0, note="sublease income from affiliated property company"))

        # other-lender double pledge needs an undisclosed lender with a lien on the same collateral
        dp_other = None
        if "DOUBLE_PLEDGE" in mechs and len(facs) == 1:
            dp_other = str(rng.choice([l for l in self.lenders if l not in disclosed_lenders]))
            self.ucc(ent, dp_other, "all receivables and chattel paper (loan collateral)", start,
                     variant=rng.random() < 0.3)
            planted["double_pledge_other_lender"] = dp_other

        # collateral + collections
        if tape_based:
            coll, bal_q = self.loans(bid, btype, facs, mechs, start, benign, planted)
        else:
            coll, bal_q = self.invoices(bid, facs, mechs, start, benign, planted)

        # disguised receipts: lender money routed to look like customer payments
        if "DISGUISED_RECEIPTS" in mechs:
            payer = shells[0] if shells else str(rng.choice([l for l in self.lenders if l not in disclosed_lenders]))
            planted["disguised_payer"] = payer
            months, amts = [], []
            for m in range(start, MONTHS):
                for _ in range(int(rng.integers(1, 4))):
                    months.append(m)
                    amts.append(max(coll[m], 1e5) * rng.uniform(0.04, 0.12))
            k = len(months)
            self.big["payments"].append(dict(
                txn_id=self.txn_ids(k), month=np.array(months, np.int16), day=rng.integers(1, 29, k).astype(np.int8),
                borrower_id=np.full(k, bid), account_id=np.full(k, f1 + "-COLL"), payer_id=np.full(k, payer),
                payer_name=np.full(k, self.ename(payer)), amount=np.round(np.array(amts), 2),
                memo=np.full(k, "customer remittance"), ref=np.full(k, "")))
        if lease_payer:
            k = MONTHS
            self.big["payments"].append(dict(
                txn_id=self.txn_ids(k), month=np.arange(k, dtype=np.int16), day=np.full(k, 5, np.int8),
                borrower_id=np.full(k, bid), account_id=np.full(k, f1 + "-COLL"), payer_id=np.full(k, lease_payer),
                payer_name=np.full(k, self.ename(lease_payer)), amount=np.full(k, round(float(rng.uniform(8e3, 4e4)), 2)),
                memo=np.full(k, "sublease rent"), ref=np.full(k, "")))

        # hidden debt: an undisclosed lender with a lien on a shell (or the borrower)
        if "HIDDEN_DEBT" in mechs:
            hl = str(rng.choice([l for l in self.lenders if l not in disclosed_lenders and l != dp_other]))
            target = shells[0] if shells else ent
            self.ucc(target, hl, str(rng.choice(["inventory and proceeds", "all accounts receivable",
                                                  "all assets of the debtor"])), start - int(rng.integers(0, 3)),
                     variant=rng.random() < 0.3)
            planted["hidden_lender"] = hl
            planted["hidden_lien_debtor"] = target
            if rng.random() < 0.3:
                self.small["court_records"].append(dict(case_id=f"CV-{len(self.small['court_records']) + 1:05d}",
                                                        defendant_name=self.ename(target),
                                                        plaintiff=self.ename(hl), kind="judgment",
                                                        amount=round(float(rng.uniform(1e6, 2e7)), 2), month=MONTHS - 2))
        if rng.random() < 0.08:  # benign small judgments happen to honest firms too
            self.small["court_records"].append(dict(case_id=f"CV-{len(self.small['court_records']) + 1:05d}",
                                                    defendant_name=name, plaintiff="(synthetic) former landlord",
                                                    kind="judgment", amount=round(float(rng.uniform(2e4, 2e5)), 2),
                                                    month=int(rng.integers(0, MONTHS))))

        self.financials(bid, btype, coll, bal_q, mechs, start, benign, disclosed_lenders, limit)
        self.pledgecheck(bid, facs, mechs, start, dp_other)

        self.small["borrowers"].append(dict(borrower_id=bid, entity_id=ent, name=name, btype=btype, state=state,
                                            owner_person_id=owner, facility_limit=limit))
        self.labels[bid] = dict(fraud=fraud, pattern=pattern, mechanisms=sorted(mechs), start_month=start,
                                benign=sorted(benign), planted=planted, btype=btype)

    # ---------- loan-tape borrowers ----------
    def loans(self, bid, btype, facs, mechs, start, benign, planted):
        rng = self.rng
        M = MONTHS
        n = int(np.clip(rng.lognormal(np.log(260 * self.scale), 0.5), 20, 400_000 * max(self.scale, 1)))
        risk = RISK[btype]
        P = np.array([[1 - 0.03 * risk, 0.03 * risk, 0, 0, 0],
                      [0.50, 0, 0.50, 0, 0],
                      [0.30, 0, 0, 0.70, 0],
                      [0.10, 0, 0, 0.30, 0.60]])
        cum = P.cumsum(1)
        orig = rng.integers(-18, M - 3, n)
        bal = rng.lognormal(np.log(BAL[btype]), 0.45, n)
        cur = np.where(orig < 0, 0, -1).astype(np.int8)
        true_b = np.full((M, n), -1, np.int8)
        balh = np.zeros((M, n), np.float32)
        paid = np.zeros((M, n), bool)
        payamt = np.zeros((M, n), np.float32)
        co_month = np.full(n, 10_000)
        defer = None
        if "DEFERMENT_PROGRAM" in benign:
            d0 = int(rng.integers(3, M - 4))
            defer = (d0, d0 + 3, rng.random(n) < 0.25)
            self.small["disclosures"].append(dict(borrower_id=bid, kind="deferment_program", counterparty_entity_id=None,
                                                  start_month=d0, note=f"disclosed 3-month hardship deferment, months {d0}-{d0 + 2}"))
        for m in range(M):
            cur[(orig == m) & (cur == -1)] = 0
            act = (cur >= 0) & (cur <= 3)
            idx = np.nonzero(act)[0]
            nb = cur.copy()
            if len(idx):
                r = rng.random(len(idx))
                nb[idx] = (r[:, None] < cum[cur[idx]]).argmax(1)
            pay = act & (nb == 0)
            pay &= rng.random(n) >= 0.01  # realism: ~1% of current borrowers skip a month without going delinquent
            if defer and defer[0] <= m < defer[1]:
                dm = act & defer[2] & (cur == 0)
                nb[dm] = 0
                pay[dm] = False
            true_b[m, act] = nb[act]
            balh[m, act] = bal[act]
            inst = bal * 0.03
            payoff = pay & (rng.random(n) < 0.015)
            paid[m] = pay
            payamt[m] = np.where(payoff, bal, np.where(pay, inst, 0))
            bal = np.where(pay, bal * 0.975, bal)
            co_month[(nb == 4) & act] = m
            cur = nb
            cur[payoff] = 5

        asset_ids = np.char.add(f"A-{bid}-", np.char.zfill(np.arange(n).astype(str), 6))
        vins = np.char.add("SYN", np.array(["".join(r) for r in rng.choice(VIN_CHARS, size=(n, 14))]))
        obligor = np.char.add(f"O-{bid}-", np.char.zfill(np.arange(n).astype(str), 6))
        oname = np.char.add(np.char.add(rng.choice(FIRST, n), " "), rng.choice(LAST, n))

        # source truth: what the borrower's own servicing system really says
        mi, ai = np.nonzero(true_b >= 0)
        self.big["source_truth"].append(dict(month=mi.astype(np.int16), borrower_id=np.full(len(mi), bid),
                                             asset_id=asset_ids[ai], dpd_bucket_true=true_b[mi, ai],
                                             balance_true=np.round(balh[mi, ai], 2)))

        # reported tape
        rep = np.where((true_b >= 0) & (true_b <= 3), true_b, -1).astype(np.int8)
        # realism: ~1.5% of honest tape rows carry last month's status (servicer reporting lag)
        for m in range(1, M):
            lag = (rng.random(n) < 0.015) & (rep[m] >= 0) & (rep[m - 1] >= 0)
            rep[m, lag] = rep[m - 1, lag]
        deferred = np.zeros((M, n), np.int8)
        if "UNDISCLOSED_DEFERRAL" in benign:  # honest hardship relief, never disclosed to the bank
            u0 = int(rng.integers(3, M - 3))
            uset = rng.random(n) < 0.03
            for m in (u0, u0 + 1):
                hit = uset & (true_b[m] == 0)
                deferred[m, hit] = 1
                paid[m, hit] = False
                payamt[m, hit] = 0
        if defer:
            deferred[defer[0]:defer[1], :] = (defer[2] & True)[None, :] & (rep[defer[0]:defer[1]] == 0)
        if "TAPE_DRESSUP" in mechs:
            dress = rng.random(n) < 0.8
            defer_lie = rng.random(n) < 0.4
            zombie = rng.random(n) < 0.5
            for m in range(start, M):
                lie = dress & (true_b[m] >= 2) & (true_b[m] <= 3)
                rep[m, lie] = 0
                deferred[m, lie & defer_lie] = 1
                z = zombie & (co_month >= start - 1) & (co_month < m) & (m <= co_month + 6)
                rep[m, z] = 0
                balh[m, z] = balh[np.clip(co_month[z], 0, M - 1), np.nonzero(z)[0]]
            planted["dressed_asset_months"] = int(((rep == 0) & (true_b >= 2)).sum())
        tapes = [(facs[0], rep >= 0)]
        if "DOUBLE_PLEDGE" in mechs:
            dp = (rng.random(n) < 0.22) & (orig <= start)
            planted["double_pledged_assets"] = int(dp.sum())
            if len(facs) > 1:
                m_grid = np.arange(M)[:, None] >= start
                tapes.append((facs[1], (rep >= 0) & dp[None, :] & m_grid))
                planted["double_pledge_internal"] = True
        late_month = int(rng.integers(2, M - 2)) if "LATE_TAPE" in benign else None
        for k, (fac, mask) in enumerate(tapes):
            if late_month is not None and k == 0:
                mask = mask.copy()
                mask[late_month] = False
            mi, ai = np.nonzero(mask)
            ids = asset_ids[ai]
            if k == 1:  # the second pledge relabels half the asset IDs; VIN and obligor stay the same
                relabel = rng.random(len(ai)) < 0.5
                ids = np.where(relabel, np.char.add(f"X-{fac}-", np.char.zfill(ai.astype(str), 6)), ids)
            self.big["tape"].append(dict(
                month=mi.astype(np.int16), facility_id=np.full(len(mi), fac), borrower_id=np.full(len(mi), bid),
                asset_id=ids, vin=vins[ai], obligor_id=obligor[ai], balance=np.round(balh[mi, ai], 2),
                dpd_bucket_reported=rep[mi, ai], deferred_flag=deferred[mi, ai],
                eligible_reported=(rep[mi, ai] <= 1)))

        # obligor payments into the WF-controlled collection account
        mi, ai = np.nonzero(paid)
        pay_month = np.minimum(mi + (rng.random(len(mi)) < 0.04), M - 1)  # realism: ~4% of payments post next month
        names = oname[ai]
        payer_ids = obligor[ai]
        if "NAME_TYPO" in benign:
            t = rng.random(len(ai)) < 0.06
            names = np.where(t, np.char.add(np.char.upper(names), "."), names)
        if "THIRD_PARTY_PAYER" in benign:  # someone else pays the obligor's instalment
            tp = rng.random(len(ai)) < 0.025
            tp_names = np.char.add(np.char.add(rng.choice(FIRST, len(ai)), " "), rng.choice(LAST, len(ai)))
            names = np.where(tp, tp_names, names)
            payer_ids = np.where(tp, np.char.add(f"TP-{bid}-", np.char.zfill(np.arange(len(ai)).astype(str), 7)), payer_ids)
        k = len(mi)
        self.big["payments"].append(dict(
            txn_id=self.txn_ids(k), month=pay_month.astype(np.int16), day=rng.integers(1, 29, k).astype(np.int8),
            borrower_id=np.full(k, bid), account_id=np.full(k, facs[0] + "-COLL"), payer_id=payer_ids,
            payer_name=names, amount=np.round(payamt[mi, ai], 2), memo=np.full(k, "loan payment"), ref=asset_ids[ai]))
        coll = np.bincount(mi, weights=payamt[mi, ai], minlength=M)
        bal_q = np.array([(balh[3 * q + 2] * (rep[3 * q + 2] >= 0)).sum() for q in range(M // 3)])
        return coll, bal_q

    # ---------- receivables borrowers ----------
    def invoices(self, bid, facs, mechs, start, benign, planted):
        rng = self.rng
        M = MONTHS
        k = int(rng.integers(12, 45))
        debtors = list(rng.choice(self.debtors, k, replace=False))
        size = np.array([self.debtor_size[d] for d in debtors])
        rate = rng.uniform(1.5, 5, k) * self.scale
        season = 1 + (0.25 * np.sin(np.arange(M) * 2 * np.pi / 12) if "SEASONAL_REVENUE" in benign else 0)
        rows = {c: [] for c in ("invoice_id", "facility_id", "pledged_month", "invoice_number", "po_number", "debtor_id",
                                "debtor_name", "issue_month", "issue_day", "due_days", "amount", "description")}
        pays = []  # (month, debtor, amount, invoice_number)
        coll = np.zeros(M)
        outstanding_q = np.zeros(M // 3)
        seq = 10_000
        open_inv = []  # (amount, paid_month)

        def add(fac, pm, num, po, d, im, day, due, amt, desc):
            self._n_inv += 1
            for c, v in zip(rows, (f"INV{self._n_inv:08d}", fac, pm, num, po, d, self.ename(d), im, day, due, round(amt, 2), desc)):
                rows[c].append(v)

        n_fake = n_dup = n_dp = 0
        for m in range(M):
            counts = rng.poisson(rate * (season[m] if np.ndim(season) else 1))
            for j in np.nonzero(counts)[0]:
                for _ in range(counts[j]):
                    seq += 1
                    amt = float(size[j] * rng.lognormal(0, 0.3))
                    due = int(rng.choice([30, 45, 60]))
                    num, po = f"{bid}-{seq}", f"PO{int(rng.integers(1e5, 1e6))}"
                    desc = f"{int(rng.integers(20, 900))} units {rng.choice(PRODUCTS)}"
                    day = int(rng.integers(1, 29))
                    add(facs[0], m, num, po, debtors[j], m, day, due, amt, desc)
                    pm = m + due // 30 + int(rng.random() < 0.3)
                    diluted = rng.random() < 0.03
                    bad_debt = rng.random() < 0.015  # realism: honest customers sometimes never pay
                    if pm < M and not bad_debt:
                        pay_amt = amt * (0.9 if diluted else 1.0)
                        pays.append((pm, debtors[j], pay_amt, num))
                        coll[pm] += pay_amt
                    open_inv.append((amt, pm))
                    # double pledge: the same invoice also in the second WF facility (or another lender, not visible)
                    if "DOUBLE_PLEDGE" in mechs and m >= start and rng.random() < 0.2:
                        n_dp += 1
                        if len(facs) > 1:
                            add(facs[1], m, num, po, debtors[j], m, day, due, amt, desc)
                    # re-submitted duplicate with an altered amount (First Brands pattern, F1)
                    if "FAKE_INVOICES" in mechs and m >= start and rng.random() < 0.06:
                        n_dup += 1
                        add(facs[-1], min(m + 1, M - 1), num, po, debtors[j], m, day, due,
                            amt * rng.uniform(1.5, 25), desc)
                        open_inv.append((amt, 10_000))
            if "FAKE_INVOICES" in mechs and m >= start:
                for _ in range(max(1, int(counts.sum() * 0.15))):
                    j = int(np.argmax(size * rng.random(k)))  # tends to name big, credible customers
                    seq += 1
                    amt = float(size[j] * (rng.uniform(3, 15) if rng.random() < 0.5 else rng.lognormal(0, 0.3)))
                    n_fake += 1
                    add(facs[0], m, f"{bid}-{seq}", f"PO{int(rng.integers(1e5, 1e6))}", debtors[j], m,
                        int(rng.integers(1, 29)), 30, amt, f"{int(rng.integers(20, 900))} units {rng.choice(PRODUCTS)}")
                    open_inv.append((amt, 10_000))  # never paid
            if m % 3 == 2:
                outstanding_q[m // 3] = sum(a for a, p in open_inv if p > m)
        if n_fake or n_dup:
            planted.update(fake_invoices=n_fake, duplicate_invoices=n_dup)
        if n_dp:
            planted["double_pledged_invoices"] = n_dp
        kk = len(rows["invoice_id"])
        self.big["invoices"].append(dict(borrower_id=np.full(kk, bid), **{c: np.array(v) for c, v in rows.items()}))
        if pays:
            pm, pd_, pa_, pn = zip(*pays)
            kk = len(pm)
            names = np.array([self.ename(d) for d in pd_])
            if "NAME_TYPO" in benign:
                t = rng.random(kk) < 0.06
                names = np.where(t, np.char.replace(names, " ", "  ", count=1), names)
            self.big["payments"].append(dict(
                txn_id=self.txn_ids(kk), month=np.array(pm, np.int16), day=rng.integers(1, 29, kk).astype(np.int8),
                borrower_id=np.full(kk, bid), account_id=np.full(kk, facs[0] + "-COLL"), payer_id=np.array(pd_),
                payer_name=names, amount=np.round(np.array(pa_), 2), memo=np.char.add("REMIT ", np.array(pn)),
                ref=np.array(pn)))
        return coll, outstanding_q

    # ---------- quarterly financial statements ----------
    def financials(self, bid, btype, coll, bal_q, mechs, start, benign, disclosed, limit):
        rng = self.rng
        manip = "FIN_MANIPULATION" in mechs
        cov = 1.5
        for q in range(MONTHS // 3):
            c = coll[3 * q:3 * q + 3].sum()
            rev_true = c * (REV_FACTOR.get(btype, 1.0))
            lie = manip and 3 * q + 2 >= start
            revenue = rev_true * (1 + (rng.uniform(0.15, 0.4) if lie else rng.normal(0, 0.02)))
            cov = float(np.clip(cov * rng.lognormal(0, 0.09), 1.0, 2.4))  # honest firms can drift near the line too
            metric = float(rng.uniform(1.005, 1.045)) if lie else cov
            debt = 0.85 * bal_q[q] * 0.8 + (len(disclosed) * limit * 0.1)
            self.small["financials"].append(dict(
                borrower_id=bid, quarter=q, revenue_reported=round(float(revenue), 2),
                receivables_reported=round(float(bal_q[q]), 2),
                cash_reported=round(float(c * 0.15 * (1.25 if lie else 1.0)), 2),
                debt_reported=round(float(debt), 2), covenant_metric_reported=round(metric, 4),
                covenant_threshold=1.0))

    # ---------- simulated Setpoint PledgeCheck results (its four published checks) ----------
    def pledgecheck(self, bid, facs, mechs, start, dp_other):
        rng = self.rng
        if rng.random() >= 0.5:
            return
        other_enrolled = rng.random() < 0.6
        completeness_sees = rng.random() < 0.7
        for f in facs:
            for m in range(MONTHS):
                after = start is not None and m >= start
                uniq_fail = after and "DOUBLE_PLEDGE" in mechs and (len(facs) > 1 or other_enrolled)
                comp_fail = after and completeness_sees and (
                    "TAPE_DRESSUP" in mechs or ("FAKE_INVOICES" in mechs and m >= start + 2))
                self.small["pledgecheck"].append(dict(
                    borrower_id=bid, facility_id=f, month=m, enrolled=True,
                    uniqueness="FAIL" if uniq_fail else "PASS", data_integrity="PASS",
                    completeness="FAIL" if comp_fail else "PASS", single_record="PASS"))

    # ---------- run + write ----------
    def run(self):
        for i, p in enumerate(self.plan(), start=1):
            self.borrower(i, p)

    def write(self, out):
        os.makedirs(out, exist_ok=True)
        counts = {}
        for name, rows in self.small.items():
            tbl = pa.Table.from_pylist(rows) if rows else pa.table({})
            pq.write_table(tbl, os.path.join(out, f"{name}.parquet"))
            counts[name] = tbl.num_rows
        for name, chunks in self.big.items():
            if not chunks:
                continue
            cols = chunks[0].keys()
            tbl = pa.table({c: pa.array(np.concatenate([ch[c] for ch in chunks])) for c in cols})
            pq.write_table(tbl, os.path.join(out, f"{name}.parquet"), compression="zstd")
            counts[name] = tbl.num_rows
        with open(os.path.join(out, "labels.json"), "w") as f:
            json.dump(self.labels, f, indent=1)
        manifest = dict(SYNTHETIC="All data in this folder is synthetic. No real company, person or loan.",
                        seed=self.seed, borrowers=self.n, scale=self.scale, fraud_rate=self.fraud_rate,
                        months=MONTHS, rows=counts, generated=time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(os.path.join(out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
        return counts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--borrowers", type=int, default=120)
    ap.add_argument("--scale", type=float, default=1.0, help="multiplies assets and invoices per borrower")
    ap.add_argument("--fraud-rate", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/out/demo")
    a = ap.parse_args(argv)
    t0 = time.time()
    b = Book(a.seed, a.borrowers, a.scale, a.fraud_rate)
    b.run()
    counts = b.write(a.out)
    n_f = sum(1 for v in b.labels.values() if v["fraud"])
    print(f"wrote {a.out} in {time.time() - t0:.1f}s · {a.borrowers} borrowers ({n_f} with planted fraud)")
    for k, v in counts.items():
        print(f"  {k:14} {v:>10,}")


if __name__ == "__main__":
    main()
