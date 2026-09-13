"""Investigator agent: an open model checks a case with tools and drafts a memo for
the credit officer. It never decides: the verdict comes from the rules, and
nothing downstream reads the agent's output to change it.

Guardrails, enforced in code rather than by asking the model nicely:
- tools only read: the case evidence, the company registry, lien and court
  records, payments, disclosures, and GLEIF (live, exact legal-name match only)
- every memo line must cite a signal ID or a tool call the agent made. A line is
  dropped (and counted) if it cites nothing, cites an ID that doesn't exist, or
  states a number that isn't in the evidence it cites
- if a model is down it moves to the next open model; if all are down there is
  no memo, and the rule-based case still stands on its own

    scripts/with-env.sh uv run python -m bt.agent.investigate --data data/out/demo --borrower B0028
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import duckdb
from rapidfuzz import fuzz

from bt.adapters import gleif

ROUTER = os.environ.get("HF_ROUTER_URL", "https://router.huggingface.co/v1/chat/completions")
MODELS = ["openai/gpt-oss-120b", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen3-8B"]  # all open-weight
MAX_ROUNDS = 8
RESULT_CHARS = 3500

SYSTEM = """You are an investigator on a bank's credit-risk team. Rule-based checks have already reached a verdict on a borrower. You cannot change it: do not state your own verdict and do not recommend lending decisions.
Your job: use the tools to check the case from other angles (who the linked companies are, who else has claims on them, where the money really came from, what the borrower disclosed), then write a short memo for the credit officer.
Start with case_evidence. Then make 3 to 6 more tool calls. Search liens and courts by company name (the borrower's and each linked company's), never by ID. If the case mentions money coming back or a payer who is not a customer, check outgoing_payments for that payer. Then write the memo.
Memo format, strictly: 4 to 8 lines, each starting with "- ", each one sentence, each ending with its sources in square brackets: tool call IDs like [T3] or signal IDs like [S3-B0028-RELATED_PARTY_INFLOW-3a0eb607]. Copy signal IDs exactly and never join a tool call ID to a signal ID.Only state facts and numbers that appear in the sources you cite, and copy amounts exactly as written there. Include at least one line on what you could not confirm or what cuts against the finding. The last line starts with "- Ask the borrower:". No headings and no other text."""

TOOLS = [
    ("case_evidence", "The rules' verdict, findings and every signal (with IDs) for a borrower.", {"borrower_id": "e.g. B0028"}),
    ("related_companies", "Companies sharing an officer or a registered address with the borrower.", {"borrower_id": "e.g. B0028"}),
    ("company_registry", "Look up companies in the registry by (part of) a name.", {"name": "company name or part of it"}),
    ("lien_search", "Public UCC lien filings whose debtor name matches (fuzzy).", {"name": "company name"}),
    ("court_search", "Court judgments whose defendant name matches (fuzzy).", {"name": "company name"}),
    ("payer_summary", "Payments into the borrower's collection account from one payer: count, total, months, memos, "
                      "and share of all inflows.", {"borrower_id": "e.g. B0028", "payer_name": "exact payer name"}),
    ("disclosures", "What the borrower disclosed to the bank: debts, affiliates, programmes.", {"borrower_id": "e.g. B0028"}),
    ("outgoing_payments", "Money the borrower sent from its own operating account to one payee: count, total, months, "
                          "and whether the same payee also sent money back.", {"borrower_id": "e.g. B0028",
                                                                               "payee_name": "exact payee name"}),
    ("gleif_lookup", "Live public legal-entity (LEI) registry: exact legal-name match, with parent companies.",
     {"name": "exact legal name"}),
]
TOOL_NAMES = {t[0] for t in TOOLS}
SUFFIX = re.compile(r"\b(llc|inc|corp|corporation|co|ltd|lp|llp|n a|na)\b")


def schema() -> list[dict]:
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in p.items()},
        "required": list(p)}}} for n, d, p in TOOLS]


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()))).strip()


class Tools:
    """Read-only tools over one book. Every call gets an ID (T1, T2, ...) the memo must cite."""

    def __init__(self, data_dir: str, cases: list[dict], live_gleif: bool = True):
        self.con = duckdb.connect()
        for t in ("entities", "ucc_filings", "court_records", "payments", "persons", "disclosures", "borrowers", "outflows"):
            f = os.path.join(data_dir, f"{t}.parquet")
            if os.path.exists(f):
                self.con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{f}')")
        self.cases = {c["borrower_id"]: c for c in cases}
        self.live_gleif = live_gleif
        self.calls: list[dict] = []
        self._ucc = self.rows("SELECT filing_id, debtor_name, debtor_address, secured_party_name, collateral_desc, "
                              "filed_month FROM ucc_filings")
        self._court = self.rows("SELECT case_id, defendant_name, plaintiff, kind, amount, month FROM court_records")
        # every company name the memo might mention, for the claim checks
        self._names = sorted({norm(n) for n in [r["name"] for r in self.rows("SELECT name FROM entities")]
                              + [r["secured_party_name"] for r in self._ucc] + [r["plaintiff"] for r in self._court]
                              if len(norm(n)) >= 6}, key=len, reverse=True)

    def rows(self, sql: str, *args) -> list[dict]:
        cur = self.con.execute(sql, list(args))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, [round(v, 2) if isinstance(v, float) else v for v in r])) for r in cur.fetchall()]

    def run(self, name: str, args: dict) -> tuple[str, dict]:
        tid = f"T{len(self.calls) + 1}"
        try:
            if name not in TOOL_NAMES:
                raise ValueError(f"no tool called {name}")
            out = getattr(self, "t_" + name)(**{k: str(v) for k, v in args.items()})
        except Exception as e:  # a bad call is reported back to the model, never raised
            out = {"error": f"{type(e).__name__}: {e}"[:200]}
        self.calls.append(dict(id=tid, tool=name, args=args, result=out))
        return tid, out

    def t_case_evidence(self, borrower_id):
        c = self.cases[borrower_id]
        return dict(verdict_by_rules=c["verdict"], headline=c["headline"],
                    findings=[dict(mechanism=f["mechanism"], confidence=f["confidence"], plain=f["plain"],
                                   signals=f["signals"], corroborated_by=f.get("corroborated_by") or [])
                              for f in c["findings"]],
                    signals=[dict(id=s["signal_id"], system=s["system"], type=s["type"], explanation=s["explanation"],
                                  evidence=s["evidence"][:5], month=s["observed_month"]) for s in c["signals"]])

    def t_related_companies(self, borrower_id):
        return self.rows("""
            WITH b AS (SELECT e.* FROM borrowers JOIN entities e USING (entity_id) WHERE borrower_id = ?)
            SELECT e.entity_id, e.name, e.kind, p.name AS officer, e.address, e.formed_month, e.has_operations,
                   e.officer_person_id = b.officer_person_id AS same_officer, e.address = b.address AS same_address,
                   e.entity_id = b.entity_id AS is_borrower
            FROM entities e CROSS JOIN b LEFT JOIN persons p ON p.person_id = e.officer_person_id
            WHERE e.officer_person_id = b.officer_person_id OR e.address = b.address
            ORDER BY is_borrower DESC, e.formed_month LIMIT 12""", borrower_id)

    def t_company_registry(self, name):
        return self.rows("""SELECT e.entity_id, e.name, e.kind, p.name AS officer, e.address, e.formed_month, e.has_operations
                            FROM entities e LEFT JOIN persons p ON p.person_id = e.officer_person_id
                            WHERE e.name ILIKE '%' || ? || '%' ORDER BY e.entity_id LIMIT 10""", name)

    def _fuzzy(self, rows, key, name):
        n = norm(name)
        hits = [dict(r, match_score=round(fuzz.token_sort_ratio(n, norm(r[key])))) for r in rows]
        hits = [h for h in hits if h["match_score"] >= 88]
        return sorted(hits, key=lambda h: (-h["match_score"], str(h.get("filed_month", h.get("month")))))[:10] or \
            {"result": f"no records matching '{name}'"}

    def _resolve(self, q: str) -> str:
        """Public records carry names, not IDs: a borrower or entity ID is turned into its legal name."""
        q = q.strip()
        if re.fullmatch(r"B\d{4}", q):
            r = self.rows("SELECT e.name FROM borrowers b JOIN entities e USING (entity_id) WHERE b.borrower_id = ?", q)
        elif re.fullmatch(r"E\d{6}", q):
            r = self.rows("SELECT name FROM entities WHERE entity_id = ?", q)
        else:
            return q
        return r[0]["name"] if r else q

    def t_lien_search(self, name):
        return self._fuzzy(self._ucc, "debtor_name", self._resolve(name))

    def t_court_search(self, name):
        return self._fuzzy(self._court, "defendant_name", self._resolve(name))

    def facts(self, borrower_id: str) -> dict:
        """What the records say, for checking the memo's claims. Never shown to the model."""
        name = self._resolve(borrower_id)
        disclosed = {norm(r["name"]) for r in self.rows(
            "SELECT e.name FROM disclosures d JOIN entities e ON e.entity_id = d.counterparty_entity_id "
            "WHERE d.borrower_id = ?", borrower_id)}
        return dict(borrower=norm(name), disclosed=disclosed, names=self._names,
                    borrower_liens=isinstance(self._fuzzy(self._ucc, "debtor_name", name), list),
                    borrower_judgments=isinstance(self._fuzzy(self._court, "defendant_name", name), list))

    def t_payer_summary(self, borrower_id, payer_name):
        r = self.rows("""SELECT count(*) AS payments, sum(amount) AS total, min(month) AS first_month, max(month) AS last_month,
                                list(DISTINCT memo ORDER BY memo) AS memos, list(txn_id ORDER BY txn_id)[1:3] AS examples
                         FROM payments WHERE borrower_id = ? AND lower(payer_name) = lower(?)""", borrower_id, payer_name)[0]
        if not r["payments"]:
            names = [x["payer_name"] for x in self.rows(
                "SELECT DISTINCT payer_name FROM payments WHERE borrower_id = ?", borrower_id)]
            close = sorted(names, key=lambda x: -fuzz.token_sort_ratio(norm(x), norm(payer_name)))[:3]
            return {"result": f"no payments from '{payer_name}'", "closest_payer_names": close}
        all_in = self.rows("SELECT sum(amount) AS t FROM payments WHERE borrower_id = ?", borrower_id)[0]["t"]
        return dict(r, payer=payer_name, share_of_all_inflows_pct=round(100 * r["total"] / all_in, 1))

    def t_disclosures(self, borrower_id):
        return self.rows("""SELECT d.kind, d.counterparty_entity_id, e.name AS counterparty, d.note
                            FROM disclosures d LEFT JOIN entities e ON e.entity_id = d.counterparty_entity_id
                            WHERE d.borrower_id = ? ORDER BY d.kind""", borrower_id) or \
            {"result": "the borrower disclosed nothing"}

    def t_outgoing_payments(self, borrower_id, payee_name):
        if not self.rows("SELECT count(*) AS n FROM duckdb_views() WHERE view_name = 'outflows'")[0]["n"]:
            return {"result": "no operating-account data for this book"}
        r = self.rows("""SELECT count(*) AS payments, sum(amount) AS total, min(month) AS first_month,
                                max(month) AS last_month, list(DISTINCT memo ORDER BY memo) AS memos
                         FROM outflows WHERE borrower_id = ? AND lower(payee_name) = lower(?)""",
                      borrower_id, payee_name)[0]
        back = self.rows("SELECT count(*) AS n, sum(amount) AS total FROM payments WHERE borrower_id = ? "
                         "AND lower(payer_name) = lower(?)", borrower_id, payee_name)[0]
        if not r["payments"]:
            return {"result": f"no payments to '{payee_name}'"}
        return dict(r, payee=payee_name, same_party_paid_back=back["n"], paid_back_total=back["total"])

    def t_gleif_lookup(self, name):
        if not self.live_gleif:
            return {"result": "GLEIF lookup switched off for this run"}
        r = gleif.lookup(name, limit=2)
        if r["match"] != "exact legal name":
            return {"query": name, "result": "no GLEIF record with this exact legal name", "source": r["source"]}
        return dict(query=name, source=r["source"], records=[{k: rec.get(k) for k in (
            "lei", "legal_name", "status", "jurisdiction", "direct_parent", "ultimate_parent")} for rec in r["records"]])


