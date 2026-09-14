"""Decision replay record: every verdict carries the fingerprints of exactly the
inputs, rules and code that produced it.

Why: a bank's model-risk team must be able to take any past decision and
recompute it. Each case gets:
- inputs_digest  : SHA-256 over every input file the run read (after the data-quality gate)
- rule_version   : SHA-256 over the source of the seven systems, the combiner and the gate
- code_version   : the git commit (+ "+local-changes" if the rule code is uncommitted)
- result_digest  : SHA-256 over the decision itself (verdict, findings, signal IDs, priority)
`bt.pipeline.replay` recomputes a run and shows the result digests are identical,
or names exactly which input, rule or code changed.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess

from bt.systems.base import VIEWS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULE_GLOBS = ("bt/systems/*.py", "bt/combiner/*.py", "bt/pipeline/dq.py", "bt/pipeline/run.py",
              "bt/sec/benchmark.py", "data/calibration/absee_auto.json")  # measured peer rates are part of the rules
EXTRA_INPUTS = ("doc_reads",)
_hash_cache: dict[tuple, str] = {}


def file_sha(path: str) -> str:
    st = os.stat(path)
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _hash_cache:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _hash_cache[key] = h.hexdigest()[:16]
    return _hash_cache[key]


def input_fingerprints(data_dir: str, overrides: dict[str, str]) -> dict[str, str]:
    out = {}
    for name in sorted({f for f, _ in VIEWS.values()} | set(EXTRA_INPUTS)):
        path = overrides.get(name, os.path.join(data_dir, f"{name}.parquet"))
        if name in overrides and not path:
            out[name] = "quarantined:empty"
        elif path and os.path.exists(path):
            out[name] = file_sha(path)
        else:
            out[name] = "absent"
    return out


def rule_version() -> str:
    h = hashlib.sha256()
    for pattern in RULE_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            h.update(os.path.relpath(path, ROOT).encode())
            h.update(open(path, "rb").read())
    return h.hexdigest()[:12]


def code_version() -> str:
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "bt"], capture_output=True, text=True,
                               timeout=5).stdout.strip()
        return (head or "unknown") + ("+local-changes" if dirty else "")
    except Exception:
        return "unknown"


def case_core(c: dict) -> dict:
    """The decision itself, in a canonical form (order-independent)."""
    return {"verdict": c["verdict"], "priority": c["priority"],
            "findings": sorted([f["mechanism"], f["confidence"]] for f in c["findings"]),
            "signals": sorted(s["signal_id"] for s in c["signals"])}


def result_digest(c: dict) -> str:
    return hashlib.sha256(json.dumps(case_core(c), sort_keys=True).encode()).hexdigest()[:12]


def manifest(data_dir: str, overrides: dict[str, str], as_of: int) -> dict:
    fp = input_fingerprints(data_dir, overrides)
    return {"as_of": as_of, "inputs": fp,
            "inputs_digest": hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:12],
            "rule_version": rule_version(), "code_version": code_version()}


def stamp(cases: list[dict], man: dict) -> None:
    for c in cases:
        d = result_digest(c)
        c["decision"] = {"decision_id": f"{c['borrower_id']}-m{man['as_of']}-{d}", "result_digest": d,
                         "inputs_digest": man["inputs_digest"], "rule_version": man["rule_version"],
                         "code_version": man["code_version"], "as_of": man["as_of"]}
