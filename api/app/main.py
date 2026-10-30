"""GitPulse FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from gitpulse.config import get_settings
from gitpulse.db import connect
from gitpulse.topics import TOPIC_BY_SLUG, TOPICS

app = FastAPI(title="GitPulse", version="0.1.0")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@app.get("/api/health")
def health() -> dict:
    with connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/topics")
def list_topics() -> list[dict]:
    return [{"slug": topic.slug, "label": topic.label} for topic in TOPICS]


@app.get("/api/series/{topic}")
def topic_series(topic: str, days: int = Query(default=90, ge=7, le=730)) -> dict:
    if topic not in TOPIC_BY_SLUG:
        raise HTTPException(status_code=404, detail="unknown topic")
    with connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT day, stars, pushes, pull_requests, issues, source
                FROM daily_facts
                WHERE topic = :topic
                ORDER BY day DESC
                LIMIT :days
                """
            ),
            {"topic": topic, "days": days},
        ).mappings().all()
    series = [dict(row) | {"day": row["day"].isoformat()} for row in reversed(rows)]
    return {"topic": topic, "label": TOPIC_BY_SLUG[topic].label, "points": series}


@app.get("/api/rising")
def rising() -> dict:
    with connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT as_of_day, topic, momentum, wow_growth, rank
                FROM rising_scores
                ORDER BY rank
                """
            )
        ).mappings().all()
    if not rows:
        return {"as_of": None, "items": []}
    return {
        "as_of": rows[0]["as_of_day"].isoformat(),
        "items": [
            {
                "rank": row["rank"],
                "topic": row["topic"],
                "label": TOPIC_BY_SLUG.get(row["topic"]).label if row["topic"] in TOPIC_BY_SLUG else row["topic"],
                "momentum": row["momentum"],
                "wow_growth": row["wow_growth"],
            }
            for row in rows
        ],
    }


@app.get("/api/forecasts")
def forecasts() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT topic, as_of_day, horizon_days, yhat, model_name, mae, mape
                FROM forecasts
                ORDER BY topic
                """
            )
        ).mappings().all()
    return [
        {
            **dict(row),
            "as_of_day": row["as_of_day"].isoformat(),
            "label": TOPIC_BY_SLUG.get(row["topic"]).label if row["topic"] in TOPIC_BY_SLUG else row["topic"],
        }
        for row in rows
    ]


@app.get("/api/results")
def results() -> dict:
    path = Path(get_settings().results_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="run ds.train first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/predictions")
def predictions(topic: str | None = Query(default=None)) -> dict:
    """Holdout actual vs model/naive/hybrid predictions from the last train run."""
    if topic is not None and topic not in TOPIC_BY_SLUG:
        raise HTTPException(status_code=404, detail="unknown topic")
    path = Path(get_settings().data_dir) / "test_predictions.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="run ds.train first")

    import csv

    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if topic and row.get("topic") != topic:
                continue
            rows.append(
                {
                    "day": row["day"],
                    "topic": row["topic"],
                    "actual": float(row["actual"]),
                    "model_pred": float(row["model_pred"]),
                    "naive_pred": float(row["naive_pred"]),
                    "hybrid_pred": float(row.get("hybrid_pred") or row["model_pred"]),
                    "model_error": float(row["model_error"]),
                    "naive_error": float(row["naive_error"]),
                    "hybrid_error": float(row.get("hybrid_error") or row["model_error"]),
                }
            )
    return {
        "topic": topic,
        "label": TOPIC_BY_SLUG[topic].label if topic and topic in TOPIC_BY_SLUG else None,
        "points": rows,
    }


@app.get("/api/etl/runs")
def etl_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, job, status, detail, rows_written, created_at
                FROM etl_runs
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [
        {**dict(row), "created_at": row["created_at"].isoformat()}
        for row in rows
    ]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
