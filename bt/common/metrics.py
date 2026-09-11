"""Push run metrics to a Prometheus Pushgateway for the live operations dashboard.

Fallback: if PUSHGATEWAY_URL is unset or the gateway is down, metrics are only
written to the run folder. Monitoring must never break the pipeline.
"""
from __future__ import annotations

import os
import urllib.request


def _line(name, labels, value):
    lab = ",".join(f'{k}="{v}"' for k, v in labels.items())
    return f"{name}{{{lab}}} {value}\n" if lab else f"{name} {value}\n"


def push(job: str, samples: list[tuple[str, dict, float]], url: str | None = None) -> bool:
    url = url or os.environ.get("PUSHGATEWAY_URL")
    if not url:
        return False
    body = "".join(_line(n, l, v) for n, l, v in samples).encode()
    try:
        req = urllib.request.Request(f"{url}/metrics/job/{job}", data=body, method="PUT",
                                     headers={"Content-Type": "text/plain; version=0.0.4"})
        urllib.request.urlopen(req, timeout=3).close()
        return True
    except Exception:
        return False


def pipeline_samples(metrics: dict, cases: list[dict]) -> list[tuple[str, dict, float]]:
    out = []
    for name, m in metrics.items():
        if isinstance(m, dict) and "seconds" in m:
            out.append(("bt_system_seconds", {"system": name}, m["seconds"]))
            out.append(("bt_system_up", {"system": name}, 1 if m["status"] == "ok" else 0))
            out.append(("bt_system_signals", {"system": name}, m.get("signals", m.get("cases", 0))))
    verdicts: dict[str, int] = {}
    for c in cases:
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    for v, n in verdicts.items():
        out.append(("bt_cases", {"verdict": v}, n))
    out.append(("bt_pipeline_total_seconds", {}, metrics.get("total_seconds", 0)))
    out.append(("bt_pipeline_as_of_month", {}, metrics.get("as_of", 0)))
    return out