# ---------- memo validation ----------
BRACKETS = re.compile(r"\[([^\[\]]+)\]")
NUM = re.compile(r"(?<![A-Za-z0-9\-_])(\$?\d[\d,]*(?:\.\d+)?)\s?([kKmMbB](?![a-z])|million|billion)?(%?)")
SCALE = {"k": 1e3, "m": 1e6, "b": 1e9, "million": 1e6, "billion": 1e9}


def _values(text: str) -> list[tuple[float, bool, float]]:
    """(value, is_amount_or_rate, rounding tolerance) for every number in the text; '$229k' is 229,000 give or take 500."""
    out = []
    for num, unit, pct in NUM.findall(text):
        try:
            v = float(num.replace("$", "").replace(",", ""))
        except ValueError:
            continue
        mult = SCALE.get(unit.lower(), 1.0) if unit else 1.0
        decimals = len(num.split(".")[1]) if "." in num else 0
        out.append((v * mult, num.startswith("$") or bool(pct) or "." in num or bool(unit), 0.5 * mult * 10 ** -decimals))
    return out


NEG_DISCLOSED = re.compile(r"undisclosed|not\s+(?:been\s+)?disclosed|never\s+disclosed|"
                           r"(?:did\s+not|didn't|does\s+not|doesn't|failed\s+to)\s+disclose|without\s+disclos|"
                           r"(?:do|does|did)\s*(?:not|n't)\s+(?:mention|include|list|show|report)|omit(?:s|ted)?\b|"
                           r"not\s+(?:mentioned|included|listed)", re.I)
