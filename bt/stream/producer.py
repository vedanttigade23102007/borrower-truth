"""Replay the synthetic bank payments as live Kafka events (topic `payments`).

Keyed by borrower_id, so adding partitions and workers scales S3 linearly.
Every event carries its produce time, so the worker can measure end-to-end
latency (payment arrives -> suspicious-payer signal).

    uv run --extra stream python -m bt.stream.producer --data data/out/demo --rate 2000
"""
from __future__ import annotations

import argparse
import json
import os
import time

import duckdb

TOPIC = "payments"


def main(argv=None):
    from confluent_kafka import Producer  # optional dependency: uv sync --extra stream

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/out/demo")
    ap.add_argument("--bootstrap", default=os.environ.get("KAFKA", "localhost:9092"))
    ap.add_argument("--rate", type=int, default=2000, help="events per second")
    ap.add_argument("--from-month", type=int, default=0)
    ap.add_argument("--to-month", type=int, default=23)
    a = ap.parse_args(argv)

    p = Producer({"bootstrap.servers": a.bootstrap, "linger.ms": 20, "enable.idempotence": True})
    f = os.path.join(a.data, "payments.parquet")
    cur = duckdb.connect().execute(
        f"SELECT txn_id, month, day, borrower_id, account_id, payer_id, payer_name, amount, memo, ref "
        f"FROM read_parquet('{f}') WHERE month BETWEEN ? AND ? ORDER BY month, day, txn_id", [a.from_month, a.to_month])
    cols = [d[0] for d in cur.description]
    sent, t0 = 0, time.time()
    while batch := cur.fetchmany(1000):
        for row in batch:
            ev = dict(zip(cols, row))
            ev["produced_at"] = time.time()
            p.produce(TOPIC, key=ev["borrower_id"], value=json.dumps(ev, default=float))
            sent += 1
        p.poll(0)
        ahead = sent / a.rate - (time.time() - t0)
        if ahead > 0:
            time.sleep(ahead)
    p.flush(30)
    print(f"produced {sent:,} payment events in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
