"""Bridge: real-time S3 signals (Kafka topic `signals`) -> the case service.

Without this, the streaming worker's alerts never reach a human. The bridge
batches alerts (up to 200, or every 2 s) and posts them to /api/live-alerts,
where they appear on the borrower's case page and in the audit log.

Reliability: offsets are committed only after a batch is delivered or parked.
Delivery retries with backoff; if the case service stays down, the batch is
written to the dead-letter folder (replayable) so nothing is lost.

    uv run --extra stream python -m bt.stream.signal_bridge --api http://localhost:8081
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

from bt.common.metrics import push

DEAD_LETTER = "data/out/dead_letter_alerts"


def deliver(api: str, batch: list[dict], attempts: int = 4) -> bool:
    body = json.dumps([dict(borrowerId=a["borrower_id"], type=a["type"], txnId=a.get("txn_id"),
                            payerName=a.get("payer_name"), amount=a.get("amount") or 0.0,
                            entityId=a.get("entity_id"), detectedAt=a.get("detected_at") or time.time())
                       for a in batch]).encode()
    delay = 0.5
    for i in range(attempts):
        try:
            req = urllib.request.Request(f"{api}/api/live-alerts", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).close()
            return True
        except Exception:
            if i < attempts - 1:
                time.sleep(delay)
                delay *= 2
    return False


def park(batch: list[dict]):
    os.makedirs(DEAD_LETTER, exist_ok=True)
    with open(os.path.join(DEAD_LETTER, f"alerts_{int(time.time() * 1000)}.json"), "w") as f:
        json.dump(batch, f)


def main(argv=None):
    from confluent_kafka import Consumer

    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default=os.environ.get("KAFKA", "localhost:9092"))
    ap.add_argument("--api", default=os.environ.get("CASE_SERVICE_URL", "http://localhost:8081"))
    ap.add_argument("--group", default="signal-bridge")
    a = ap.parse_args(argv)
    c = Consumer({"bootstrap.servers": a.bootstrap, "group.id": a.group, "enable.auto.commit": False,
                  "auto.offset.reset": "earliest"})
    c.subscribe(["signals"])
    batch, last_flush, sent, parked = [], time.time(), 0, 0
    try:
        while True:
            for m in c.consume(num_messages=200, timeout=1.0):
                if not m.error():
                    try:
                        batch.append(json.loads(m.value()))
                    except ValueError:
                        parked += 1  # unreadable message: counted, skipped
            if batch and (len(batch) >= 200 or time.time() - last_flush > 2):
                if deliver(a.api, batch):
                    sent += len(batch)
                else:
                    park(batch)
                    parked += len(batch)
                c.commit(asynchronous=False)  # delivered or parked: safe to move on
                batch, last_flush = [], time.time()
                push("borrower_truth_bridge", [("bt_bridge_forwarded_total", {}, sent),
                                               ("bt_bridge_parked_total", {}, parked)])
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


if __name__ == "__main__":
    main()