ABSENT = re.compile(
    r"\bno\s+(?:public\s+|ucc\s+|court\s+|lien\s+)*(?:liens?|judg(?:e)?ments?|ucc\s+filings?|court\s+records?)\b"
    r"|\b(?:did\s+not|could\s*n[o']t|couldn't|didn't|failed\s+to)\s+(?:find|locate|identify|confirm\s+(?:any|the\s+existence\s+of))"
    r"\b[^.]{0,40}?\b(?:liens?|judg(?:e)?ments?|court\s+records?)\b"
    r"|\b(?:liens?|judg(?:e)?ments?)\b[^.]{0,30}\b(?:were|was)\s+(?:not|never)\s+(?:found|filed|recorded)", re.I)


def _mentions(body: str, names: list[str]) -> list[str]:
    """Company names in the text, longest first; a matched name is consumed so 'Silverline Credit' can't
    also match inside 'Silverline Credit Fund'."""
    ln, found = f" {norm(body)} ", []
    for n in names:  # sorted longest first
        if f" {n} " in ln:
            found.append(n)
            ln = ln.replace(f" {n} ", " | ")
    return found


def _claim_problem(body: str, facts: dict | None) -> str | None:
    """Checks two kinds of claim against the records: what was disclosed, and whether liens or judgments exist."""
    if not facts:
        return None
    others = [n for n in _mentions(body, facts["names"]) if n != facts["borrower"]]
    if "disclos" in body.lower():
        negative = bool(NEG_DISCLOSED.search(body))
        for n in others:
            listed = any(fuzz.token_sort_ratio(n, d) >= 90 for d in facts["disclosed"])
            if negative and listed:
                return f"says '{n}' was not disclosed, but the disclosures list it"
            if not negative and not listed:
                return f"says '{n}' was disclosed, but the disclosures don't list it"
    if not others and ABSENT.search(body):  # a claim that something is absent, about the borrower itself
        low = body.lower()
        if ("lien" in low or "ucc" in low) and facts["borrower_liens"]:
            return "says there are no liens, but the lien records show some against the borrower"
        if ("judg" in low or "court" in low) and facts["borrower_judgments"]:
            return "says there are no judgments, but the court records show some against the borrower"
    return None


