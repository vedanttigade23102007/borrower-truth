"""Blind red team (RED-TEAM-PLAN.md): the sealed briefing, the leak scan, planting the attacks, scoring once.

    uv run python -m bt.eval.redteam briefing --out <dir>        # sealed briefing folder + zip, leak-scanned
    uv run python -m bt.eval.redteam scan <folder or zip>        # our internal names in anything the red team sees or sends
    uv run python -m bt.eval.redteam freeze --zip <briefing zip> # record the rule version before the tag `redteam-frozen`
    uv run python -m bt.eval.redteam plant --attacks attacks.zip --i-have-read-them
    uv run python -m bt.eval.redteam score

Honesty rules:
- The rules are frozen at the git tag `redteam-frozen`, before the red team starts. `plant` and `score` refuse to run
  if the rule version differs from proof/redteam/FROZEN.json.
- A person reads every attack script before `plant` runs it. A crash may be fixed; what an attack does may not; every
  fix is logged in proof/REDTEAM.md.
- An attack that breaks the rules of engagement (levers, start month, the data's layout or quality) is reverted and
  reported, never repaired. One that gains less than 5% of the credit limit is scored apart as "too small to matter".
- Copy A (the books as generated) is the fresh held-out run; copy B adds the attacks. Both are scored once.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

import duckdb
import numpy as np
import pyarrow.parquet as pq

from bt.pipeline import dq, record

ROOT = record.ROOT
BRIEFING_SRC = os.path.join(ROOT, "redteam", "briefing")
ALLEGATIONS = ("doj-first-brands.txt", "doj-tricolor.txt", "sec-tricolor-2026-77.txt")
FROZEN = os.path.join(ROOT, "proof", "redteam", "FROZEN.json")
SAMPLE_SEED, SAMPLE_BORROWERS, SAMPLE_SCALE = 913, 40, 0.5  # never used for anything else
FRESH_SEEDS = (501, 502, 503, 504, 505)
DEV_SEEDS = (7, 101, 102, 103, 104, 105)
PER_BOOK = 2  # each attack is planted into this many honest borrowers per book
SIZE_FLOOR = 0.05  # of the borrower's facility_limit (decided by Vedant, 1 Oct 2026)
LAST_START = 18
MONTHS = 24


# ---------- the leak scan ----------
def forbidden_terms() -> set[str]:
    """Words that would tell the red team how the bank checks: our signal and finding names, the generator's
    fraud catalogue and look-alikes, the check names, and the product's own name."""
    from bt.combiner.combine import MECHANISM_OF
    from bt.datagen.generate import BENIGN, FRAUD_MECHS, PATTERNS
    terms = set(MECHANISM_OF) | set(MECHANISM_OF.values()) | set(FRAUD_MECHS) | set(PATTERNS) | set(BENIGN)
    terms |= {"public_pool_double_pledge", "paid_to_look_current", "filer_hidden_debt", "nominee_shell", "round_trip",
              "DORMANT_SUBSIDIARY", "NEW_DEBT_8K", "DEBT_ACCELERATION", "TAKEOUT_TIMING", "LIKELY_FRAUD",
              "NEEDS_MORE_EVIDENCE", "Borrower Truth", "borrower-truth", "borrower_truth", "Collateral integrity",
              "Tape vs source", "Cash provenance", "Invoice authenticity", "Hidden-debt finder", "Relationship mapper",
              "Financial consistency", "combiner", "worth a look", "redteam-frozen", "vercel"}
    return terms


def threshold_numbers() -> set[str]:
    """Module-level numeric constants in the checks: if one shows up in a briefing text, a person looks at it."""
    nums = set()
    for path in glob.glob(os.path.join(ROOT, "bt", "systems", "*.py")) + [os.path.join(ROOT, "bt", "combiner", "combine.py")]:
        for m in re.finditer(r"^[A-Z_]+\s*=\s*([0-9]+\.?[0-9]*)\b", open(path).read(), re.M):
            if m.group(1) not in {"0", "1", "0.0", "1.0"}:
                nums.add(m.group(1))
    return nums


def _term_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.I)


SYSTEM_IDS = [f"S{i}" for i in range(1, 8)]


