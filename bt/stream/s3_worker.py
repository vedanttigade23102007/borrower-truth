"""Streaming S3: flag a suspicious payer seconds after the payment lands.

The batch S3 answers "who paid?" once a night. This worker answers it per event.
Reference data (known obligors and debtors, the company registry, S6's linked
companies) comes from the nightly batch and is refreshed periodically.

Reliability (design §12):
- at-least-once: offsets are committed only after a batch is processed
- idempotent: duplicate deliveries are dropped by txn_id
- poison messages go to `payments.dlq` with the error; the worker keeps running
- metrics (throughput, latency p50/p95, DLQ count, unknown-payer events) go to
  the Pushgateway every few seconds for the live dashboard

    uv run --extra stream python -m bt.stream.s3_worker --data data/out/demo
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import time

from bt.common.metrics import push
from bt.systems import s6_relationships
from bt.systems.base import Ctx

REFRESH_S = 300


class Reference:
    """Known payers per borrower + who unknown payers really are. Built from the batch data."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.load()

    def load(self):
        ctx = Ctx(self.data_dir, as_of=23)
        s6_relationships.run(ctx)
        self.obligors = {(r["borrower_id"], r["obligor_id"]) for r in ctx.rows(
            "SELECT DISTINCT borrower_id, obligor_id FROM tape")}
        self.debtors = {(r["borrower_id"], r["dn"]) for r in ctx.rows(
            "SELECT DISTINCT borrower_id, norm(debtor_name) AS dn FROM invoices")}
        self.entities = {r["pn"]: r for r in ctx.rows("SELECT norm(name) AS pn, entity_id, kind, name FROM entities")}
        self.related = {(r["borrower_id"], r["entity_id"]): r["disclosed"] for r in ctx.rows("SELECT * FROM related")}
        ctx.con.close()
        self.loaded_at = time.time()

    @staticmethod
    def norm(s: str) -> str:
        import re
        return re.sub(r" +", " ", re.sub(r"[^A-Z0-9 ]", "", (s or "").upper())).strip()

    def classify(self, ev: dict):
        b = ev["borrower_id"]
        if (b, ev["payer_id"]) in self.obligors or (b, self.norm(ev["payer_name"])) in self.debtors:
            return None
        ent = self.entities.get(self.norm(ev["payer_name"]))
        if ent and (b, ent["entity_id"]) in self.related:
            if self.related[(b, ent["entity_id"])]:
                return None  # disclosed affiliate
            return "RELATED_PARTY_INFLOW", ent
        if ent and ent["kind"] == "lender":
            return "LENDER_FUNDS_AS_RECEIPTS", ent
        return "NON_OBLIGOR_PAYER", ent


def main(argv=None):
    from confluent_kafka import Consumer, Producer

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/out/demo")
    ap.add_argument("--bootstrap", default=os.environ.get("KAFKA", "localhost:9092"))
    ap.add_argument("--group", default="s3-cash-provenance")
    a = ap.parse_args(argv)

    ref = Reference(a.data)
    consumer = Consumer({"bootstrap.servers": a.bootstrap, "group.id": a.group, "enable.auto.commit": False,
                         "auto.offset.reset": "earliest"})
    producer = Producer({"bootstrap.servers": a.bootstrap, "enable.idempotence": True})
    consumer.subscribe(["payments"])

    seen = collections.OrderedDict()  # txn_id dedupe window
    lat = collections.deque(maxlen=5000)
    counts = collections.Counter()
    last_push = time.time()
    try:
        while True:
            msgs = consumer.consume(num_messages=500, timeout=1.0)
            for m in msgs:
                if m.error():
                    counts["kafka_errors"] += 1
                    continue
                try:
                    ev = json.loads(m.value())
                    if ev["txn_id"] in seen:
                        counts["duplicates"] += 1
                        continue
                    seen[ev["txn_id"]] = True
                    if len(seen) > 200_000:
                        seen.popitem(last=False)
                    res = ref.classify(ev)
                    counts["events"] += 1
                    if res:
                        typ, ent = res
                        counts[f"signal_{typ}"] += 1
                        producer.produce("signals", key=ev["borrower_id"], value=json.dumps(dict(
                            system="S3", type=typ, borrower_id=ev["borrower_id"], txn_id=ev["txn_id"],
                            payer_name=ev["payer_name"], amount=ev["amount"],
                            entity_id=ent["entity_id"] if ent else None, detected_at=time.time())))
                    lat.append(time.time() - ev.get("produced_at", time.time()))
                except Exception as e:  # poison message: park it, keep going
                    counts["dlq"] += 1
                    producer.produce("payments.dlq", value=m.value(), headers={"error": str(e)[:200]})
            if msgs:
                producer.poll(0)
                consumer.commit(asynchronous=False)  # at-least-once: commit after processing
            if time.time() - ref.loaded_at > REFRESH_S:
                try:
                    ref.load()
                except Exception:
                    counts["reference_refresh_failed"] += 1  # keep using the last good reference
            if time.time() - last_push > 5:
                q = sorted(lat)
                samples = [("bt_stream_events_total", {}, counts["events"]),
                           ("bt_stream_dlq_total", {}, counts["dlq"]),
                           ("bt_stream_duplicates_total", {}, counts["duplicates"])]
                samples += [("bt_stream_signals_total", {"type": k[7:]}, v) for k, v in counts.items() if k.startswith("signal_")]
                if q:
                    samples += [("bt_stream_latency_seconds", {"quantile": "0.5"}, statistics.median(q)),
                                ("bt_stream_latency_seconds", {"quantile": "0.95"}, q[int(0.95 * (len(q) - 1))])]
                push("borrower_truth_stream", samples)
                last_push = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        consumer.close()
        print(dict(counts))


if __name__ == "__main__":
    main()