def _canon(cid: str, signals: dict, calls: dict) -> str:
    """Models sometimes glue IDs together ('T1-S3-B0043-...') or garble the type; the 8-hex suffix is unique."""
    if cid in signals or cid in calls:
        return cid
    m = re.match(r"T\d+-(.+)$", cid)
    if m and m.group(1) in signals:
        return m.group(1)
    tail = cid.rsplit("-", 1)[-1]
    hits = [s for s in signals if s.endswith("-" + tail)] if re.fullmatch(r"[0-9a-f]{8}", tail) else []
    return hits[0] if len(hits) == 1 else cid


def validate(text: str, signals: dict[str, dict], calls: dict[str, dict],
             facts: dict | None = None) -> tuple[list[dict], list[dict]]:
    lines = [l.strip()[2:].strip() for l in text.splitlines() if l.strip()[:2] in ("- ", "* ", "• ")]
    kept, dropped = [], []
    for line in lines:
        ids = [x.strip() for g in BRACKETS.findall(line) for x in re.split(r"[,;]\s*", g) if x.strip()]
        body = re.sub(r"\s*\[[^\[\]]*\]", "", line).strip()  # also drops empty "[]"
        ask = body.lower().startswith("ask the borrower")
        if not ids and not ask:
            dropped.append(dict(text=line, reason="cites no source"))
            continue
        ids = list(dict.fromkeys(_canon(i, signals, calls) for i in ids))
        unknown = [i for i in ids if i not in signals and i not in calls]
        if unknown:
            dropped.append(dict(text=line, reason=f"cites an unknown source: {unknown[0]}"))
            continue
        # a question for the borrower asserts nothing and may go uncited; its numbers must still be in the evidence
        cited = ids or list(signals) + list(calls)
        source_text = " ".join(json.dumps(signals.get(i) or calls[i]["result"], default=str) for i in cited)
        have = [v for v, _, _ in _values(source_text)]
        bad = [v for v, strong, tol in _values(body) if (strong or v >= 13)  # small bare counts and months are allowed
               and not any(abs(v - h) <= max(1.0, tol) for h in have)]
        if bad:
            dropped.append(dict(text=line, reason=f"states a number not in its sources: {bad[0]:g}"))
            continue
        problem = _claim_problem(body, facts)
        if not problem and facts and ids:  # every company a line names must appear in what that line cites
            src = f" {norm(source_text)} "
            ungrounded = [n for n in _mentions(body, facts["names"]) if n != facts["borrower"] and f" {n} " not in src]
            if ungrounded:
                problem = f"names '{ungrounded[0]}', which its sources don't mention"
        if problem:
            dropped.append(dict(text=line, reason=problem))
            continue
        kept.append(dict(text=body.rstrip(" ."), cites=ids))
    return kept, dropped


