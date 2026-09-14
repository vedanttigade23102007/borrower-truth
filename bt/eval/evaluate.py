"""Proof harness: how well does Borrower Truth catch planted fraud, and how early?

This is the ONLY module allowed to read labels.json.

Honesty rules:
- Rules were developed looking at seed 7 (the dev book). The reported numbers come
  from held-out seeds that were never inspected while tuning.
- The baseline is a quarterly sample audit using the same data, described below;
  it is not crippled to make us look better.
- Everything is synthetic: these numbers prove coverage of the documented
  mechanisms, not real-world catch rates.

Measures (design §8):
  1. catch rate, per borrower and per mechanism
  2. switch-off test: turn each system off, measure what is lost
  3. beyond PledgeCheck: frauds its four published checks never flag
  4. days earlier than the quarterly audit
  5. false alarms per 100 honest borrowers (at the end, and ever over 24 months)
  6. run time per month

    uv run python -m bt.eval.evaluate --seeds 101 102 103 104 105
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter

import duckdb

from bt.datagen.generate import FRAUD_MECHS, MONTHS
from bt.datagen.generate import main as generate
from bt.pipeline.run import run as pipeline

SYSTEMS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
ABLATE = SYSTEMS + ("SEC",)  # "SEC": every check built on public SEC data, switched off together
AUDIT_LOANS, AUDIT_INVOICES = 20, 10


def ensure_book(root, seed, borrowers):
    out = os.path.join(root, f"seed_{seed}")
    if not os.path.exists(os.path.join(out, "labels.json")):
        generate(["--borrowers", str(borrowers), "--seed", str(seed), "--out", out])
    return out


def flagged(c):
    return c["verdict"] == "LIKELY_FRAUD"


def mech_hits(c):
    return {f["mechanism"] for f in c["findings"] if f["confidence"] in ("high", "medium")}


def baseline_audit(data):
    """Quarterly field exam, the way it's commonly done without these systems:
    at each quarter end, pull AUDIT_LOANS eligible loans from the servicer system
    (flag if >= 1 is actually 60+ late or gone) and check AUDIT_INVOICES recent
    invoices (flag if >= 2 are unpaid past due or re-submitted with a new amount).
    Lien searches happen only at onboarding (month 0), which is common practice."""
    con = duckdb.connect()
    p = lambda t: f"read_parquet('{os.path.join(data, t)}.parquet')"
    first = {}
    for m in range(2, MONTHS, 3):
        loans = con.execute(f"""
            WITH s AS (SELECT borrower_id, asset_id, month,
                              row_number() OVER (PARTITION BY borrower_id ORDER BY hash(asset_id || 'field-exam' || {m})) AS k
                       FROM {p('tape')} WHERE month = {m} AND eligible_reported AND asset_id LIKE 'A-%')
            SELECT s.borrower_id FROM s LEFT JOIN {p('source_truth')} t ON t.asset_id = s.asset_id AND t.month = s.month
            WHERE s.k <= {AUDIT_LOANS} GROUP BY 1
            HAVING count(*) FILTER (WHERE t.asset_id IS NULL OR t.dpd_bucket_true >= 2) >= 1""").fetchall()
        inv = con.execute(f"""
            WITH i AS (SELECT borrower_id, invoice_number, issue_month, due_days, amount,
                              row_number() OVER (PARTITION BY borrower_id ORDER BY hash(invoice_id || 'confirm' || {m})) AS k
                       FROM {p('invoices')} WHERE pledged_month BETWEEN {m - 2} AND {m}),
                 dup AS (SELECT borrower_id, invoice_number FROM {p('invoices')} WHERE pledged_month <= {m}
                         GROUP BY 1, 2 HAVING count(DISTINCT amount) > 1),
                 paid AS (SELECT DISTINCT ref FROM {p('payments')} WHERE month <= {m})
            SELECT i.borrower_id FROM i
            LEFT JOIN dup ON dup.borrower_id = i.borrower_id AND dup.invoice_number = i.invoice_number
            LEFT JOIN paid ON paid.ref = i.invoice_number
            WHERE i.k <= {AUDIT_INVOICES}
            GROUP BY 1
            HAVING count(*) FILTER (WHERE dup.invoice_number IS NOT NULL
                   OR (paid.ref IS NULL AND i.issue_month + CAST(ceil(i.due_days / 30.0) AS INTEGER) + 1 <= {m})) >= 2""").fetchall()
        for (b,) in loans + inv:
            first.setdefault(b, m)
    return first


def pledgecheck_only(data):
    con = duckdb.connect()
    f = os.path.join(data, "pledgecheck.parquet")
    return {b for (b,) in con.execute(f"SELECT DISTINCT borrower_id FROM read_parquet('{f}') "
                                      "WHERE uniqueness = 'FAIL' OR completeness = 'FAIL'").fetchall()}


def evaluate_book(data):
    labels = json.load(open(os.path.join(data, "labels.json")))
    fraud = {b for b, v in labels.items() if v["fraud"]}
    honest = set(labels) - fraud

    # 24-month replay: the first month each borrower becomes a LIKELY_FRAUD case
    first, ever_flagged, secs = {}, set(), []
    for m in range(MONTHS):
        _, cases, met = pipeline(data, m)
        secs.append(met["total_seconds"])
        for c in cases:
            if flagged(c):
                first.setdefault(c["borrower_id"], m)
                ever_flagged.add(c["borrower_id"])
    final = {c["borrower_id"]: c for c in cases}

    caught = {b for b in fraud if flagged(final[b])}
    per_mech, per_mech_hit = Counter(), Counter()
    for b in fraud:
        for m in labels[b]["mechanisms"]:
            per_mech[m] += 1
            per_mech_hit[m] += m in mech_hits(final[b])

    # switch-off test
    ablation = {}
    for s in ABLATE:
        _, cases, _ = pipeline(data, MONTHS - 1, {s})
        fc = {c["borrower_id"]: c for c in cases}
        lost_b = [b for b in caught if not flagged(fc[b])]
        lost_m = sum(1 for b in fraud for m in labels[b]["mechanisms"]
                     if m in mech_hits(final[b]) and m not in mech_hits(fc[b]))
        ablation[s] = dict(borrowers_lost=len(lost_b), mechanism_detections_lost=lost_m)

    # top-decile precision: of the highest-priority 10% of the queue, how many are real frauds?
    ranked = sorted(final.values(), key=lambda c: -c["priority"])
    k = max(1, len(ranked) // 10)
    top_decile_fraud = sum(1 for c in ranked[:k] if c["borrower_id"] in fraud)
    # fix quality: does the suggested playbook address a mechanism that was actually planted?
    right_fix = sum(1 for b in caught if mech_hits(final[b]) & set(labels[b]["mechanisms"]))
    fix_total = sum(len(mech_hits(final[b])) for b in caught)
    fix_on_target = sum(len(mech_hits(final[b]) & set(labels[b]["mechanisms"])) for b in caught)

    base = baseline_audit(data)
    pc = pledgecheck_only(data)
    lead = []
    for b in fraud:
        if b in first and b in base:
            lead.append((base[b] - first[b]) * 30)
    return dict(
        borrowers=len(labels), fraud=len(fraud), honest=len(honest),
        honest_needing_review=sum(1 for b in honest if final[b]["verdict"] == "NEEDS_MORE_EVIDENCE"),
        fraud_needing_review=sum(1 for b in fraud if final[b]["verdict"] == "NEEDS_MORE_EVIDENCE"),
        top_decile=[top_decile_fraud, k], right_fix=right_fix, fix_on_target=[fix_on_target, fix_total],
        caught=len(caught), false_alarms_end=sum(1 for b in honest if flagged(final[b])),
        false_alarms_ever=len(ever_flagged & honest),
        per_mechanism={m: [per_mech_hit[m], per_mech[m]] for m in FRAUD_MECHS},
        per_pattern={p: [sum(1 for b in fraud if labels[b]["pattern"] == p and b in caught),
                         sum(1 for b in fraud if labels[b]["pattern"] == p)]
                     for p in sorted({labels[b]["pattern"] for b in fraud})},
        ablation=ablation,
        baseline_caught=len(fraud & set(base)), baseline_false_alarms=len(honest & set(base)),
        pledgecheck_caught=len(fraud & pc), beyond_pledgecheck=len(caught - pc),
        caught_never_by_baseline=len(caught - set(base)),
        lead_days=lead,
        detect_after_start_days=[(first[b] - labels[b]["start_month"]) * 30 for b in caught if b in first],
        seconds_per_month=round(statistics.mean(secs), 3),
    )


def summarize(results: dict) -> dict:
    tot = lambda k: sum(r[k] for r in results.values())
    fraud, honest = tot("fraud"), tot("honest")
    mech = {m: [sum(r["per_mechanism"][m][0] for r in results.values()),
                sum(r["per_mechanism"][m][1] for r in results.values())] for m in FRAUD_MECHS}
    patterns = sorted({p for r in results.values() for p in r["per_pattern"]})
    pat = {p: [sum(r["per_pattern"].get(p, [0, 0])[0] for r in results.values()),
               sum(r["per_pattern"].get(p, [0, 0])[1] for r in results.values())] for p in patterns}
    abl = {s: {k: sum(r["ablation"][s][k] for r in results.values()) for k in ("borrowers_lost", "mechanism_detections_lost")}
           for s in ABLATE if all(s in r["ablation"] for r in results.values())}
    lead = [d for r in results.values() for d in r["lead_days"]]
    after = [d for r in results.values() for d in r["detect_after_start_days"]]
    timing = Counter("before the effects start" if d < 0 else "same month" if d == 0 else
                     "1-3 months later" if d <= 90 else "over 3 months later" for d in after)
    td = [sum(r["top_decile"][0] for r in results.values()), sum(r["top_decile"][1] for r in results.values())]
    fo = [sum(r["fix_on_target"][0] for r in results.values()), sum(r["fix_on_target"][1] for r in results.values())]
    return dict(
        top_decile_precision=round(td[0] / max(td[1], 1), 3), top_decile=td,
        right_fix_rate=round(tot("right_fix") / max(tot("caught"), 1), 3),
        fix_on_target=fo, fix_on_target_rate=round(fo[0] / max(fo[1], 1), 3),
        honest_needing_review_per_100=round(100 * tot("honest_needing_review") / honest, 1),
        fraud_left_at_review=tot("fraud_needing_review"),
        detection_timing=dict(timing),
        seeds=list(results), borrowers=tot("borrowers"), fraud=fraud, honest=honest,
        caught=tot("caught"), catch_rate=round(tot("caught") / fraud, 3),
        false_alarms_per_100_end=round(100 * tot("false_alarms_end") / honest, 2),
        false_alarms_per_100_ever=round(100 * tot("false_alarms_ever") / honest, 2),
        per_mechanism=mech, per_pattern=pat, ablation=abl,
        baseline_caught=tot("baseline_caught"), baseline_catch_rate=round(tot("baseline_caught") / fraud, 3),
        baseline_false_alarms_per_100=round(100 * tot("baseline_false_alarms") / honest, 2),
        pledgecheck_caught=tot("pledgecheck_caught"), beyond_pledgecheck=tot("beyond_pledgecheck"),
        caught_never_by_baseline=tot("caught_never_by_baseline"),
        median_days_earlier_than_audit=statistics.median(lead) if lead else None, n_lead=len(lead),
        median_days_from_fraud_start_to_detection=statistics.median(after) if after else None,
        seconds_per_monthly_run=round(statistics.mean(r["seconds_per_month"] for r in results.values()), 3),
    )


def report_md(s: dict) -> str:
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else "–"
    lines = [
        "# Proof report: Borrower Truth on synthetic books",
        "",
        f"Held-out seeds {s['seeds']} · {s['borrowers']} borrowers · {s['fraud']} with planted fraud · {s['honest']} honest. "
        "**All data synthetic.** These numbers prove coverage of the documented mechanisms, not real-world catch rates.",
        "",
        "| Measure | Borrower Truth | Quarterly sample audit |",
        "|---|---|---|",
        f"| Frauds caught by month 24 | {pct(s['caught'], s['fraud'])} | {pct(s['baseline_caught'], s['fraud'])} |",
        f"| False alarms per 100 honest borrowers (final month) | {s['false_alarms_per_100_end']} | {s['baseline_false_alarms_per_100']} (ever) |",
        f"| False alarms per 100 honest borrowers (ever, any month) | {s['false_alarms_per_100_ever']} | |",
        f"| Median days earlier than the audit (frauds both caught, n={s['n_lead']}) | {s['median_days_earlier_than_audit']} | – |",
        f"| Frauds the audit never caught but we did | {s['caught_never_by_baseline']} | – |",
        f"| Top-decile precision (highest-priority 10% of the queue that are real frauds) | {pct(*s['top_decile'])} | |",
        f"| Caught frauds whose suggested fix targets a planted mechanism | {s['right_fix_rate']:.0%} | |",
        f"| Suggested fixes that target a planted mechanism (all fixes on caught frauds) | {pct(*s['fix_on_target'])} | |",
        f"| Honest borrowers routed to 'needs more evidence' (review load) per 100 | {s['honest_needing_review_per_100']} | |",
        f"| Planted frauds left at 'needs more evidence' (not missed, not flagged) | {s['fraud_left_at_review']} | |",
        f"| Frauds caught that PledgeCheck's four checks never flagged | {s['beyond_pledgecheck']} (PledgeCheck flagged {s['pledgecheck_caught']}) | |",
        f"| Mean run time, all borrowers, one month | {s['seconds_per_monthly_run']} s | |",
        "",
        "## When we caught it, relative to the fraud's first effects in the data",
        "",
        "| Timing | Frauds |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in sorted(s["detection_timing"].items())],
        "",
        "'Before the effects start' happens because precursors are public records that exist before the "
        "fraud shows up in loan or payment data: a shell company is formed, or a lien is filed. "
        "It is not a sign the system sees the future.",
        "",
        "## Per mechanism (finding at medium or high confidence)",
        "",
        "| Mechanism | Caught |", "|---|---|",
        *[f"| {m} | {pct(*v)} |" for m, v in s["per_mechanism"].items()],
        "",
        "## Per pattern", "", "| Pattern | Caught |", "|---|---|",
        *[f"| {p} | {pct(*v)} |" for p, v in s["per_pattern"].items()],
        "",
        "## Switch-off test: what is lost when one system is removed",
        "",
        "| System off | Fraud borrowers lost | Mechanism detections lost |", "|---|---|---|",
        *[f"| {k} | {v['borrowers_lost']} | {v['mechanism_detections_lost']} |" for k, v in s["ablation"].items()],
        "",
        "Every system that loses detections when switched off earns its place. "
        "Zero borrowers lost with a system off means the others overlap it (defence in depth), "
        "not that it is useless: check the mechanism column.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[101, 102, 103, 104, 105])
    ap.add_argument("--borrowers", type=int, default=120)
    ap.add_argument("--root", default="data/out/eval_v3")  # generator v3 books (data/out/eval holds the v2 books)
    ap.add_argument("--report", default="proof/REPORT.md")
    a = ap.parse_args(argv)
    t0 = time.time()
    results = {}
    for seed in a.seeds:
        data = ensure_book(a.root, seed, a.borrowers)
        results[seed] = evaluate_book(data)
        r = results[seed]
        print(f"seed {seed}: caught {r['caught']}/{r['fraud']}, false alarms {r['false_alarms_end']}/{r['honest']} "
              f"(ever {r['false_alarms_ever']}), baseline {r['baseline_caught']}/{r['fraud']}")
    s = summarize(results)
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    with open(a.report, "w") as f:
        f.write(report_md(s))
    with open(a.report.replace(".md", ".json"), "w") as f:
        json.dump(dict(summary=s, per_seed=results), f, indent=1)
    print(report_md(s))
    print(f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
