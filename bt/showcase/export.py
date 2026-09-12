"""Export the public "Data" section: samples, one fraud story, documents, answer key.

Everything exported is SYNTHETIC and deliberately partial: 10 sample rows per
table (never the full dataset), a handful of documents, and results. No code,
no rules or thresholds, no model weights leave the repo.

Uses the demo book, the one the console shows, so every row in the answer key
can be clicked through to its case. The held-out results (five books the rules
never saw) are added from proof/REPORT.json as the honest test.

    uv run python -m bt.showcase.export
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

import duckdb

TABLES = {
    "borrowers": ("Borrowers", "The finance companies Wells Fargo lends to (car lenders, invoice-based businesses, mortgage lenders).",
                  {"borrower_id": "ID used everywhere", "name": "company name", "btype": "kind of lending business",
                   "state": "US state", "facility_limit": "size of the credit line ($)"}),
    "entities": ("Company registry", "Every company the system knows about: borrowers, their affiliates, lenders, customers. Like a state business register.",
                 {"entity_id": "registry ID", "name": "legal name", "kind": "borrower / company / lender / debtor / holding",
                  "officer_person_id": "who runs it", "address": "registered address",
                  "formed_month": "when it was formed (month of the timeline)", "has_operations": "does it actually do business?"}),
    "tape": ("Loan file (tape)", "What the borrower reports each month about the loans it pledged as collateral.",
             {"month": "month of the timeline (0-23)", "facility_id": "which Wells Fargo credit line", "asset_id": "loan ID",
              "vin": "vehicle ID (synthetic, starts with SYN)", "balance": "amount owed ($)",
              "dpd_bucket_reported": "reported lateness: 0 current, 1 = 30 days, 2 = 60, 3 = 90+",
              "deferred_flag": "payment pause reported", "eligible_reported": "counts toward borrowing"}),
    "source_truth": ("Servicer system", "What the borrower's own loan system really says. The system samples it the way an auditor would.",
                     {"month": "month", "asset_id": "loan ID", "dpd_bucket_true": "real lateness", "balance_true": "real balance ($)"}),
    "payments": ("Bank payments", "Money arriving in the collection account Wells Fargo controls.",
                 {"txn_id": "transaction ID", "month": "month", "payer_name": "who sent it (as the bank sees it)",
                  "amount": "amount ($)", "memo": "reference text", "ref": "loan or invoice it pays"}),
    "invoices": ("Invoices", "Invoices pledged as collateral by invoice-based borrowers.",
                 {"invoice_number": "the borrower's number", "debtor_name": "the customer who owes it",
                  "amount": "amount ($)", "issue_month": "issued", "due_days": "payment terms", "facility_id": "credit line"}),
    "ucc_filings": ("Lien filings (UCC)", "Public records of who has a claim on a company's assets. Names and addresses, no IDs.",
                    {"debtor_name": "company the lien is against", "debtor_address": "its address on the filing",
                     "secured_party_name": "the lender holding the lien", "collateral_desc": "what is pledged",
                     "filed_month": "when (negative = before the timeline)"}),
    "court_records": ("Court records", "Judgments against companies.",
                      {"defendant_name": "company", "plaintiff": "who sued", "amount": "judgment ($)", "month": "when"}),
    "financials": ("Financial statements", "What the borrower reports each quarter.",
                   {"quarter": "quarter (0-7)", "revenue_reported": "revenue ($)", "receivables_reported": "receivables ($)",
                    "debt_reported": "debt ($)", "covenant_metric_reported": "covenant ratio",
                    "covenant_threshold": "minimum allowed"}),
    "disclosures": ("Disclosures", "What the borrower told Wells Fargo: its debts, affiliates, payment-pause programmes.",
                    {"kind": "debt / related_party / deferment_program", "counterparty_entity_id": "who", "note": "detail"}),
    "pledgecheck": ("PledgeCheck results (simulated)", "Setpoint PledgeCheck's four published checks, for borrowers enrolled in it.",
                    {"month": "month", "uniqueness": "collateral in only one facility?", "completeness": "collections match reports?"}),
}


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, [(round(v, 2) if isinstance(v, float) else v) for v in r])) for r in cur.fetchall()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="data/out/demo")
    ap.add_argument("--docs", default="data/out/docs_score/demo")
    ap.add_argument("--report", default="proof/REPORT.json")
    ap.add_argument("--out", default="web/public/showcase")
    a = ap.parse_args(argv)
    con = duckdb.connect()
    p = lambda t: f"read_parquet('{os.path.join(a.book, t)}.parquet')"
    labels = json.load(open(os.path.join(a.book, "labels.json")))
    cases = {c["borrower_id"]: c for c in json.load(open(os.path.join(a.book, "run", "cases.json")))}
    os.makedirs(os.path.join(a.out, "docs"), exist_ok=True)

    # --- the story: a caught First Brands-style borrower (disguised receipts through linked shells)
    def found(b):
        return {f["mechanism"] for f in cases[b]["findings"] if f["confidence"] in ("high", "medium")}
    candidates = [b for b, v in sorted(labels.items()) if "DISGUISED_RECEIPTS" in v["mechanisms"]
                  and "RELATED_SHELLS" in v["mechanisms"] and cases[b]["verdict"] == "LIKELY_FRAUD"
                  and "DISGUISED_RECEIPTS" in found(b)]
    story_b = sorted(candidates, key=lambda b: (labels[b]["pattern"] != "first_brands_like", b))[0]
    ent = rows(con, f"SELECT e.* FROM {p('borrowers')} b JOIN {p('entities')} e USING (entity_id) WHERE borrower_id = '{story_b}'")[0]
    registry = rows(con, f"SELECT entity_id, name, kind, officer_person_id, has_operations, formed_month, address "
                         f"FROM {p('entities')} WHERE officer_person_id = '{ent['officer_person_id']}' ORDER BY formed_month")
    names = [r["name"] for r in registry]
    shells = [r for r in registry if r["kind"] == "company" and not r["has_operations"]]
    shell_names = "', '".join(r["name"].replace("'", "''") for r in shells) or "__none__"
    pay_month = rows(con, f"SELECT max(month) AS m FROM {p('payments')} WHERE borrower_id='{story_b}' AND payer_name IN ('{shell_names}')")[0]["m"]
    payments = rows(con, f"""(SELECT month, payer_name, amount, memo FROM {p('payments')}
                              WHERE borrower_id='{story_b}' AND month={pay_month} AND payer_name IN ('{shell_names}') ORDER BY amount DESC LIMIT 3)
                             UNION ALL
                             (SELECT month, payer_name, amount, memo FROM {p('payments')}
                              WHERE borrower_id='{story_b}' AND month={pay_month} AND payer_name NOT IN ('{shell_names}') ORDER BY txn_id LIMIT 3)""")
    liens = rows(con, "SELECT debtor_name, secured_party_name, collateral_desc, filed_month FROM " + p('ucc_filings')
                 + " WHERE debtor_name IN ('" + "', '".join(n.replace("'", "''") for n in names) + "') ORDER BY filed_month")
    fin = rows(con, f"SELECT quarter, revenue_reported, covenant_metric_reported, covenant_threshold FROM {p('financials')} "
                    f"WHERE borrower_id='{story_b}' ORDER BY quarter")
    c = cases[story_b]
    story = dict(borrower_id=story_b, name=ent["name"], planted=labels[story_b]["mechanisms"], pattern=labels[story_b]["pattern"],
                 fraud_start_month=labels[story_b]["start_month"], registry=registry, payments=payments, liens=liens,
                 financials=fin, verdict=c["verdict"], headline=c["headline"], findings=c["findings"], signals=c["signals"],
                 decision=c.get("decision"))
    json.dump(story, open(os.path.join(a.out, "story.json"), "w"), indent=1, default=str)

    # --- tables: dictionary + 10 sample rows (story borrower first, then an honest one), never the full data
    honest = next(b for b, v in sorted(labels.items()) if not v["fraud"] and cases[b]["verdict"] == "NO_ISSUE")
    tables = []
    for t, (title, what, cols) in TABLES.items():
        f = os.path.join(a.book, f"{t}.parquet")
        if not os.path.exists(f):
            continue
        n = con.execute(f"SELECT count(*) FROM {p(t)}").fetchone()[0]
        schema = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {p(t)}").fetchall()]
        keep = [col for col in cols if col in schema]
        if "borrower_id" in schema:
            sample = rows(con, f"SELECT {', '.join(keep)} FROM {p(t)} WHERE borrower_id IN ('{story_b}', '{honest}') "
                               f"ORDER BY borrower_id = '{story_b}' DESC, 1 LIMIT 10")
        elif t == "entities":
            sample = registry[:5] + rows(con, f"SELECT {', '.join(keep)} FROM {p(t)} WHERE kind = 'lender' ORDER BY entity_id LIMIT 5")
            sample = [{k: r.get(k) for k in keep} for r in sample]
        else:
            sample = rows(con, f"SELECT {', '.join(keep)} FROM {p(t)} ORDER BY 1 LIMIT 10")
        tables.append(dict(table=t, title=title, what=what, rows=n, columns=[dict(name=k, meaning=cols[k]) for k in keep],
                           sample=sample))
    json.dump(dict(book="the demo book shown in the console", borrowers=len(labels),
                   total_rows=sum(t["rows"] for t in tables), tables=tables),
              open(os.path.join(a.out, "tables.json"), "w"), indent=1, default=str)

    # --- answer key: planted vs found, for every borrower, misses included
    key, counts = [], {}
    for b, v in sorted(labels.items()):
        cs = cases[b]
        got = sorted(found(b))
        if v["fraud"]:
            status = "caught" if cs["verdict"] == "LIKELY_FRAUD" else ("sent to review" if cs["verdict"] == "NEEDS_MORE_EVIDENCE" else "missed")
        else:
            status = {"LIKELY_FRAUD": "false alarm", "NEEDS_MORE_EVIDENCE": "worth a look (honest)"}.get(cs["verdict"], "cleared")
        counts[status] = counts.get(status, 0) + 1
        key.append(dict(borrower_id=b, planted=sorted(v["mechanisms"]), lookalikes=sorted(v["benign"]), verdict=cs["verdict"],
                        found=got, right_mechanisms=sorted(set(got) & set(v["mechanisms"])), status=status,
                        priority=cs["priority"]))
    rep = json.load(open(a.report))
    heldout = [dict(seed=int(s), borrowers=v["borrowers"], fraud=v["fraud"], caught=v["caught"],
                    sent_to_review=v["fraud_needing_review"], missed=v["fraud"] - v["caught"] - v["fraud_needing_review"],
                    false_alarms=v["false_alarms_end"], honest_worth_a_look=v["honest_needing_review"],
                    per_mechanism=v["per_mechanism"]) for s, v in sorted(rep["per_seed"].items())]
    json.dump(dict(counts=counts, borrowers=key, heldout=heldout), open(os.path.join(a.out, "answer_key.json"), "w"), indent=1)

    # --- documents: tampered (caught), clean, and one honest false flag
    reads = {r["invoice_id"]: r for r in rows(con, f"SELECT * FROM {p('doc_reads')}")}
    dlabels = {json.loads(l)["invoice_id"]: json.loads(l) for l in open(os.path.join(a.docs, "doc_labels.jsonl"))}
    pick = ([i for i in sorted(dlabels) if dlabels[i]["tampered"] and reads[i]["doc_mismatch"]][:3]
            + [i for i in sorted(dlabels) if not dlabels[i]["tampered"] and not reads[i]["doc_mismatch"]][:2]
            + [i for i in sorted(dlabels) if not dlabels[i]["tampered"] and reads[i]["doc_mismatch"]][:1])
    docs = []
    for i in pick:
        shutil.copy(os.path.join(a.docs, f"{i}.png"), os.path.join(a.out, "docs", f"{i}.png"))
        r, l = reads[i], dlabels[i]
        docs.append(dict(invoice_id=i, borrower_id=r["borrower_id"], image=f"/showcase/docs/{i}.png",
                         read_total=r["read_total"], first_read=r["read_total_first"], second_look=r["reread"],
                         record_amount=r["record_amount"], flagged=r["doc_mismatch"], truly_tampered=l["tampered"],
                         outcome=("tampered, caught" if l["tampered"] and r["doc_mismatch"] else
                                  "clean, passed" if not l["tampered"] and not r["doc_mismatch"] else
                                  "clean but flagged (a model misread: a person checks it)")))
    json.dump(docs, open(os.path.join(a.out, "documents.json"), "w"), indent=1)
    # --- decision replay: the manifest and the replay report of the run the console shows
    run = os.path.join(a.book, "run")
    if os.path.exists(os.path.join(run, "replay_report.json")):
        man, rr = (json.load(open(os.path.join(run, f))) for f in ("manifest.json", "replay_report.json"))
        json.dump(dict(replayed=rr["replayed"], identical=rr["identical"], different=len(rr["different"]),
                       inputs_changed=rr["inputs_changed"], rules_changed=rr["rules_changed"], inputs=man["inputs"],
                       inputs_digest=man["inputs_digest"], rule_version=man["rule_version"],
                       code_version=man["code_version"]), open(os.path.join(a.out, "replay.json"), "w"), indent=1)
    print(f"showcase -> {a.out}: story {story_b}, {len(tables)} tables, answer key {counts}, {len(docs)} documents")


if __name__ == "__main__":
    main()