# ---------- the loop ----------
def chat(model: str, messages: list[dict], tools: list[dict] | None, token: str, router: str = ROUTER) -> dict:
    body = {"model": model, "messages": messages, "max_tokens": 1500, "temperature": 0}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(router, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "borrower-truth-agent/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _loop(model, borrower_id, tools: Tools, ask):
    c = tools.cases[borrower_id]
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Investigate borrower {borrower_id}. The rules' verdict is {c['verdict']}: "
                                        f"{c['headline']}."}]
    used, t0 = 0, time.perf_counter()
    for rnd in range(MAX_ROUNDS):
        last = rnd == MAX_ROUNDS - 1
        if last:
            msgs.append({"role": "user", "content": "Write the memo now, in the required format."})
        r = ask(model, msgs, None if last else schema())
        used += (r.get("usage") or {}).get("total_tokens", 0)
        m = r["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        if not calls:
            signals = {s["signal_id"]: s for s in c["signals"]}
            kept, dropped = validate(m.get("content") or "", signals, {x["id"]: x for x in tools.calls},
                                     tools.facts(borrower_id))
            if not kept:
                raise ValueError("memo had no line that passed validation")
            return dict(status="ok", model=model, memo=kept, dropped=dropped, rounds=rnd + 1, tokens=used,
                        seconds=round(time.perf_counter() - t0, 1))
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
        for tc in calls:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tid, out = tools.run(tc["function"]["name"], args)
            msgs.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": json.dumps({"call_id": tid, "result": out}, default=str)[:RESULT_CHARS]})
    raise ValueError("no memo within the round limit")


def investigate(borrower_id: str, tools: Tools, token: str | None, models=MODELS, router: str = ROUTER, ask=None) -> dict:
    """`ask(model, messages, tools)` returns an OpenAI-shaped response; default: the Hugging Face router."""
    ask = ask or (lambda m, msgs, t: chat(m, msgs, t, token, router))
    errors = []
    for model in models:
        tools.calls.clear()
        try:
            res = _loop(model, borrower_id, tools, ask)
            break
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as e:
            code = getattr(e, "code", None)
            errors.append(f"{model}: {type(e).__name__}{f' {code}' if code else ''} {getattr(e, 'reason', '') or e}"[:200])
    else:
        res = dict(status="unavailable", model=None, memo=[], dropped=[], note="agent unavailable; the rule-based case stands")
    steps = [dict(id=x["id"], tool=x["tool"], args=x["args"],
                  result=json.dumps(x["result"], default=str)[:700]) for x in tools.calls]
    c = tools.cases[borrower_id]
    return dict(borrower_id=borrower_id, verdict_by_rules=c["verdict"], steps=steps, errors=errors,
                generated_at=time.strftime("%Y-%m-%d"), **res)


def revalidate(res: dict, tools: Tools) -> dict:
    """Re-apply the current checks to a saved memo without calling the model again. The tools are
    deterministic, so replaying the agent's calls in order rebuilds the same T1, T2, ... sources."""
    if res["status"] != "ok":
        return res
    b = res["borrower_id"]
    tools.calls.clear()
    for s in res["steps"]:
        tools.run(s["tool"], s["args"])
    lines = [m["text"] + (f" [{', '.join(m['cites'])}]" if m["cites"] else "") for m in res["memo"]] + \
            [d["text"] for d in res["dropped"]]
    lines.sort(key=lambda l: l.lower().startswith("ask the borrower"))  # the question stays last
    signals = {s["signal_id"]: s for s in tools.cases[b]["signals"]}
    kept, dropped = validate("\n".join("- " + l for l in lines), signals, {x["id"]: x for x in tools.calls},
                             tools.facts(b))
    return dict(res, memo=kept, dropped=dropped, checks_reapplied=time.strftime("%Y-%m-%d"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/out/demo")
    ap.add_argument("--out", default="web/public/showcase/agent")
    ap.add_argument("--borrower", nargs="*", default=None)
    ap.add_argument("--top-review", type=int, default=8, help="also investigate this many 'needs more evidence' cases")
    ap.add_argument("--no-gleif", action="store_true")
    ap.add_argument("--backend", choices=["hf", "local"], default="hf",
                    help="hf: hosted open models via the Hugging Face router; local: run the model on this machine's GPU")
    ap.add_argument("--local-model", default="Qwen/Qwen3-8B")
    ap.add_argument("--revalidate", action="store_true",
                    help="re-apply the current checks to the memos already in --out; no model is called")
    a = ap.parse_args(argv)
    if a.revalidate:
        tools = Tools(a.data, json.load(open(os.path.join(a.data, "run", "cases.json"))), live_gleif=not a.no_gleif)
        index = []
        for f in sorted(glob.glob(os.path.join(a.out, "B*.json"))):
            res = revalidate(json.load(open(f)), tools)
            json.dump(res, open(f, "w"), indent=1)
            index.append(dict(borrower_id=res["borrower_id"], status=res["status"], model=res["model"],
                              lines=len(res["memo"]), dropped=len(res["dropped"]), tool_calls=len(res["steps"])))
        json.dump(index, open(os.path.join(a.out, "index.json"), "w"), indent=1)
        print(f"re-checked {len(index)} memos: {sum(r['lines'] for r in index)} lines kept, "
              f"{sum(r['dropped'] for r in index)} dropped")
        return
    token, ask, models = os.environ.get("HF_TOKEN"), None, MODELS
    if a.backend == "local":
        from bt.agent.local_model import LocalChat
        ask, models = LocalChat(a.local_model), [a.local_model]
    elif not token:
        sys.exit("HF_TOKEN is not set: put it in .env and run through scripts/with-env.sh")
    cases = json.load(open(os.path.join(a.data, "run", "cases.json")))
    tools = Tools(a.data, cases, live_gleif=not a.no_gleif)
    if a.borrower:
        targets = a.borrower
    else:
        by_p = sorted(cases, key=lambda c: -c["priority"])
        targets = [c["borrower_id"] for c in by_p if c["verdict"] == "LIKELY_FRAUD"] + \
                  [c["borrower_id"] for c in by_p if c["verdict"] == "NEEDS_MORE_EVIDENCE"][:a.top_review]
    os.makedirs(a.out, exist_ok=True)
    index_path = os.path.join(a.out, "index.json")
    index = {r["borrower_id"]: r for r in (json.load(open(index_path)) if os.path.exists(index_path) else [])}
    for b in targets:
        res = investigate(b, tools, token, models=models, ask=ask)
        json.dump(res, open(os.path.join(a.out, f"{b}.json"), "w"), indent=1)
        index[b] = dict(borrower_id=b, status=res["status"], model=res["model"], lines=len(res["memo"]),
                        dropped=len(res["dropped"]), tool_calls=len(res["steps"]))
        print(f"{b}: {res['status']} {res['model']} · {len(res['steps'])} tool calls · {len(res['memo'])} lines kept, "
              f"{len(res['dropped'])} dropped · {res.get('tokens', 0)} tokens" + (f" · {res['errors']}" if res["errors"] else ""))
        if res["status"] != "ok" and all(" 402 " in e for e in res["errors"]):
            print("out of inference credits: stopping")
            break
    json.dump(sorted(index.values(), key=lambda r: r["borrower_id"]), open(index_path, "w"), indent=1)


if __name__ == "__main__":
    main()
