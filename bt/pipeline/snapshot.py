"""Freeze the case service's current state into static JSON for the web console.

The public demo (Vercel) has no backend; it reads this snapshot. Approvals made
in the static demo stay in the visitor's browser only, and the console says so.

    uv run python -m bt.pipeline.snapshot --out web/public/snapshot
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("CASE_SERVICE_URL", "http://localhost:8081") + "/api")
    ap.add_argument("--out", default="web/public/snapshot")
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(a.out, "case"), exist_ok=True)
    latest = get(f"{a.api}/runs/latest")
    cases = get(f"{a.api}/cases")
    json.dump(latest, open(os.path.join(a.out, "latest.json"), "w"), indent=1)
    json.dump(cases, open(os.path.join(a.out, "cases.json"), "w"), indent=1)
    json.dump(get(f"{a.api}/feedback"), open(os.path.join(a.out, "feedback.json"), "w"), indent=1)
    for c in cases:
        json.dump(get(f"{a.api}/cases/{c['borrowerId']}"), open(os.path.join(a.out, "case", f"{c['borrowerId']}.json"), "w"))
    print(f"snapshot: {len(cases)} cases -> {a.out}")


if __name__ == "__main__":
    main()
