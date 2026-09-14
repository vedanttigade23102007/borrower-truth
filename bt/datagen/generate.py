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
BIG = ("tape", "source_truth", "payments", "invoices", "outflows")
COMMERCIAL_AGENTS = ("(synthetic) Corporate Agents Inc, 100 Registry Plaza",
                     "(synthetic) Registered Agent Services LLC, 12 Filing Way",
                     "(synthetic) Statutory Agent Co, 7 Compliance Ct")
VARIANT_SHARE = 0.03  # of the book, for each of the two harder variants added in extras()
ELIGIBLE_SCORE = 600  # facility rule: a loan needs a credit score of 600+ at origination to count as collateral

# ---------- generator v3: honest auto loans calibrated on real public data (SEC Form ABS-EE) ----------
V3_TIERS, V3_TIER_P = ("subprime", "near-prime", "prime"), (0.6, 0.1, 0.3)  # warehouse auto borrowers skew subprime
V3_STATES = ("current", "30-59", "60-89", "90+", "charged_off", "paid_off")
BAND_EDGES, BAND_NAMES = (580, 620, 660, 720), ("<580", "580-619", "620-659", "660-719", "720+")
AGE_EDGES, AGE_NAMES = (12, 24), ("0-11m", "12-23m", "24m+")
CAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "calibration")
GEN_V3 = ("v3: honest auto loans drawn from, and moving month to month like, real public auto loans (SEC ABS-EE "
          "calibration); SEC filers (10-K, 8-K, XBRL revenue); public securitization pools; three harder variants "
          "(public-pool double pledge, self-funded payments, debt disclosed only to the SEC). Own random stream.")
SEC_SCHEMA = pa.schema([("borrower_id", pa.string()), ("form", pa.string()), ("filed_month", pa.int64()),
                        ("item", pa.string()), ("counterparty_entity_id", pa.string()), ("counterparty_name", pa.string()),
                        ("amount", pa.float64()), ("quarter", pa.int64()), ("note", pa.string())])


def load_calibration() -> dict:
    """Real monthly loan moves by credit band x loan age, real no-payment rates, real loan attributes."""
    js, sp = os.path.join(CAL_DIR, "absee_auto.json"), os.path.join(CAL_DIR, "absee_auto_sample.parquet")
    if not (os.path.exists(js) and os.path.exists(sp)):
        raise SystemExit("generator v3 needs data/calibration/ (python -m bt.sec.absee fetch, then "
                         "python -m bt.sec.calibrate), or pass --generator v2")
    cal = json.load(open(js))
    P = np.zeros((len(BAND_NAMES), len(AGE_NAMES), 4, len(V3_STATES)))
    for bi, b in enumerate(BAND_NAMES):
        for ai, a in enumerate(AGE_NAMES):
            for si, s in enumerate(V3_STATES[:4]):
                cell = None
                for src in (cal["transitions_band_age"].get(f"{b}|{a}", {}), cal["transitions"].get(f"band {b}", {}),
                            cal["transitions"]["all"]):
                    if s in src and src[s]["n"] >= 100:  # thin cells borrow the band's (or the whole book's) rates
                        cell = src[s]
                        break
                row = np.array([cell["p"][t] for t in V3_STATES]) if cell else np.eye(len(V3_STATES))[si]
                P[bi, ai, si] = row / row.sum()
    cum = P.cumsum(-1)
    cum[..., -1] = 1.0
    t = pq.read_table(sp).to_pydict()
    sample = {}
    for tier in V3_TIERS:
        idx = [i for i, x in enumerate(t["tier"]) if x == tier] or [i for i, x in enumerate(t["tier"]) if x == "subprime"]

        def col(k, d):
            vals = [t[k][i] if t[k][i] is not None else d for i in idx]
            return np.array(vals, dtype=object) if isinstance(d, str) else np.array(vals, dtype=float)
        rate = col("rate", 0.0)
        rate = np.clip(np.nan_to_num(np.where(rate > 1, rate / 100, rate)), 0.0, 0.36)  # a few servicers report percent
        sample[tier] = dict(orig_amt=np.maximum(col("orig_amt", 0.0), 1000.0), term=np.clip(col("term", 60.0), 12, 96),
                            rate=rate, make=col("make", ""), model=col("model", ""), model_year=col("model_year", 0.0),
                            score=col("score", 650.0), state=col("state", ""))
    return dict(cum=cum, sample=sample, skip={k: v["share"] for k, v in cal["current_no_payment"].items()})