def scan(path: str) -> dict:
    """Search every text file and every text cell of every parquet file for the forbidden terms. Text files are also
    searched for S1-S7 and for the checks' numeric constants (listed for a person to judge, not failed)."""
    tmp = None
    if path.endswith(".zip"):
        tmp = tempfile.mkdtemp()
        zipfile.ZipFile(path).extractall(tmp)
        path = tmp
    terms = [(t, _term_re(t)) for t in sorted(forbidden_terms())]
    ids = [(t, _term_re(t)) for t in SYSTEM_IDS]
    nums = [(n, _term_re(n)) for n in sorted(threshold_numbers())]
    hits, numbers, files = [], [], 0
    for f in sorted(glob.glob(os.path.join(path, "**", "*"), recursive=True)):
        rel = os.path.relpath(f, path)
        if os.path.isdir(f) or "__pycache__" in rel:
            continue
        files += 1
        if f.endswith(".parquet"):
            t = pq.read_table(f)
            for col in t.column_names:
                if str(t.schema.field(col).type) not in ("string", "large_string"):
                    continue
                for v in set(x for x in t.column(col).to_pylist() if x):
                    for term, rx in terms:
                        if rx.search(v):
                            hits.append(dict(file=rel, where=col, term=term, context=v[:120]))
            continue
        try:
            text = open(f, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for term, rx in terms + ids:
            for m in rx.finditer(text):
                hits.append(dict(file=rel, where=f"char {m.start()}", term=term,
                                 context=text[max(0, m.start() - 50):m.end() + 50].replace("\n", " ")))
        for n, rx in nums:
            for m in rx.finditer(text):
                numbers.append(dict(file=rel, number=n, context=text[max(0, m.start() - 50):m.end() + 50].replace("\n", " ")))
    if tmp:
        shutil.rmtree(tmp)
    return dict(files=files, hits=hits, numbers=numbers)


def scan_md(res: dict, title: str) -> str:
    out = [f"# Leak scan: {title}", "",
           f"Files scanned: {res['files']}. Forbidden terms searched: {len(forbidden_terms())} "
           f"(our signal, finding and check names, the generator's fraud catalogue and look-alikes, the product's name), "
           f"plus S1-S7 in text. Every text cell of every table was searched too.", "",
           f"**Forbidden terms found: {len(res['hits'])}**", ""]
    for h in res["hits"]:
        out.append(f"- `{h['file']}` ({h['where']}): **{h['term']}**: …{h['context']}…")
    out += ["", f"**The checks' numeric constants appearing in text: {len(res['numbers'])}** "
                "(a person judges each one: a number can appear for an innocent reason)", ""]
    for n in res["numbers"]:
        out.append(f"- `{n['file']}`: **{n['number']}**: …{n['context']}…")
    return "\n".join(out) + "\n"


# ---------- the sealed briefing ----------
def honest_sample(out_dir: str) -> int:
    """An ordinary book on an unused seed, with every borrower that has a planted fraud stripped out, together with
    the companies, people, liens and judgments that exist only because of them. Labels and notes are removed."""
    from bt.datagen.generate import main as generate
    raw = tempfile.mkdtemp()
    generate(["--borrowers", str(SAMPLE_BORROWERS), "--scale", str(SAMPLE_SCALE), "--fraud-rate", "0",
              "--seed", str(SAMPLE_SEED), "--out", raw])
    labels = json.load(open(os.path.join(raw, "labels.json")))
    fraud = sorted(b for b, v in labels.items() if v["fraud"])
    con = duckdb.connect()
    for f in glob.glob(os.path.join(raw, "*.parquet")):
        con.execute(f"CREATE TABLE {os.path.basename(f)[:-8]} AS SELECT * FROM read_parquet('{f}')")
    fr = "(" + ",".join(f"'{b}'" for b in fraud) + ")"
    con.execute(f"CREATE TABLE gone_b AS SELECT * FROM borrowers WHERE borrower_id IN {fr}")
    # companies referenced by honest borrowers stay; companies only the stripped borrowers touched go
    con.execute(f"""CREATE TABLE keep_e AS
        SELECT entity_id FROM borrowers WHERE borrower_id NOT IN {fr}
        UNION SELECT payer_id FROM payments WHERE borrower_id NOT IN {fr}
        UNION SELECT payee_id FROM outflows WHERE borrower_id NOT IN {fr}
        UNION SELECT counterparty_entity_id FROM disclosures WHERE borrower_id NOT IN {fr}
        UNION SELECT counterparty_entity_id FROM sec_filings WHERE borrower_id NOT IN {fr}
        UNION SELECT debtor_id FROM invoices WHERE borrower_id NOT IN {fr}
        UNION SELECT lender_entity_id FROM facilities""")
    con.execute(f"""CREATE TABLE gone_e AS SELECT DISTINCT e.entity_id, e.name FROM entities e
        JOIN gone_b g ON e.entity_id = g.entity_id OR e.officer_person_id = g.owner_person_id
          OR e.address = (SELECT address FROM entities WHERE entity_id = g.entity_id)
        UNION SELECT e.entity_id, e.name FROM entities e WHERE e.entity_id IN (
          SELECT payer_id FROM payments WHERE borrower_id IN {fr} UNION SELECT payee_id FROM outflows WHERE borrower_id IN {fr}
          UNION SELECT counterparty_entity_id FROM disclosures WHERE borrower_id IN {fr}
          UNION SELECT counterparty_entity_id FROM sec_filings WHERE borrower_id IN {fr})""")
    con.execute("DELETE FROM gone_e WHERE entity_id IN (SELECT entity_id FROM keep_e WHERE entity_id IS NOT NULL)")
    for t in ("borrowers", "facilities", "tape", "source_truth", "payments", "outflows", "invoices", "financials",
              "disclosures", "pledgecheck", "sec_filings"):
        con.execute(f"DELETE FROM {t} WHERE borrower_id IN {fr}")
    con.execute(f"DELETE FROM public_abs WHERE issuer_borrower_id IN {fr}")
    con.execute("DELETE FROM entities WHERE entity_id IN (SELECT entity_id FROM gone_e)")
    con.execute("DELETE FROM gleif WHERE entity_id IN (SELECT entity_id FROM gone_e)")
    con.execute("CREATE MACRO nm(s) AS regexp_replace(upper(s), '[^A-Z0-9]', '', 'g')")
    con.execute("DELETE FROM ucc_filings WHERE nm(debtor_name) IN (SELECT nm(name) FROM gone_e) "
                "OR nm(secured_party_name) IN (SELECT nm(name) FROM gone_e)")
    con.execute("DELETE FROM court_records WHERE nm(defendant_name) IN (SELECT nm(name) FROM gone_e)")
    con.execute("DELETE FROM persons WHERE person_id IN (SELECT owner_person_id FROM gone_b) AND person_id NOT IN "
                "(SELECT officer_person_id FROM entities WHERE officer_person_id IS NOT NULL)")
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(raw, "*.parquet")):
        t = os.path.basename(f)[:-8]
        schema = pq.read_schema(f)
        tbl = con.execute(f"SELECT * FROM {t}").to_arrow_table().cast(schema)
        pq.write_table(tbl, os.path.join(out_dir, f"{t}.parquet"))
    n = con.execute("SELECT count(*) FROM borrowers").fetchone()[0]
    shutil.rmtree(raw)
    return n


