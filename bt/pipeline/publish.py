"""Adapter: post a pipeline run to the case service.

Fallback (design §12): retry with backoff; if the service stays down, the run is
parked in a dead-letter folder and can be replayed later with --replay. A
failed publish never loses results.

    uv run python -m bt.pipeline.publish --run data/out/demo/run
    uv run python -m bt.pipeline.publish --replay
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time
import urllib.request

DEAD_LETTER = "data/out/dead_letter"


def camel(o):
    if isinstance(o, dict):
        return {re.sub(r"_([a-z])", lambda m: m.group(1).upper(), k): camel(v) for k, v in o.items()}
    if isinstance(o, list):
        return [camel(x) for x in o]
    return o


def payload(run_dir: str) -> dict:
    cases = json.load(open(os.path.join(run_dir, "cases.json")))
    metrics = json.load(open(os.path.join(run_dir, "run_metrics.json")))
    return {"asOf": metrics.get("as_of", 23), "runMetrics": metrics, "cases": camel(cases)}


def post(url: str, body: dict, attempts: int = 4) -> dict:
    data = json.dumps(body, default=str).encode()
    delay = 0.5
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == attempts - 1:
                raise
            print(f"  publish attempt {i + 1} failed ({type(e).__name__}); retrying in {delay:.1f}s")
            time.sleep(delay)
            delay *= 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="data/out/demo/run")
    ap.add_argument("--url", default=os.environ.get("CASE_SERVICE_URL", "http://localhost:8081") + "/api/runs")
    ap.add_argument("--replay", action="store_true", help="re-send everything parked in the dead-letter folder")
    a = ap.parse_args(argv)
    if a.replay:
        for f in sorted(glob.glob(os.path.join(DEAD_LETTER, "*.json"))):
            print("replaying", f, post(a.url, json.load(open(f))))
            os.remove(f)
        return
    body = payload(a.run)
    try:
        print("published:", post(a.url, body))
    except Exception as e:
        os.makedirs(DEAD_LETTER, exist_ok=True)
        path = os.path.join(DEAD_LETTER, f"run_{body['asOf']}_{int(time.time())}.json")
        json.dump(body, open(path, "w"))
        print(f"case service unavailable ({type(e).__name__}); run parked in {path}, replay with --replay")


if __name__ == "__main__":
    main()
