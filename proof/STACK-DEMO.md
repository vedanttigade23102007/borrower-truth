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

## Update 12 Sep 2026: the dashboard seen, and the full path timed

Re-run in Codespaces with the stack hardened (host ports on localhost only, writes to the case service need the shared key).

| What | Result |
|---|---|
| Grafana dashboard | **rendered to an image by Grafana's own renderer**: [grafana-dashboard.png](grafana-dashboard.png). Every panel draws data. S4 shows 0 because the demo's last step crashes S4 on purpose, and the dashboard reports it. "Human decisions" is empty because nobody had approved anything in the fresh stack |
| Payment into Kafka → alert visible on the officer's case (case-service API) | **p50 1.50 s · max 1.54 s**, 10 of 10 tagged test payments arrived. The bridge batches alerts every 2 s, which is most of that time |
| Payment → worker signal | p50 24 ms · p95 29 ms (unchanged) |
| Dead letters / duplicates | 0 / 0 |

Found on the way: the first render attempt failed because macOS metadata files (`._provider.yml`), copied by my file sync from a Mac, crashed Grafana's provisioning. That came from how I copied the files, not from the repo. The sync now disables them.
