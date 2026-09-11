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

**Notes:**
- The producer rate was capped at 3,000 events/s by design; the worker kept up with no backlog. Its maximum throughput was not measured here.
- Latency is measured from when the producer sent the event to when the worker classified it, on one machine. Real bank networks add transport time.
