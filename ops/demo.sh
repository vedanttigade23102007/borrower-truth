#!/usr/bin/env bash
# Drive the full-stack demo inside Codespaces, after: docker compose -f ops/docker-compose.yml up -d
# All data is synthetic. Prints what Prometheus (and so Grafana) now shows.
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null; then UV=uv
elif [ -x "$HOME/.local/bin/uv" ]; then UV="$HOME/.local/bin/uv"
else UV="python3 -m uv"; fi
export PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"
export CASE_SERVICE_URL="${CASE_SERVICE_URL:-http://localhost:8081}"

echo "== 1) batch: seven checks + combiner"
$UV run python -m bt.pipeline.run --data data/out/demo
echo "== 2) publish cases to the Java case service"
$UV run python -m bt.pipeline.publish --run data/out/demo/run
echo "== 3) stream: replay the last 3 months of bank payments into Kafka"
$UV run --extra stream python -m bt.stream.producer --data data/out/demo --from-month 21 --to-month 23 --rate 3000
sleep 20

echo "== 4) what Prometheus / Grafana now show"
for q in 'sum(bt_system_up)' 'bt_pipeline_total_seconds' 'bt_stream_events_total' 'bt_stream_latency_seconds' \
         'sum(bt_stream_signals_total)' 'bt_stream_dlq_total' 'bt_stream_duplicates_total' 'sum(bt_drafts_total)'; do
  printf '  %-30s ' "$q"
  curl -s http://localhost:9090/api/v1/query --data-urlencode "query=$q" | python3 -c \
    "import json,sys; r=json.load(sys.stdin)['data']['result']; print([(x['metric'].get('quantile', ''), x['value'][1]) for x in r] or 'no data')"
done

echo "== 5) break-it: crash S4, the run still completes"
$UV run python -m bt.pipeline.run --data data/out/demo --out data/out/breakit --fail S4 | head -1
