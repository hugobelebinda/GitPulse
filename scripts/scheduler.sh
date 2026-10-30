#!/usr/bin/env bash
# Daily refresh loop: ClickHouse incremental backfill + retrain.
set -euo pipefail

INTERVAL_SECONDS="${GITPULSE_REFRESH_INTERVAL_SECONDS:-86400}"
BACKFILL_DAYS="${GITPULSE_BACKFILL_DAYS:-14}"
HOLDOUT_DAYS="${GITPULSE_HOLDOUT_DAYS:-30}"

echo "GitPulse scheduler started interval=${INTERVAL_SECONDS}s backfill_days=${BACKFILL_DAYS}"

while true; do
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] backfill…"
  python -m etl.clickhouse_backfill --days "${BACKFILL_DAYS}" || echo "backfill failed; will retry next cycle"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] train…"
  python -m ds.train --holdout-days "${HOLDOUT_DAYS}" || echo "train failed; will retry next cycle"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] sleeping ${INTERVAL_SECONDS}s"
  sleep "${INTERVAL_SECONDS}"
done