def briefing(out: str) -> str:
    folder = os.path.join(out, "redteam_briefing")
    if os.path.exists(folder):
        shutil.rmtree(folder)
    shutil.copytree(BRIEFING_SRC, folder, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    os.makedirs(os.path.join(folder, "allegations"))
    for a in ALLEGATIONS:
        shutil.copy(os.path.join(ROOT, "research", "sources", a), os.path.join(folder, "allegations", a))
    n = honest_sample(os.path.join(folder, "sample_book"))
    readme = open(os.path.join(folder, "README.md")).read()
    assert f"one honest book: {n} borrowers" in readme, f"README.md must say the sample has {n} borrowers"
    # the example attack must run on a copy of the sample, through bookio
    test = tempfile.mkdtemp()
    shutil.copytree(os.path.join(folder, "sample_book"), os.path.join(test, "book"))
    mod = load_attack(os.path.join(folder, "example_attack"), folder)
    first = sorted(r["borrower_id"] for r in pq.read_table(os.path.join(test, "book", "borrowers.parquet")).to_pylist())[0]
    mod.plant(os.path.join(test, "book"), first, 0)
    shutil.rmtree(test)
    zpath = os.path.join(out, "redteam_briefing.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(folder, "**", "*"), recursive=True)):
            if os.path.isfile(f) and "__pycache__" not in f:
                z.write(f, os.path.relpath(f, out))
    res = scan(folder)
    open(os.path.join(out, "LEAK-SCAN-briefing.md"), "w").write(scan_md(res, "the sealed briefing, before upload"))
    print(f"briefing: {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB, {n} honest borrowers in the sample); "
          f"leak scan: {len(res['hits'])} forbidden terms, {len(res['numbers'])} numbers to look at")
    return zpath


# ---------- freeze ----------
def freeze(zpath: str | None, out: str = FROZEN, tag: str = "redteam-frozen", attacks: str | None = None) -> None:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rec = dict(tag=tag, rule_version=record.rule_version(), code_version=record.code_version(),
               frozen_at=datetime.date.today().isoformat())
    if zpath:
        rec.update(briefing_zip_sha256=hashlib.sha256(open(zpath, "rb").read()).hexdigest(),
                   briefing_zip_bytes=os.path.getsize(zpath))
    if attacks:
        rec.update(attacks_zip_sha256=hashlib.sha256(open(attacks, "rb").read()).hexdigest())
    json.dump(rec, open(out, "w"), indent=1)
    print(json.dumps(rec, indent=1))


def check_frozen(test: bool, seeds, frozen: str = FROZEN) -> dict:
    if test:
        if not set(seeds) <= set(DEV_SEEDS):
            sys.exit("--test runs only on dev seeds (7, 101-105): fresh seeds are scored once, for real")
        return {}
    if not os.path.exists(frozen):
        sys.exit(f"{frozen} is missing: freeze the rules before the red team starts")
    rec = json.load(open(frozen))
    now = record.rule_version()
    if now != rec["rule_version"]:
        sys.exit(f"the rules changed since the freeze ({rec['rule_version']} -> {now}): the score would not be blind")
    return rec


# ---------- planting ----------
def load_attack(folder: str, briefing_dir: str | None = None):
    """Import an attack's plant.py with its own folder (and bookio) importable."""
    if not os.path.exists(os.path.join(folder, "bookio.py")):
        shutil.copy(os.path.join(briefing_dir or BRIEFING_SRC, "bookio.py"), folder)
    sys.path.insert(0, folder)
    try:
        name = "attack_" + re.sub(r"\W", "_", os.path.basename(folder.rstrip("/")))
        spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "plant.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(folder)


OWN_ROWS = {"tape": "borrower_id", "source_truth": "borrower_id", "invoices": "borrower_id", "financials": "borrower_id",
            "disclosures": "borrower_id", "sec_filings": "borrower_id", "public_abs": "issuer_borrower_id"}
ADD_ONLY = ("payments", "outflows")
UNTOUCHABLE = ("borrowers", "facilities", "ucc_filings", "court_records")


def lever_violations(before: str, after: str, b: str) -> tuple[list[str], bool, bool]:
    """What the plant changed that a borrower doesn't control (README.md, rule 1). Returns (violations, servicer,
    history): whether it pulled the two levers a real borrower can only partly pull. `servicer`: it changed its
    servicer records. `history`: it faked a company's history, by changing when an existing company was formed or
    whether it shows a real business, or by adding a company formed before month 0 (an old shelf company) or one
    that shows a real business (a dressed-up shell)."""
    con = duckdb.connect()
    out, servicer, history = [], False, False
    q = lambda s: con.execute(s).fetchall()  # noqa: E731
    owner, own_e = q(f"SELECT owner_person_id, entity_id FROM read_parquet('{before}/borrowers.parquet') "
                     f"WHERE borrower_id = '{b}'")[0]
    for f in sorted(glob.glob(os.path.join(before, "*.parquet"))):
        t = os.path.basename(f)[:-8]
        g = os.path.join(after, f"{t}.parquet")
        if pq.read_schema(f) != pq.read_schema(g):
            out.append(f"{t}: the table's layout changed")
            continue
        old, new = f"read_parquet('{f}')", f"read_parquet('{g}')"
        removed = f"(SELECT * FROM {old} EXCEPT ALL SELECT * FROM {new})"
        added = f"(SELECT * FROM {new} EXCEPT ALL SELECT * FROM {old})"
        n_rem, n_add = q(f"SELECT count(*) FROM {removed}")[0][0], q(f"SELECT count(*) FROM {added}")[0][0]
        if not (n_rem or n_add):
            continue
        if t in UNTOUCHABLE:
            out.append(f"{t}: {n_rem} row(s) removed or changed, {n_add} added; the borrower doesn't control it")
        elif t in OWN_ROWS:
            col = OWN_ROWS[t]
            others = q(f"SELECT count(*) FROM (SELECT * FROM {removed} UNION ALL SELECT * FROM {added}) WHERE {col} IS DISTINCT FROM '{b}'")[0][0]
            if others:
                out.append(f"{t}: {others} row(s) of other borrowers changed")
            servicer |= t == "source_truth"
        elif t in ADD_ONLY:
            if n_rem:
                out.append(f"{t}: {n_rem} recorded payment(s) removed or changed; only new ones may be added")
            if q(f"SELECT count(*) FROM {added} WHERE borrower_id IS DISTINCT FROM '{b}'")[0][0]:
                out.append(f"{t}: payments added to other borrowers' accounts")
        elif t == "pledgecheck":
            if n_add or q(f"SELECT count(*) FROM {removed} WHERE borrower_id IS DISTINCT FROM '{b}'")[0][0]:
                out.append("pledgecheck: results changed (only leaving the registry, by removing its own rows, is allowed)")
        elif t == "persons":
            if n_rem or q(f"SELECT count(*) FROM {added} WHERE person_id IN (SELECT person_id FROM {old})")[0][0]:
                out.append("persons: existing people removed or changed; only new people may be added")
        elif t in ("entities", "gleif"):
            ent = f"read_parquet('{before}/entities.parquet')"
            allowed = (f"(SELECT entity_id FROM {ent} WHERE entity_id = '{own_e}' OR officer_person_id = '{owner}' "
                       f"UNION SELECT entity_id FROM read_parquet('{after}/entities.parquet') WHERE entity_id NOT IN "
                       f"(SELECT entity_id FROM {ent}))")
            bad = q(f"SELECT count(*) FROM (SELECT entity_id FROM {removed} UNION ALL SELECT entity_id FROM {added}) "
                    f"WHERE entity_id NOT IN {allowed}")[0][0]
            if bad:
                out.append(f"{t}: {bad} row(s) of companies the borrower doesn't control changed")
            if t == "entities":
                changed = q(f"SELECT count(*) FROM {added} a JOIN {old} o USING (entity_id) "
                            f"WHERE a.formed_month IS DISTINCT FROM o.formed_month OR a.has_operations IS DISTINCT FROM o.has_operations")[0][0]
                dressed = q(f"SELECT count(*) FROM {added} WHERE entity_id NOT IN (SELECT entity_id FROM {old}) "
                            f"AND (formed_month < 0 OR has_operations)")[0][0]
                history |= bool(changed or dressed)
        else:
            out.append(f"{t}: changed, and no rule covers it")
    return out, servicer, history


def dq_issues(book: str) -> list[str]:
    return [f"{t}: {', '.join(i)}" for t in dq.REQUIRED if (i := dq.check(os.path.join(book, f"{t}.parquet"), t))]


def _book_files(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    for f in glob.glob(os.path.join(src, "*.parquet")) + [os.path.join(src, "labels.json"), os.path.join(src, "manifest.json")]:
        shutil.copy2(f, dst)


def plant(attacks_zip: str, seeds, root: str, test: bool, frozen: str = FROZEN) -> None:
    check_frozen(test, seeds, frozen)
    from bt.eval.evaluate import ensure_book
    adir = os.path.join(root, "attacks_received")
    if os.path.exists(adir):
        shutil.rmtree(adir)
    zipfile.ZipFile(attacks_zip).extractall(adir)
    folders = sorted({os.path.dirname(p) for p in glob.glob(os.path.join(adir, "**", "plant.py"), recursive=True)})
    attacks = {os.path.basename(f): f for f in folders if os.path.basename(f) != "example_attack"}
    log = dict(attacks_zip_sha256=hashlib.sha256(open(attacks_zip, "rb").read()).hexdigest(), attacks=sorted(attacks),
               books={})
    for seed in seeds:
        a_book = ensure_book(os.path.join(root, "A"), seed, 120)
        b_book = os.path.join(root, "B", f"seed_{seed}")
        if os.path.exists(b_book):
            shutil.rmtree(b_book)
        _book_files(a_book, b_book)
        labels = json.load(open(os.path.join(b_book, "labels.json")))
        btype = {r["borrower_id"]: r["btype"] for r in pq.read_table(os.path.join(b_book, "borrowers.parquet")).to_pylist()}
        limit = {r["borrower_id"]: r["facility_limit"] for r in pq.read_table(os.path.join(b_book, "borrowers.parquet")).to_pylist()}
        used, planted = set(), {}
        for i, (name, folder) in enumerate(sorted(attacks.items())):
            try:
                mod = load_attack(folder)
                applies, start = list(mod.APPLIES_TO), int(mod.START_MONTH)
            except Exception as e:
                planted[f"{name}:load"] = dict(attack=name, valid=False, problems=[f"didn't load: {type(e).__name__}: {e}"])
                continue
            pool = sorted(b for b, v in labels.items() if not v["fraud"] and btype[b] in applies and b not in used)
            rng = np.random.default_rng([seed, 4242, i])
            for k, b in enumerate(rng.choice(pool, size=min(PER_BOOK, len(pool)), replace=False) if pool else []):
                b = str(b)
                used.add(b)
                snap = tempfile.mkdtemp()
                _book_files(b_book, snap)
                problems, gain, how, servicer, history = [], 0.0, "", False, False
                try:
                    res = mod.plant(b_book, b, int(seed) * 1000 + i * 10 + k)
                    gain, how = float(res["gain_usd"]), str(res.get("how", ""))
                except Exception as e:
                    problems.append(f"crashed: {type(e).__name__}: {e}"[:300])
                if not problems:
                    lv, servicer, history = lever_violations(snap, b_book, b)
                    problems += lv + [f"data quality: {x}" for x in dq_issues(b_book)]
                    if start > LAST_START:
                        problems.append(f"starts at month {start}, after month {LAST_START}")
                ok = not problems
                if not ok:  # reverted, never repaired
                    for f in glob.glob(os.path.join(snap, "*.parquet")):
                        shutil.copy2(f, b_book)
                planted[b] = dict(attack=name, valid=ok, problems=problems, gain_usd=gain, how=how,
                                  facility_limit=limit[b], gain_share=gain / limit[b] if limit[b] else 0.0,
                                  small=ok and gain < SIZE_FLOOR * limit[b], start_month=start,
                                  servicer=servicer or bool(getattr(mod, "USES_SERVICER_RECORDS", False)),
                                  history=history or bool(getattr(mod, "USES_COMPANY_HISTORY", False)))
                shutil.rmtree(snap)
                print(f"  seed {seed} {name} -> {b}: {'planted' if ok else 'REVERTED: ' + '; '.join(problems)[:200]}")
        json.dump(planted, open(os.path.join(b_book, "redteam_labels.json"), "w"), indent=1)
        log["books"][seed] = planted
    json.dump(log, open(os.path.join(root, "plant_log.json"), "w"), indent=1)


# ---------- scoring, once ----------
def score(seeds, root: str, report_a: str, report_rt: str, test: bool, frozen_path: str = FROZEN,
          label: str = "") -> None:
    frozen = check_frozen(test, seeds, frozen_path)
    from bt.eval.evaluate import main as evaluate
    from bt.pipeline.run import run as pipeline
    evaluate(["--seeds", *map(str, seeds), "--root", os.path.join(root, "A"), "--report", report_a])  # copy A
    rows, honest_end, honest_ever, honest_review, honest_n, orig_caught, orig_n = [], 0, 0, 0, 0, 0, 0
    for seed in seeds:
        book = os.path.join(root, "B", f"seed_{seed}")
        labels = json.load(open(os.path.join(book, "labels.json")))
        rt = {b: v for b, v in json.load(open(os.path.join(book, "redteam_labels.json"))).items() if v.get("valid")}
        first_flag, first_review, ever = {}, {}, set()
        for m in range(MONTHS):
            _, cases, _ = pipeline(book, m)
            for c in cases:
                if c["verdict"] == "LIKELY_FRAUD":
                    first_flag.setdefault(c["borrower_id"], m)
                    ever.add(c["borrower_id"])
                elif c["verdict"] == "NEEDS_MORE_EVIDENCE":
                    first_review.setdefault(c["borrower_id"], m)
        final = {c["borrower_id"]: c for c in cases}
        for b, v in rt.items():
            c = final[b]
            outcome = {"LIKELY_FRAUD": "caught", "NEEDS_MORE_EVIDENCE": "sent to review"}.get(c["verdict"], "missed")
            rows.append(dict(seed=seed, borrower_id=b, **v, outcome=outcome, verdict=c["verdict"],
                             first_flag=first_flag.get(b), first_review=first_review.get(b),
                             findings=[f"{f['mechanism']} ({f['confidence']})" for f in c["findings"]]))
        honest = [b for b, v in labels.items() if not v["fraud"] and b not in rt]
        honest_n += len(honest)
        honest_end += sum(final[b]["verdict"] == "LIKELY_FRAUD" for b in honest)
        honest_ever += sum(b in ever for b in honest)
        honest_review += sum(final[b]["verdict"] == "NEEDS_MORE_EVIDENCE" for b in honest)
        orig = [b for b, v in labels.items() if v["fraud"]]
        orig_n += len(orig)
        orig_caught += sum(final[b]["verdict"] == "LIKELY_FRAUD" for b in orig)
    out = dict(label=label, frozen=frozen, rule_version=record.rule_version(), code_version=record.code_version(), seeds=list(seeds),
               rows=rows, honest=dict(n=honest_n, flagged_end=honest_end, flagged_ever=honest_ever,
                                      review_per_100=round(100 * honest_review / honest_n, 1) if honest_n else None),
               original_frauds=dict(n=orig_n, caught=orig_caught),
               attacks_leak_scan=scan(os.path.join(root, "attacks_received")))
    json.dump(out, open(report_rt.replace(".md", ".json"), "w"), indent=1, default=str)
    open(report_rt, "w").write(redteam_md(out))
    print(redteam_md(out))


def redteam_md(r: dict) -> str:
    from collections import Counter, defaultdict
    by = defaultdict(list)
    for x in r["rows"]:
        by[x["attack"]].append(x)

    def tally(xs):
        c = Counter(x["outcome"] for x in xs)
        return c["caught"], c["sent to review"], c["missed"]

    def months(xs):
        d = sorted(x["first_flag"] - x["start_month"] for x in xs if x["outcome"] == "caught" and x["first_flag"] is not None)
        return f"{d[len(d) // 2]}" if d else "-"

    lines = [f"# Red team result: seeds {', '.join(map(str, r['seeds']))}, scored once"
             + (f" ({r['label']})" if r.get("label") else ""), "",
             "**All data synthetic.** The attacks were designed by an AI red team that had not seen the rules "
             "(RED-TEAM-PLAN.md). They measure what this red team thought of, not real-world catch rates.", ""]
    if r.get("label"):
        lines += [f"**{r['label']}.** The rules were fixed after round 1 of these same attacks was scored, so this run "
                  "is not blind: it shows whether the fixes work on fresh books, not how a new attacker would do.", ""]
    lines += [
             f"Rules version {r['rule_version']} (frozen: {r['frozen'].get('rule_version', 'test run')}); "
             f"code {r['code_version']}.", "",
             f"Counted: frauds gaining at least {SIZE_FLOOR:.0%} of the borrower's credit limit. Smaller ones are shown "
             "apart, as \"too small to matter\".", "",
             "| Attack | Counted | Caught | Sent to review | Missed | Median months to catch | Too small (caught / review / missed) | Servicer lever | Company-history lever |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, xs in sorted(by.items()):
        big, small = [x for x in xs if not x["small"]], [x for x in xs if x["small"]]
        c, v, m = tally(big)
        sc, sv, sm = tally(small)
        lines.append(f"| {name} | {len(big)} | {c} | {v} | {m} | {months(big)} | "
                     f"{f'{len(small)} ({sc} / {sv} / {sm})' if small else '-'} | "
                     f"{'yes' if any(x['servicer'] for x in xs) else 'no'} | "
                     f"{'yes' if any(x.get('history') for x in xs) else 'no'} |")
    for label, keep in (("All counted attacks", lambda x: True),
                        ("Without either partial lever", lambda x: not x["servicer"] and not x.get("history")),
                        ("With the servicer lever", lambda x: x["servicer"]),
                        ("With the company-history lever", lambda x: x.get("history"))):
        xs = [x for x in r["rows"] if not x["small"] and keep(x)]
        if xs:
            c, v, m = tally(xs)
            lines.append(f"| **{label}** | {len(xs)} | {c} | {v} | {m} | {months(xs)} | | | |")
    h = r["honest"]
    lines += ["", f"Honest borrowers in the attacked books: {h['n']}. Flagged at month 24: {h['flagged_end']}; "
                  f"flagged in any month: {h['flagged_ever']}; sent to review: {h['review_per_100']} per 100.",
              f"The books' own planted frauds: {r['original_frauds']['caught']}/{r['original_frauds']['n']} caught.", "",
              "## Every red-team fraud not caught", ""]
    for x in r["rows"]:
        if x["outcome"] != "caught":
            lines.append(f"- **{x['attack']}** on {x['borrower_id']} (seed {x['seed']}): {x['outcome']}"
                         f"{' (too small to matter)' if x['small'] else ''}; gain ${x['gain_usd']:,.0f} "
                         f"({x['gain_share']:.0%} of the credit limit); findings: {', '.join(x['findings']) or 'none'}")
    scan_ = r["attacks_leak_scan"]
    lines += ["", f"## Leak scan of the hand-in: {len(scan_['hits'])} forbidden terms", ""]
    lines += [f"- `{s['file']}`: {s['term']}: …{s['context']}…" for s in scan_["hits"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("briefing")
    p.add_argument("--out", required=True)
    p = sub.add_parser("scan")
    p.add_argument("path")
    p = sub.add_parser("freeze")
    p.add_argument("--zip", default=None, help="the sealed briefing given to the red team")
    p.add_argument("--attacks", default=None, help="the attacks being re-scored, if any")
    p.add_argument("--out", default=FROZEN)
    p.add_argument("--tag", default="redteam-frozen")
    for name in ("plant", "score"):
        p = sub.add_parser(name)
        p.add_argument("--seeds", type=int, nargs="+", default=list(FRESH_SEEDS))
        p.add_argument("--root", default="data/out/redteam")
        p.add_argument("--test", action="store_true", help="dev seeds only, no freeze check: for testing this harness")
        p.add_argument("--frozen", default=FROZEN, help="the freeze record the rules must match")
        if name == "plant":
            p.add_argument("--attacks", required=True)
            p.add_argument("--i-have-read-them", action="store_true", help="a person read every plant.py first")
        else:
            p.add_argument("--report-a", default="proof/REPORT_seeds501-505.md")
            p.add_argument("--report", default="proof/REDTEAM.md")
            p.add_argument("--label", default="", help='e.g. "after fixes: these attacks are no longer blind"')
    a = ap.parse_args(argv)
    if a.cmd == "briefing":
        briefing(a.out)
    elif a.cmd == "scan":
        res = scan(a.path)
        print(scan_md(res, a.path))
    elif a.cmd == "freeze":
        freeze(a.zip, a.out, a.tag, a.attacks)
    elif a.cmd == "plant":
        if not a.i_have_read_them:
            sys.exit("read every plant.py first, then pass --i-have-read-them")
        plant(a.attacks, a.seeds, a.root, a.test, a.frozen)
    else:
        score(a.seeds, a.root, a.report_a, a.report, a.test, a.frozen, a.label)


if __name__ == "__main__":
    main()
