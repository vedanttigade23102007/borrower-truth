"""Replay recorded decisions and prove they are identical, or show what changed.

    uv run python -m bt.pipeline.replay --data data/out/eval/seed_201 --run data/out/eval/seed_201/run

Reads the run's manifest.json and decision_records.jsonl, recomputes every
decision from the same book, and compares result digests. Reports:
- which inputs changed since the recording (by fingerprint), if any
- whether the rule code or git commit changed
- every decision that came out different, with old vs new verdict
Exit code 0 only if every decision replays identically.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from bt.pipeline import dq, record
from bt.pipeline.run import run as pipeline


def replay(data_dir: str, run_dir: str) -> dict:
    man = json.load(open(os.path.join(run_dir, "manifest.json")))
    recs = {r["borrower_id"]: r for r in map(json.loads, open(os.path.join(run_dir, "decision_records.jsonl")))}
    overrides, _ = dq.stage(data_dir)
    # replay with the document module set as it was recorded (older records: on if they read the document file)
    doc = man.get("document_model", man["inputs"].get("doc_reads", "absent") != "absent")
    now = record.manifest(data_dir, overrides, man["as_of"], doc)
    inputs_changed = sorted(k for k in man["inputs"] if man["inputs"][k] != now["inputs"].get(k))
    _, cases, _ = pipeline(data_dir, man["as_of"], document_model=doc)
    new = {c["borrower_id"]: c for c in cases}
    diffs = []
    for b, r in sorted(recs.items()):
        c = new.get(b)
        if c is None or c["decision"]["result_digest"] != r["result_digest"]:
            diffs.append(dict(borrower_id=b, recorded=r["verdict"], replayed=c["verdict"] if c else None,
                              recorded_findings=r["findings"],
                              replayed_findings=sorted(f["mechanism"] for f in c["findings"]) if c else None))
    return dict(replayed=len(recs), identical=len(recs) - len(diffs), different=diffs,
                inputs_changed=inputs_changed, rules_changed=man["rule_version"] != now["rule_version"],
                code_recorded=man["code_version"], code_now=now["code_version"],
                inputs_digest=man["inputs_digest"], rule_version=man["rule_version"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--run", default=None)
    a = ap.parse_args(argv)
    rep = replay(a.data, a.run or os.path.join(a.data, "run"))
    out = os.path.join(a.run or os.path.join(a.data, "run"), "replay_report.json")
    json.dump(rep, open(out, "w"), indent=1)
    print(f"replayed {rep['replayed']} decisions: {rep['identical']} identical, {len(rep['different'])} different")
    print(f"  inputs changed since recording: {rep['inputs_changed'] or 'none'} · rules changed: {rep['rules_changed']}"
          f" · code {rep['code_recorded']} -> {rep['code_now']}")
    for d in rep["different"][:10]:
        print(f"  {d['borrower_id']}: {d['recorded']} -> {d['replayed']}")
    sys.exit(0 if not rep["different"] else 1)


if __name__ == "__main__":
    main()
