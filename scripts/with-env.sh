#!/usr/bin/env bash
# Run a command with the private tokens from .env loaded. Never prints them.
#   scripts/with-env.sh kaggle datasets list --mine
set -euo pipefail
set +x
here="$(cd "$(dirname "$0")/.." && pwd)"
set -a
# shellcheck disable=SC1091
. "$here/.env"
set +a
# Kaggle's newer tokens (KGAT_...) are read from KAGGLE_API_TOKEN
case "${KAGGLE_KEY:-}" in KGAT_*) export KAGGLE_API_TOKEN="$KAGGLE_KEY" ;; esac
exec "$@"