class Book:
    def __init__(self, seed: int, n_borrowers: int, scale: float, fraud_rate: float, generator: str = "v3"):
        self.rng = np.random.default_rng(seed)
        # extras() draws from its own stream, after everything else: every table it doesn't touch is unchanged
        self.rng2 = np.random.default_rng([seed, 2026])
        # v3 extras (SEC filers, public pools, three variants) draw from a third stream
        self.rng3 = np.random.default_rng([seed, 2027])
        self.v3 = generator == "v3"
        self.cal = load_calibration() if self.v3 else None
        self._vin_score, self._v3_loans, self._fin_true = {}, {}, {}
        self._n_out = 0
        self.seed, self.n, self.scale, self.fraud_rate = seed, n_borrowers, scale, fraud_rate
        self.small = {k: [] for k in SMALL}
        self.big = {k: [] for k in BIG}
        if self.v3:
            self.small["sec_filings"] = []
            self.big["public_abs"] = []
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
        v3auto = self.v3 and btype == "auto_finance"  # consumer and real-estate books keep v2's assumed behaviour
        risk = RISK[btype]
        P = np.array([[1 - 0.03 * risk, 0.03 * risk, 0, 0, 0],
                      [0.50, 0, 0.50, 0, 0],
                      [0.30, 0, 0, 0.70, 0],
                      [0.10, 0, 0, 0.30, 0.60]])
        cum = P.cumsum(1)
        if v3auto:  # real public auto loans (SEC ABS-EE sample), see _v3_attrs
            orig, bal, info = self._v3_attrs(n)
        else:
            orig = rng.integers(-18, M - 3, n)
            bal = rng.lognormal(np.log(BAL[btype]), 0.45, n)
            info = None
        bal0 = bal.copy()
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
                if v3auto:  # measured monthly moves of real loans, by credit band and loan age
                    c3 = self.cal["cum"][info["band"][idx], np.searchsorted(AGE_EDGES, m - orig[idx], side="right"), cur[idx]]
                    nb[idx] = (r[:, None] < c3).argmax(1)
                else:
                    nb[idx] = (r[:, None] < cum[cur[idx]]).argmax(1)
            if v3auto:
                nb[act & (nb == 0) & (bal <= info["inst"] * 1.001)] = 5  # the last instalment pays it off
            pay = act & ((nb == 0) | (nb == 5))
            # realism: some current loans show no payment in a month (v2: ~1% assumed; v3: measured per lender tier)
            pay &= (~(act & (cur == 0) & (nb == 0) & (rng.random(n) < info["skip"])) if v3auto
                    else rng.random(n) >= 0.01)
            if defer and defer[0] <= m < defer[1]:
                dm = act & defer[2] & (cur == 0)
                nb[dm] = 0
                pay[dm] = False
            if v3auto:
                payoff = act & (nb == 5)
                nb = np.where(nb == 5, 0, nb).astype(np.int8)  # the payoff month is reported current; gone after
            true_b[m, act] = nb[act]
            balh[m, act] = bal[act]
            if v3auto:
                inst = np.minimum(info["inst"], bal)
                info["payoff_month"][payoff] = m
            else:
                inst = bal * 0.03
                payoff = pay & (rng.random(n) < 0.015)
            paid[m] = pay
            payamt[m] = np.where(payoff, bal, np.where(pay, inst, 0))
            bal = (np.where(pay & ~payoff, np.maximum(bal * (1 + info["rate"] / 12) - inst, 0), bal) if v3auto
                   else np.where(pay, bal * 0.975, bal))
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
            row = dict(
                month=mi.astype(np.int16), facility_id=np.full(len(mi), fac), borrower_id=np.full(len(mi), bid),
                asset_id=ids, vin=vins[ai], obligor_id=obligor[ai], balance=np.round(balh[mi, ai], 2),
                dpd_bucket_reported=rep[mi, ai], deferred_flag=deferred[mi, ai],
                eligible_reported=(rep[mi, ai] <= 1))
            if self.v3:  # loan attributes, as on a real tape (and in ABS-EE): what a no-VIN fingerprint uses
                row.update(self._tape_attrs(ai, orig, bal0, info))
            self.big["tape"].append(row)
            if info is not None and k == 0:
                info.update(tape_chunk=len(self.big["tape"]) - 1, tape_mi=mi, tape_ai=ai)

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
        if info is not None:  # what the v3 extras (public pools, variants) need to know about these loans
            info.update(pay_chunk=len(self.big["payments"]) - 1, asset_ids=asset_ids, vins=vins, obligor=obligor,
                        oname=oname, orig=orig, true_b=true_b, facs=facs, n=n)
            self._v3_loans[bid] = info
            self._vin_score.update(zip(vins.tolist(), info["score"].tolist()))
        coll = np.bincount(mi, weights=payamt[mi, ai], minlength=M)
        bal_q = np.array([(balh[3 * q + 2] * (rep[3 * q + 2] >= 0)).sum() for q in range(M // 3)])
        return coll, bal_q

    def _v3_attrs(self, n):
        """n loans drawn from real public auto loans of one lender tier: amount, term, rate, vehicle, state, score."""
        rng, cal = self.rng, self.cal
        tier = str(rng.choice(V3_TIERS, p=V3_TIER_P))
        S = cal["sample"][tier]
        pick = rng.integers(0, len(S["score"]), n)
        a = {k: v[pick] for k, v in S.items()}
        orig = rng.integers(-18, MONTHS - 3, n)
        # small variation, so a drawn real profile isn't reused exactly (real fingerprints are 99.99% unique)
        amt = np.round(a["orig_amt"] * (1 + rng.uniform(-0.02, 0.02, n)), 2)
        term, rate = a["term"].astype(int), a["rate"]
        r_m = rate / 12
        with np.errstate(divide="ignore", invalid="ignore"):  # zero-rate loans take the amt / term branch
            inst = np.where(r_m > 0, amt * r_m / (1 - (1 + r_m) ** -term), amt / term)
        age0 = np.maximum(0, -orig)
        grow = (1 + r_m) ** age0
        bal = np.where(r_m > 0, amt * grow - inst * (grow - 1) / np.where(r_m > 0, r_m, 1.0), amt - inst * age0)
        bal = np.maximum(bal, inst)  # balance at month 0 for loans already seasoned by then
        score = a["score"].astype(int)
        info = dict(tier=tier, attrs=a, amt=amt, term=term, rate=rate, inst=inst, score=score,
                    band=np.searchsorted(BAND_EDGES, score, side="right"), skip=float(cal["skip"].get(tier, 0.07)),
                    payoff_month=np.full(n, 10_000))
        return orig, bal, info

    def _tape_attrs(self, ai, orig, bal0, info):
        k = len(ai)
        if info is None:  # one tape schema per book; non-auto loans carry what is known about them
            return dict(orig_month=orig[ai].astype(np.int16), orig_amount=np.round(bal0[ai], 2),
                        rate=np.full(k, np.nan), term=np.zeros(k, np.int16), make=np.full(k, "", dtype=object),
                        model=np.full(k, "", dtype=object), model_year=np.zeros(k, np.int16),
                        obligor_state=np.full(k, "", dtype=object))
        a = info["attrs"]
        return dict(orig_month=orig[ai].astype(np.int16), orig_amount=np.round(info["amt"][ai], 2),
                    rate=np.round(info["rate"][ai], 4), term=info["term"][ai].astype(np.int16),
                    make=a["make"][ai], model=a["model"][ai], model_year=a["model_year"][ai].astype(np.int16),
                    obligor_state=a["state"][ai])

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
            self._fin_true[(bid, q)] = float(rev_true)  # what an audited SEC filing would show
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
        self.extras()
        if self.v3:
            self.extras_v3()

    # ---------- extras: contact details, operating-account outflows, two harder fraud variants ----------
    def _person2(self) -> str:
        self._n_person += 1
        pid = f"P{self._n_person:05d}"
        self.small["persons"].append(dict(person_id=pid, name=f"{self.rng2.choice(FIRST)} {self.rng2.choice(LAST)}"))
        return pid

    def _address2(self) -> str:
        self._n_addr += 1
        return f"{int(self.rng2.integers(10, 9999))} {self.rng2.choice(STREETS)}, Suite {self._n_addr}"

    def _phone2(self) -> str:
        return f"555-{int(self.rng2.integers(100, 1000))}-{int(self.rng2.integers(1000, 10000))}"

    def _name2(self, words) -> str:
        for _ in range(1000):
            n = f"{self.rng2.choice(W1)} {self.rng2.choice(words)} {self.rng2.choice(['LLC', 'Inc'])}"
            if n not in self._names:
                self._names.add(n)
                return n
        raise RuntimeError("ran out of company names")

    def _entity2(self, kind, name, officer, address, formed, ops, state, phone, agent) -> str:
        eid = self.entity(kind, name, officer, address, formed, ops, state=state)
        self.small["entities"][-1].update(phone=phone, registered_agent=agent)
        return eid

    def _out(self, bid, account, rows):
        """rows: (month, day, payee_id, payee_name, amount, memo) -> the borrower's operating-account outflows."""
        if not rows:
            return
        m, d, pid, pn, amt, memo = zip(*rows)
        k = len(rows)
        ids = np.char.add("O", np.char.zfill((np.arange(k) + self._n_out).astype(str), 9))
        self._n_out += k
        self.big["outflows"].append(dict(
            txn_id=ids, month=np.array(m, np.int16), day=np.array(d, np.int8), borrower_id=np.full(k, bid),
            account_id=np.full(k, account), payee_id=np.array(pid), payee_name=np.array(pn),
            amount=np.round(np.array(amt, float), 2), memo=np.array(memo)))

    def _pay(self, bid, account, rows):
        """rows: (month, day, payer_id, payer_name, amount) -> extra 'customer remittance' inflows."""
        m, d, pid, pn, amt = zip(*rows)
        k = len(rows)
        self.big["payments"].append(dict(
            txn_id=self.txn_ids(k), month=np.array(m, np.int16), day=np.array(d, np.int8), borrower_id=np.full(k, bid),
            account_id=np.full(k, account), payer_id=np.array(pid), payer_name=np.array(pn),
            amount=np.round(np.array(amt, float), 2), memo=np.full(k, "customer remittance"), ref=np.full(k, "")))

    def extras(self):
        r2 = self.rng2
        M = MONTHS
        ents = self.small["entities"]
        pname = {p["person_id"]: p["name"] for p in self.small["persons"]}
        brow = {b["borrower_id"]: b for b in self.small["borrowers"]}
        ent_of = {e["entity_id"]: e for e in ents}
        first_fac = {}
        for f in self.small["facilities"]:
            first_fac.setdefault(f["borrower_id"], f["facility_id"])
        pb = np.concatenate([c["borrower_id"] for c in self.big["payments"]])
        ub, pinv = np.unique(pb, return_inverse=True)
        paid_by = dict(zip(ub.tolist(), np.bincount(pinv, weights=np.concatenate([c["amount"] for c in self.big["payments"]]))))
        avg_coll = {b: max(float(paid_by.get(b, 0.0)) / M, 20_000.0) for b in brow}

        # 1. phone number and registered agent for every company in the registry
        for e in ents:
            e["phone"] = self._phone2()
            own = e["officer_person_id"] and r2.random() < 0.3
            e["registered_agent"] = (f"{pname[e['officer_person_id']]}, {e['address']}" if own
                                     else str(r2.choice(COMMERCIAL_AGENTS)))
        for b, v in self.labels.items():  # fraud shells often keep the borrower's phone or owner-as-agent
            be = ent_of[brow[b]["entity_id"]]
            for s in v["planted"].get("shells", []):
                if r2.random() < 0.6:
                    ent_of[s]["phone"] = be["phone"]
                if r2.random() < 0.5:
                    ent_of[s]["registered_agent"] = be["registered_agent"]

        honest = [b for b, v in sorted(self.labels.items()) if not v["fraud"]]
        k = max(1, round(self.n * VARIANT_SHARE))
        picks = list(r2.choice(honest, size=min(2 * k, len(honest)), replace=False))
        nominee, round_trip = picks[:k], picks[k:]
        rest = [b for b in honest if b not in picks]

        # 2. honest look-alikes for the new links: a neighbour in a shared virtual office (same phone), and an
        #    unrelated operating business that uses the owner as its registered agent
        for b in rest:
            be = ent_of[brow[b]["entity_id"]]
            if r2.random() < 0.05:
                self._entity2("company", self._name2(["Consulting", "Logistics", "Services", "Staffing"]),
                              self._person2(), self._address2(), int(r2.integers(-200, -40)), True, be["state"],
                              be["phone"], str(r2.choice(COMMERCIAL_AGENTS)))
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["VIRTUAL_OFFICE"])
            if r2.random() < 0.03:
                be["registered_agent"] = f"{pname[be['officer_person_id']]}, {be['address']}"
                self._entity2("company", self._name2(["Bakery", "Studio", "Landscaping", "Dental"]),
                              self._person2(), self._address2(), int(r2.integers(-200, -40)), True, be["state"],
                              self._phone2(), be["registered_agent"])
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["OWNER_IS_AGENT_ELSEWHERE"])

        # 3. every borrower's operating account: payroll, rent, vendors, disclosed debt service
        debt_lenders = {}
        for d in self.small["disclosures"]:
            if d["kind"] == "debt":
                debt_lenders.setdefault(d["borrower_id"], []).append(d["counterparty_entity_id"])
        customers = {}
        for c in self.big["invoices"]:
            for b, dn, did in zip(c["borrower_id"], c["debtor_name"], c["debtor_id"]):
                customers.setdefault(str(b), {})[str(did)] = str(dn)
        for b in sorted(brow):
            acct, size = first_fac[b] + "-OPER", avg_coll[b]
            landlord = f"(synthetic) {r2.choice(W1)} Property Management LLC"
            two_way = []
            if b in customers and r2.random() < 0.25:  # honest: a customer that is also a supplier
                ids = sorted(customers[b])
                two_way = list(r2.choice(ids, size=min(2, len(ids)), replace=False))
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["TWO_WAY_TRADE"])
            rows = []
            for m in range(M):
                for _ in range(2):
                    rows.append((m, int(r2.integers(1, 29)), "PAYROLL", "(synthetic) Payroll Services LLC",
                                 size * r2.uniform(0.04, 0.08), "payroll"))
                rows.append((m, 1, "RENT", landlord, size * 0.02, "rent"))
                for _ in range(int(r2.poisson(3))):
                    v = str(r2.choice(self.debtors))
                    rows.append((m, int(r2.integers(1, 29)), v, self.ename(v), size * r2.uniform(0.005, 0.03), "vendor payment"))
                for L in debt_lenders.get(b, []):
                    rows.append((m, 15, L, self.ename(L), size * 0.03, "debt service"))
                for did in two_way:
                    rows.append((m, int(r2.integers(1, 29)), did, customers[b][did], size * r2.uniform(0.005, 0.04),
                                 "vendor payment"))
            self._out(b, acct, rows)

        # 4a. nominee shell: registered to someone else at another address, but it has the borrower's phone
        #     (and the owner as registered agent when the owner acts as agent), and it pays the borrower as a "customer"
        for b in nominee:
            be, start = ent_of[brow[b]["entity_id"]], int(r2.integers(6, 17))
            agent = be["registered_agent"] if be["registered_agent"].startswith(pname[be["officer_person_id"]]) \
                else str(r2.choice(COMMERCIAL_AGENTS))
            eid = self._entity2("company", self._name2(["Customer Collections", "Trade Services", "Receivables Co"]),
                                self._person2(), self._address2(), start - int(r2.integers(1, 5)), False, be["state"],
                                be["phone"], agent)
            rows = [(m, int(r2.integers(1, 29)), eid, self.ename(eid), avg_coll[b] * r2.uniform(0.04, 0.12))
                    for m in range(start, M) for _ in range(int(r2.integers(1, 4)))]
            self._pay(b, first_fac[b] + "-COLL", rows)
            self.labels[b].update(fraud=True, pattern="nominee_shell", start_month=start,
                                  mechanisms=sorted(["DISGUISED_RECEIPTS", "RELATED_SHELLS"]),
                                  planted=dict(self.labels[b]["planted"], nominee_shell=eid))

        # 4b. round trip through a legitimate-looking middleman: out of the operating account, back in days later
        #     as a "customer" payment of almost the same amount
        for b in round_trip:
            be, start = ent_of[brow[b]["entity_id"]], int(r2.integers(6, 17))
            eid = self._entity2("company", self._name2(["Industrial Supply", "Wholesale", "Distributors"]),
                                self._person2(), self._address2(), int(r2.integers(-200, -60)), True,
                                str(r2.choice(STATES)), self._phone2(), str(r2.choice(COMMERCIAL_AGENTS)))
            outs, ins = [], []
            for m in range(start, M - 1):
                for _ in range(int(r2.integers(1, 3))):
                    amt, d1 = avg_coll[b] * r2.uniform(0.05, 0.12), int(r2.integers(1, 21))
                    back = m * 30 + d1 + int(r2.integers(3, 21))
                    outs.append((m, d1, eid, self.ename(eid), amt, "vendor payment"))
                    ins.append((min(back // 30, M - 1), min(max(back % 30, 1), 28), eid, self.ename(eid),
                                amt * r2.uniform(0.985, 0.999)))
            self._out(b, first_fac[b] + "-OPER", outs)
            self._pay(b, first_fac[b] + "-COLL", ins)
            self.labels[b].update(fraud=True, pattern="round_trip", start_month=start,
                                  mechanisms=["DISGUISED_RECEIPTS"],
                                  planted=dict(self.labels[b]["planted"], round_trip_via=eid))

        # 5. credit score at origination on every tape row. It should never change. Dress-up borrowers rewrite
        #    some sub-600 scores to just over the eligibility line (Tricolor, as alleged: ineligible collateral made
        #    to "meet lender requirements"); honest servicers occasionally correct a score once.
        dress = {b for b, v in self.labels.items() if "TAPE_DRESSUP" in v["mechanisms"]}
        scores, cheat, fix, n_cheat = {}, {}, {}, {}
        for ch in self.big["tape"]:
            b = str(ch["borrower_id"][0])
            u, inv = np.unique(ch["vin"], return_inverse=True)
            new = [v for v in u if v not in scores]
            for v, x in zip(new, np.clip(r2.normal(680, 55, len(new)), 480, 850).astype(int)):
                x = self._vin_score.get(v, x)  # v3 auto loans carry a real credit score from the SEC sample
                scores[v] = int(x)
                if b in dress and x < ELIGIBLE_SCORE and r2.random() < 0.6:
                    cheat[v] = (self.labels[b]["start_month"], int(r2.integers(ELIGIBLE_SCORE, ELIGIBLE_SCORE + 13)))
                    n_cheat[b] = n_cheat.get(b, 0) + 1
                elif r2.random() < (0.0 if self.v3 else 0.003):  # real servicers: 0 of 774,975 scores ever changed
                    fix[v] = (int(r2.integers(1, M)), int(r2.choice([-1, 1]) * r2.integers(5, 41)))
            base = np.array([scores[v] for v in u])
            c_m = np.array([cheat.get(v, (10_000, 0))[0] for v in u])[inv]
            c_v = np.array([cheat.get(v, (0, 0))[1] for v in u])[inv]
            f_m = np.array([fix.get(v, (10_000, 0))[0] for v in u])[inv]
            f_d = np.array([fix.get(v, (0, 0))[1] for v in u])[inv]
            month = ch["month"].astype(int)
            rep = base[inv] + np.where(month >= f_m, f_d, 0)
            ch["credit_score"] = np.where(month >= c_m, c_v, rep).astype(np.int16)
        for b in dress:
            self.labels[b]["planted"]["rewritten_scores"] = n_cheat.get(b, 0)

    # ---------- v3 extras: SEC filers, public securitization pools, three harder variants ----------
    def _person3(self) -> str:
        self._n_person += 1
        pid = f"P{self._n_person:05d}"
        self.small["persons"].append(dict(person_id=pid, name=f"{self.rng3.choice(FIRST)} {self.rng3.choice(LAST)}"))
        return pid

    def _address3(self) -> str:
        self._n_addr += 1
        return f"{int(self.rng3.integers(10, 9999))} {self.rng3.choice(STREETS)}, Suite {self._n_addr}"

    def _phone3(self) -> str:
        return f"555-{int(self.rng3.integers(100, 1000))}-{int(self.rng3.integers(1000, 10000))}"

    def _name3(self, words) -> str:
        for _ in range(1000):
            n = f"{self.rng3.choice(W1)} {self.rng3.choice(words)} {self.rng3.choice(['LLC', 'Inc'])}"
            if n not in self._names:
                self._names.add(n)
                return n
        raise RuntimeError("ran out of company names")

    def _filing(self, b, form, month, item, cp=None, amount=None, quarter=None, note=""):
        self.small["sec_filings"].append(dict(
            borrower_id=b, form=form, filed_month=int(month), item=item, counterparty_entity_id=cp,
            counterparty_name=(("Wells Fargo Bank, N.A." if cp == self.wf else self.ename(cp)) if cp else None),
            amount=None if amount is None else round(float(amount), 2),
            quarter=None if quarter is None else int(quarter), note=note))

    def _pool(self, pool_id, issuer, months, fp, loan_ids):
        """One row per loan per month, like a Form ABS-EE file: no VIN, no borrower identity."""
        k = len(loan_ids)
        for m in months:
            self.big["public_abs"].append(dict(
                pool_id=np.full(k, pool_id, dtype=object), issuer_borrower_id=np.full(k, issuer, dtype=object),
                month=np.full(k, m, np.int16), pool_loan_id=np.asarray(loan_ids, dtype=object),
                orig_month=np.asarray(fp["orig_month"]).astype(np.int16), orig_amount=np.asarray(fp["orig_amount"], float),
                rate=np.asarray(fp["rate"], float), term=np.asarray(fp["term"]).astype(np.int16),
                make=np.asarray(fp["make"], dtype=object), model=np.asarray(fp["model"], dtype=object),
                model_year=np.asarray(fp["model_year"]).astype(np.int16),
                obligor_state=np.asarray(fp["obligor_state"], dtype=object),
                credit_score=np.asarray(fp["credit_score"]).astype(np.int16),
                dpd_bucket=(self.rng3.random(k) < 0.07).astype(np.int8)))

    def _fp_tape(self, info, ai):
        """The public fingerprint of loans already on the Wells Fargo tape."""
        a = info["attrs"]
        return dict(orig_month=info["orig"][ai], orig_amount=np.round(info["amt"][ai], 2), rate=np.round(info["rate"][ai], 4),
                    term=info["term"][ai], make=a["make"][ai], model=a["model"][ai], model_year=a["model_year"][ai],
                    obligor_state=a["state"][ai], credit_score=np.array([self._vin_score[v] for v in info["vins"][ai]]))

    def _fp_new(self, tier, k, t_issue):
        """Other loans the lender sold straight into its public trust, drawn from real public loans."""
        r3, S = self.rng3, self.cal["sample"][tier]
        pick = r3.integers(0, len(S["score"]), k)
        return dict(orig_month=r3.integers(t_issue - 24, t_issue, k),
                    orig_amount=np.round(S["orig_amt"][pick] * (1 + r3.uniform(-0.02, 0.02, k)), 2),
                    rate=np.round(S["rate"][pick], 4), term=S["term"][pick].astype(int), make=S["make"][pick],
                    model=S["model"][pick], model_year=S["model_year"][pick], obligor_state=S["state"][pick],
                    credit_score=S["score"][pick].astype(int))

    def extras_v3(self):
        r3, M = self.rng3, MONTHS
        brow = {b["borrower_id"]: b for b in self.small["borrowers"]}
        ent_of = {e["entity_id"]: e for e in self.small["entities"]}
        first_fac = {}
        for f in self.small["facilities"]:
            first_fac.setdefault(f["borrower_id"], f["facility_id"])
        debt = {}
        for d in self.small["disclosures"]:
            if d["kind"] == "debt":
                debt.setdefault(d["borrower_id"], []).append(d["counterparty_entity_id"])
        fin = {(f["borrower_id"], f["quarter"]): f for f in self.small["financials"]}

        # 1. three harder variants, each converted from an honest borrower; each needs one of the SEC-data checks
        honest = [b for b, v in sorted(self.labels.items()) if not v["fraud"]]
        k = max(1, round(self.n * VARIANT_SHARE))
        auto = [b for b in honest if b in self._v3_loans]
        pool_dp = [str(x) for x in r3.choice(auto, size=min(k, len(auto)), replace=False)] if auto else []
        auto = [b for b in auto if b not in pool_dp]
        paid_look = [str(x) for x in r3.choice(auto, size=min(k, len(auto)), replace=False)] if auto else []
        rest = [b for b in honest if b not in pool_dp and b not in paid_look]
        filer_hd = [str(x) for x in r3.choice(rest, size=min(k, len(rest)), replace=False)] if rest else []
        filers = sorted({b for b in sorted(brow) if r3.random() < 0.25} | set(filer_hd))
        issuers = sorted({b for b in sorted(self._v3_loans) if r3.random() < 0.4} | set(pool_dp))

        # 2. SEC filers (the borrower or its parent is public): 10-K debt footnote and Exhibit 21, 8-K items, XBRL revenue
        for b in filers:
            lab, owner = self.labels[b], brow[b]["owner_person_id"]
            be = ent_of[brow[b]["entity_id"]]
            start = lab["start_month"]
            hidden = lab["planted"].get("hidden_lender") if "HIDDEN_DEBT" in lab["mechanisms"] else None
            tell = hidden is not None and r3.random() < 0.5  # hidden from the bank, not from its auditors
            if b in filer_hd:  # variant: an unsecured loan (no lien filed) that only the SEC filings mention
                start = int(r3.integers(6, 17))
                hidden = str(r3.choice([l for l in self.lenders if l not in debt.get(b, [])]))
                tell = True
                self._out(b, first_fac[b] + "-OPER", [(m, 15, hidden, self.ename(hidden), max(1.0, 2e4 * self.scale),
                                                       "debt service") for m in range(start + 1, M)])
                self.labels[b].update(fraud=True, pattern="filer_hidden_debt", start_month=start,
                                      mechanisms=["HIDDEN_DEBT"],
                                      planted=dict(lab["planted"], hidden_lender=hidden, revealed_by="8-K Item 2.03 and 10-K"))
                lab = self.labels[b]
            if tell:
                self._filing(b, "8-K", start, "2.03", hidden, note="entry into a material direct financial obligation")
            subs = []
            for _ in range(int(r3.integers(0, 3))):  # operating subsidiaries the bank knows about
                s = self._entity2("company", self._name3(["Funding", "Servicing", "Auto Sales", "Recovery"]), owner,
                                  self._address3(), int(r3.integers(-150, -24)), True, be["state"], self._phone3(),
                                  str(r3.choice(COMMERCIAL_AGENTS)))
                self.small["disclosures"].append(dict(borrower_id=b, kind="related_party", counterparty_entity_id=s,
                                                      start_month=0, note="subsidiary (listed in 10-K Exhibit 21)"))
                subs.append(s)
            if not lab["fraud"] and r3.random() < 0.15:  # honest look-alike: a dormant subsidiary nobody mentioned
                subs.append(self._entity2("company", self._name3(["Insurance Services", "Title", "Leasing"]),
                                          self._person3(), self._address3(), int(r3.integers(-200, -60)), False,
                                          be["state"], self._phone3(), str(r3.choice(COMMERCIAL_AGENTS))))
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["DORMANT_SUBSIDIARY"])
            subs += [s for s in lab["planted"].get("shells", []) if r3.random() < 0.4]  # public list, hidden from the bank
            for fm in (2, 14):  # annual 10-K
                for L in [self.wf] + debt.get(b, []):
                    self._filing(b, "10-K", fm, "debt", L, note="debt footnote")
                if tell and fm >= start:
                    self._filing(b, "10-K", fm, "debt", hidden, note="debt footnote")
                for s in subs:
                    self._filing(b, "10-K", fm, "subsidiary", s, note="Exhibit 21")
            if not self.labels[b]["fraud"] and r3.random() < 0.3:  # honest: new debt announced, told to the bank next month
                L = str(r3.choice([l for l in self.lenders if l not in debt.get(b, [])]))
                t = int(r3.integers(3, M - 3))
                self._filing(b, "8-K", t, "2.03", L, note="new unsecured term loan")
                if t < 14:
                    self._filing(b, "10-K", 14, "debt", L, note="debt footnote")
                self.small["disclosures"].append(dict(borrower_id=b, kind="debt", counterparty_entity_id=L, start_month=t + 1,
                                                      note="new unsecured term loan, disclosed after closing"))
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["NEW_DEBT_8K"])
            if debt.get(b) and r3.random() < 0.03:  # a lender sped up repayment: a credit event, not fraud
                self._filing(b, "8-K", int(r3.integers(2, M)), "2.04", debt[b][0], note="acceleration of an obligation")
                self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["DEBT_ACCELERATION"])
            lie_sec = "FIN_MANIPULATION" in self.labels[b]["mechanisms"] and r3.random() < 0.6
            for q in range(M // 3):
                f = fin.get((b, q))
                if not f:
                    continue
                lying = lie_sec and 3 * q + 2 >= self.labels[b]["start_month"]
                amt = self._fin_true[(b, q)] * (1 + r3.normal(0, 0.004)) if lying else f["revenue_reported"]
                self._filing(b, "10-K" if q % 4 == 3 else "10-Q", min(3 * q + 3, M - 1), "revenue", amount=amt,
                             quarter=q, note="XBRL Revenues")
            if lie_sec:
                self.labels[b]["planted"]["revenue_differs_from_sec_filing"] = True

        # 3. public securitization pools: the lender's own trust reports every loan monthly (Form ABS-EE)
        for b in issuers:
            info, lab = self._v3_loans[b], self.labels[b]
            t_issue = int(r3.integers(0, 12))
            pool_id = f"SYN-ABS-{b}"
            kk = int(max(40, info["n"] * r3.uniform(0.8, 1.5)))
            fp = self._fp_new(info["tier"], kk, t_issue)
            self._pool(pool_id, b, range(t_issue, M), fp, np.char.add(f"{pool_id}-", np.char.zfill(np.arange(kk).astype(str), 6)))
            if b in pool_dp or "DOUBLE_PLEDGE" in lab["mechanisms"]:
                start = int(r3.integers(6, 17)) if b in pool_dp else lab["start_month"]
                at_start = np.unique(info["tape_ai"][info["tape_mi"] == start])
                sel = at_start[r3.random(len(at_start)) < 0.22]
                if len(sel) < 3:
                    continue
                self._pool(pool_id, b, range(start, M), self._fp_tape(info, sel),
                           np.char.add(f"{pool_id}-X", np.char.zfill(np.arange(len(sel)).astype(str), 5)))
                pc = self.big["payments"][info["pay_chunk"]]  # the trust, not Wells Fargo, now collects on these loans
                keep = ~(np.isin(pc["ref"], info["asset_ids"][sel]) & (pc["month"] >= start))
                for c in list(pc):
                    pc[c] = pc[c][keep]
                planted = dict(lab["planted"], public_pool=pool_id, public_pool_overlap_loans=int(len(sel)))
                if b in pool_dp:
                    self.labels[b].update(fraud=True, pattern="public_pool_double_pledge", start_month=start,
                                          mechanisms=["DOUBLE_PLEDGE"], planted=planted)
                else:
                    self.labels[b]["planted"] = planted
            elif r3.random() < 0.15:  # honest: loans sold into the trust leave the tape that same month
                po = info["payoff_month"]
                cand = np.nonzero((po >= 3) & (po <= M - 3))[0]
                if len(cand):
                    for j, a_i in enumerate(r3.choice(cand, size=min(8, len(cand)), replace=False)):
                        self._pool(pool_id, b, range(int(po[a_i]), min(int(po[a_i]) + 6, M)),
                                   self._fp_tape(info, np.array([a_i])), np.array([f"{pool_id}-T{j:03d}"]))
                    self.labels[b]["benign"] = sorted(self.labels[b]["benign"] + ["TAKEOUT_TIMING"])

        # 4. self-funded payments: 60+ day loans reported current, and paid by the borrower itself, so the tape and the
        #    collection account agree. Only the shape of the tape (late loans never get later) and a servicer pull show it.
        for b in paid_look:
            info = self._v3_loans[b]
            start = int(r3.integers(6, 17))
            tc = self.big["tape"][info["tape_chunk"]]
            mi, ai = info["tape_mi"], info["tape_ai"]
            tb = info["true_b"][mi, ai]
            sel = (mi >= start) & (tb >= 2) & (tb <= 3) & (r3.random(info["n"]) < 0.9)[ai]
            kk = int(sel.sum())
            if kk < 3:
                continue
            tc["dpd_bucket_reported"][sel] = 0
            tc["eligible_reported"][sel] = True
            self.big["payments"].append(dict(
                txn_id=self.txn_ids(kk), month=mi[sel].astype(np.int16), day=r3.integers(1, 29, kk).astype(np.int8),
                borrower_id=np.full(kk, b), account_id=np.full(kk, info["facs"][0] + "-COLL"),
                payer_id=info["obligor"][ai[sel]], payer_name=info["oname"][ai[sel]],
                amount=np.round(info["inst"][ai[sel]], 2), memo=np.full(kk, "loan payment"), ref=info["asset_ids"][ai[sel]]))
            per_m = np.bincount(mi[sel], weights=info["inst"][ai[sel]], minlength=M)
            proc = f"(synthetic) {r3.choice(W1)} Payment Solutions LLC"
            self._out(b, info["facs"][0] + "-OPER", [(m, 3, "PAYPROC", proc, float(per_m[m]), "payment processing")
                                                      for m in range(M) if per_m[m] > 0])
            self.labels[b].update(fraud=True, pattern="paid_to_look_current", start_month=start, mechanisms=["TAPE_DRESSUP"],
                                  planted=dict(self.labels[b]["planted"], dressed_asset_months=kk, self_funded_payments=kk))

    def write(self, out):
        os.makedirs(out, exist_ok=True)
        counts = {}
        for name, rows in self.small.items():
            if name == "sec_filings":
                tbl = pa.Table.from_pylist(rows, schema=SEC_SCHEMA)
            else:
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
                        generator=GEN_V3 if self.v3 else
                        "v2: + contact details, operating-account outflows, nominee-shell and "
                        "round-trip variants (own random stream; earlier tables unchanged)",
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
    ap.add_argument("--generator", choices=["v3", "v2"], default="v3",
                    help="v3: calibrated on real SEC data (default); v2: rebuilds older books exactly")
    a = ap.parse_args(argv)
    t0 = time.time()
    b = Book(a.seed, a.borrowers, a.scale, a.fraud_rate, a.generator)
    b.run()
    counts = b.write(a.out)
    n_f = sum(1 for v in b.labels.values() if v["fraud"])
    print(f"wrote {a.out} in {time.time() - t0:.1f}s · {a.borrowers} borrowers ({n_f} with planted fraud)")
    for k, v in counts.items():
        print(f"  {k:14} {v:>10,}")


if __name__ == "__main__":
    main()
