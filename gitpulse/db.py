"""Postgres helpers shared by API, ETL, and training."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from gitpulse.config import get_settings
from gitpulse.topics import TOPICS

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


@contextmanager
def connect() -> Iterator:
    with get_engine().begin() as conn:
        yield conn


def sync_topics() -> int:
    """Upsert curated topics so ETL/train work on existing Postgres volumes."""
    with connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO topics (slug, label)
                VALUES (:slug, :label)
                ON CONFLICT (slug) DO UPDATE SET label = EXCLUDED.label
                """
            ),
            [{"slug": topic.slug, "label": topic.label} for topic in TOPICS],
        )
    return len(TOPICS)


def upsert_daily_facts(rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO daily_facts (day, topic, stars, pushes, pull_requests, issues, source)
        VALUES (:day, :topic, :stars, :pushes, :pull_requests, :issues, :source)
        ON CONFLICT (day, topic)
        DO UPDATE SET
            stars = EXCLUDED.stars,
            pushes = EXCLUDED.pushes,
            pull_requests = EXCLUDED.pull_requests,
            issues = EXCLUDED.issues,
            source = EXCLUDED.source,
            loaded_at = NOW()
        """
    )
    with connect() as conn:
        conn.execute(sql, rows)
    return len(rows)


def record_etl_run(
    job: str,
    status: str,
    detail: str,
    rows_written: int = 0,
) -> None:
    with connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO etl_runs (job, status, detail, rows_written)
                VALUES (:job, :status, :detail, :rows_written)
                """
            ),
            {
                "job": job,
                "status": status,
                "detail": detail,
                "rows_written": rows_written,
            },
        )


def replace_forecasts(rows: list[dict]) -> int:
    with connect() as conn:
        conn.execute(text("DELETE FROM forecasts"))
        if rows:
            conn.execute(
                text(
                    """
                    INSERT INTO forecasts (
                        topic, as_of_day, horizon_days, yhat, model_name, mae, mape
                    ) VALUES (
                        :topic, :as_of_day, :horizon_days, :yhat, :model_name, :mae, :mape
                    )
                    """
                ),
                rows,
            )
    return len(rows)
