"""Run all seven systems in feed order, then the combiner.

Order: S6 (relationships) first, because S1/S3/S5 widen their search with it;
then S1-S5; then S7, which consumes S3/S4/S5; then the combiner.

Fallbacks (design §12): every system runs isolated with a time budget. If one
fails or times out, the run continues, the failure is recorded in `coverage`,
and every case says which checks were unavailable. `--fail S4` simulates a crash
for the break-it demo.

    uv run python -m bt.pipeline.run --data data/out/demo --out data/out/demo/run
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time

import pyarrow as pa
import pyarrow.parquet as pq

from bt.combiner.combine import build_cases
from bt.pipeline import dq, record
from bt.common.metrics import pipeline_samples, push
from bt.systems import (s1_collateral, s2_tape_source, s3_cash, s4_invoices, s5_hidden_debt,
                        s6_relationships, s7_financial)
from bt.systems.base import Ctx

TIME_BUDGET_S = 120


class SystemFailure(Exception):
    pass


def _guarded(ctx: Ctx, name: str, fn, simulate_fail: set[str], metrics: dict):
    t0 = time.perf_counter()
    timer = threading.Timer(TIME_BUDGET_S, ctx.con.interrupt)
    timer.start()
    try:
        if name in simulate_fail:
            raise SystemFailure(f"{name}: simulated crash (break-it demo)")
        out = fn()
        metrics[name] = dict(status="ok", seconds=round(time.perf_counter() - t0, 3), signals=len(out))
        return out
    except Exception as e:  # isolate: one system failing never stops the others
        metrics[name] = dict(status="unavailable", seconds=round(time.perf_counter() - t0, 3), signals=0,
                             error=f"{type(e).__name__}: {e}"[:300])
        return []
    finally:
        timer.cancel()


def run(data_dir: str, as_of: int = 23, simulate_fail: set[str] | None = None, materialize: bool = True):
    simulate_fail = simulate_fail or set()
    t0 = time.perf_counter()
    overrides, dq_report = dq.stage(data_dir)  # quarantine bad files before anything reads them
    ctx = Ctx(data_dir, as_of, materialize=materialize, overrides=overrides)
    metrics: dict = {"data_quality": dq_report}
    signals = []
    signals += _guarded(ctx, "S6", lambda: s6_relationships.run(ctx), simulate_fail, metrics)
    if metrics["S6"]["status"] != "ok":  # degraded mode: downstream systems search the borrower only
        ctx.con.execute("CREATE OR REPLACE TABLE related AS SELECT NULL::VARCHAR AS borrower_id, NULL::VARCHAR AS entity_id, "
                        "NULL::VARCHAR AS name, NULL::VARCHAR AS kind, NULL::BOOLEAN AS has_operations, "
                        "NULL::BIGINT AS formed_month, NULL::BOOLEAN AS same_owner, NULL::BOOLEAN AS same_address, "
                        "NULL::BOOLEAN AS disclosed, NULL::BOOLEAN AS in_gleif WHERE false")
    signals += _guarded(ctx, "S1", lambda: s1_collateral.run(ctx), simulate_fail, metrics)
    signals += _guarded(ctx, "S2", lambda: s2_tape_source.run(ctx), simulate_fail, metrics)
    signals += _guarded(ctx, "S3", lambda: s3_cash.run(ctx), simulate_fail, metrics)
    s4 = _guarded(ctx, "S4", lambda: s4_invoices.run(ctx), simulate_fail, metrics)
    signals += s4
    signals += _guarded(ctx, "S5", lambda: s5_hidden_debt.run(ctx), simulate_fail, metrics)
    upstream = dict(s5_undisclosed=ctx.shared.get("s5_undisclosed", {}), s4_flags={})
    for s in s4:
        upstream["s4_flags"].setdefault(s.entity_id, []).append(s.signal_id)
    signals += _guarded(ctx, "S7", lambda: s7_financial.run(ctx, upstream), simulate_fail, metrics)

    coverage = {k: v["status"] for k, v in metrics.items() if isinstance(v, dict) and "status" in v}
    q = dq_report["quarantined"]
    coverage["data"] = ("quarantined: " + ", ".join(f"{t} ({v['using']})" for t, v in q.items())) if q else "ok"
    coverage["documents"] = ctx.shared.get("documents", "unavailable (rule checks only)")
    borrowers = [r["borrower_id"] for r in ctx.rows("SELECT borrower_id FROM borrowers ORDER BY 1")]
    t1 = time.perf_counter()
    cases = build_cases(signals, coverage, ctx.explanations, borrowers)
    man = record.manifest(data_dir, overrides, as_of)  # replay record: inputs, rules, code
    record.stamp(cases, man)
    metrics["manifest"] = man
    metrics["combiner"] = dict(status="ok", seconds=round(time.perf_counter() - t1, 3), cases=len(cases))
    metrics["total_seconds"] = round(time.perf_counter() - t0, 3)
    metrics["as_of"] = as_of
    ctx.con.close()
    return signals, cases, metrics


def write(out_dir, signals, cases, metrics):
    os.makedirs(out_dir, exist_ok=True)
    rows = [s.row() for s in signals]
    if rows:
        pq.write_table(pa.Table.from_pylist(rows), os.path.join(out_dir, "signals.parquet"))
    with open(os.path.join(out_dir, "cases.json"), "w") as f:
        json.dump(cases, f, indent=1, default=str)
    with open(os.path.join(out_dir, "run_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=1)
    if "manifest" in metrics:
        with open(os.path.join(out_dir, "manifest.json"), "w") as f:
            json.dump(metrics["manifest"], f, indent=1)
        with open(os.path.join(out_dir, "decision_records.jsonl"), "w") as f:
            for c in cases:
                f.write(json.dumps(dict(c["decision"], borrower_id=c["borrower_id"], verdict=c["verdict"],
                                        findings=sorted(x["mechanism"] for x in c["findings"]))) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/out/demo")
    ap.add_argument("--out", default=None)
    ap.add_argument("--as-of", type=int, default=23)
    ap.add_argument("--fail", nargs="*", default=[], help="simulate a crash in these systems, e.g. --fail S4")
    a = ap.parse_args(argv)
    signals, cases, metrics = run(a.data, a.as_of, set(a.fail))
    write(a.out or os.path.join(a.data, "run"), signals, cases, metrics)
    if push("borrower_truth_pipeline", pipeline_samples(metrics, cases)):
        print("  metrics pushed to Pushgateway")
    counts = {}
    for c in cases:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    print(f"as_of month {a.as_of}: {len(signals)} signals, {len(cases)} cases {counts}")
    for k, v in metrics.items():
        if isinstance(v, dict) and "status" in v:
            print(f"  {k:9} {v['status']:12} {v['seconds']:>7.3f}s  {v.get('signals', v.get('cases', ''))}"
                  + (f"  ({v['error']})" if "error" in v else ""))
    q = metrics["data_quality"]["quarantined"]
    print("  data      " + ("ok" if not q else "QUARANTINED " + ", ".join(f"{t}: {v['issues'][0]} -> {v['using']}"
                                                                   for t, v in q.items())))
    print(f"  total {metrics['total_seconds']:.2f}s")


if __name__ == "__main__":
    main()
