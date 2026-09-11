# Full-stack demo: GitHub Codespaces (4-core / 16 GB), 11 Sep 2026

Run with `ops/demo.sh` against `docker compose -f ops/docker-compose.yml up -d`. All data synthetic.

| What | Result |
|---|---|
| Services up | Redpanda (Kafka API), case service (Java, healthy), S3 streaming worker, Prometheus, Pushgateway, Grafana |
| Batch run: seven checks + combiner, 120 borrowers | **1.34 s**; 8 of 8 components `ok`; 245 signals; 29 likely fraud, 32 worth a look |
| Published to the case service | 120 cases, **173 proposed fix steps with drafts** |
| Streamed through Kafka (last 3 months of payments) | **59,551 events in 19.9 s** (producer capped at 3,000/s) |
| Worker processed | 59,551 of 59,551 |
| Payment → suspicious-payer signal latency | **p50 24 ms · p95 29 ms** |
| Streaming signals raised | 250 (unknown payers, one per payment; the batch combiner groups them per borrower) |
| Dead-letter messages / duplicates dropped | 0 / 0 |
| Break-it (S4 crashed) | run completed; cases marked "S4 unavailable" |

## Update: streaming alerts now reach the case, and only real ones go out

- **Signal bridge added** (Kafka `signals` → case service `/api/live-alerts`). Alerts appear on the borrower's case page and in the audit log.
- **First run: half the alerted cases were honest borrowers.** The worker alerted on *every* payment from an unknown payer, including honest ones (relatives paying car loans). Fix: stream only facts, meaning money from a linked company or from a lender. Unknown-payer patterns go to the batch S3, which weighs them by share of inflows.
- **Cold start:** latency measured right after a worker restart was 13 s (p50), because the worker was still loading its reference data. It is re-measured below with a warm worker.

Re-run with a warm worker (same 59,551 payments):

| What | Result |
|---|---|
| Payment → alert latency | **p50 24 ms · p95 29 ms** |
| Real-time alerts sent / weak events left to batch | 48 / 202 |
| Forwarded to the case service by the bridge | 48 of 48, 0 dead letters |
| **Borrowers alerted that are planted frauds** | **8 of 8** (no honest borrower alerted) |
| Disguised-receipt frauds alerted in real time | **8 of 8** |

**Notes:**
- The producer rate was capped at 3,000 events/s by design; the worker kept up with no backlog. Its maximum throughput was not measured here.
- Latency is measured from when the producer sent the event to when the worker classified it, on one machine. Real bank networks add transport time.
