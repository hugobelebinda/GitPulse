# GitPulse

Engineering-topic pulse on public GitHub. An ETL pipeline lands daily activity facts for **30 curated topics**, scikit-learn forecasts next-day stars against a seasonal baseline, and a FastAPI dashboard ranks rising topics and charts holdout actual vs predicted.

## Stack

- **FastAPI** dashboard and JSON API
- **Postgres** warehouse (`daily_facts`, `forecasts`, `rising_scores`)
- **MinIO** raw lake for GH Archive hours
- **Polars/Pandas + NumPy + scikit-learn + matplotlib**
- **Jupyter Lab** for exploration
- **Docker Compose** (+ optional daily scheduler profile)
- **pytest + ruff** via GitHub Actions CI

RabbitMQ is not required. Jobs are `docker compose run` one-shots, or the `schedule` profile for a daily refresh loop.

## Quick start

```bash
cp -n .env.example .env
chmod +x scripts/pulse scripts/scheduler.sh
./scripts/pulse up
./scripts/pulse backfill --days 180
./scripts/pulse train
```

Open http://localhost:8000

Optional lake ingest (multi-day, resumes existing MinIO objects). Partial-hour runs stay in MinIO only unless you pass `--promote-facts`; full `0-23` days promote to Postgres automatically:

```bash
./scripts/pulse ingest-range --start 2025-06-01 --end 2025-06-03 --hours 12-13
./scripts/pulse ingest-range --start 2025-06-01 --end 2025-06-01 --hours 0-23
```

Daily refresh loop:

```bash
./scripts/pulse schedule
```

Notebook:

```bash
./scripts/pulse notebook
# http://localhost:8888
```

Tests:

```bash
./scripts/pulse test
# or locally: PYTHONPATH=. pytest -q
```

## Topics (30)

Languages & runtimes: Python, Rust, TypeScript, Go, Java, .NET/C#, C/C++, Ruby, PHP, Swift, Kotlin, Scala, Zig, Elixir  
Platforms & infra: Kubernetes, Docker, AWS/Cloud, DevOps/CI, Observability, Streaming  
App domains: React, Vue, WebAssembly, Mobile, Web3, Security, Databases  
Data & AI: LLM/GenAI, Classical ML, Data Engineering  

Matching uses curated seed repos plus narrow repo-name keywords in `gitpulse/topics.py`.

## What the numbers mean

- **Facts:** per topic, per UTC day — stars, pushes, PRs, issues.
- **Rising:** week-over-week growth of the 7-day star average.
- **Split:** ~6 months of facts → first ~5 months train, last 30 days test. Predictions are scored against real held-out stars.
- **Model:** `GradientBoostingRegressor` on `log1p(stars)` with lag/rolling features; high-volume topics get dedicated models; a **hybrid** selector keeps model or seasonal naive per topic based on holdout MAE.
- Artifacts: `ds/results.json`, `data/test_predictions.csv`, `data/models/stars_gbr.joblib`.

Protocol: `gitpulse/protocol.json`.

## API

- `GET /api/health`
- `GET /api/topics`
- `GET /api/series/{topic}`
- `GET /api/rising`
- `GET /api/forecasts`
- `GET /api/results`
- `GET /api/predictions?topic=python`
- `GET /api/etl/runs`

## Data sources

1. **ClickHouse playground** `github_events` — fast historical backfill (no giant download). End date auto-clamps to playground max.
2. **GH Archive** hourly `.json.gz` — lake path into MinIO with skip-existing resume, then aggregate.

Keep lake windows bounded; a full year of raw GH Archive is tens of GB.
