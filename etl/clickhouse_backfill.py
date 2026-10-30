"""Backfill daily topic aggregates from the public ClickHouse GitHub events table."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from gitpulse.config import get_settings
from gitpulse.db import record_etl_run, sync_topics, upsert_daily_facts
from gitpulse.topics import TOPICS


def _default_end() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=2)


def resolve_end_date(requested: date, clickhouse_url: str) -> date:
    """Clamp end date to the playground's available github_events window."""
    sql = "SELECT toDate(max(created_at)) AS max_day FROM github_events FORMAT JSONEachRow"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(clickhouse_url, content=sql.encode("utf-8"))
            response.raise_for_status()
        line = next((part for part in response.text.splitlines() if part.strip()), "")
        if not line:
            return requested
        max_day = date.fromisoformat(str(json.loads(line)["max_day"])[:10])
        if requested > max_day:
            print(f"clamping end {requested} → {max_day} (ClickHouse max)")
            return max_day
    except Exception as exc:  # noqa: BLE001 - fall back to requested end
        print(f"could not probe ClickHouse max date ({exc}); using {requested}")
    return requested


def _topic_predicate(topic_slug: str) -> str:
    topic = next(t for t in TOPICS if t.slug == topic_slug)
    parts: list[str] = []
    for repo in topic.seed_repos:
        parts.append(f"repo_name = '{repo}'")
    for keyword in topic.keywords:
        safe = keyword.replace("'", "\\'")
        parts.append(f"positionCaseInsensitive(repo_name, '{safe}') > 0")
    return "(" + " OR ".join(parts) + ")"


def fetch_topic_days(
    topic_slug: str,
    start: date,
    end: date,
    clickhouse_url: str,
    *,
    retries: int = 4,
) -> list[dict[str, Any]]:
    predicate = _topic_predicate(topic_slug)
    sql = f"""
    SELECT
        toDate(created_at) AS day,
        countIf(event_type = 'WatchEvent') AS stars,
        countIf(event_type = 'PushEvent') AS pushes,
        countIf(event_type = 'PullRequestEvent') AS pull_requests,
        countIf(event_type = 'IssuesEvent') AS issues
    FROM github_events
    WHERE created_at >= toDateTime('{start.isoformat()} 00:00:00')
      AND created_at < toDateTime('{end.isoformat()} 00:00:00')
      AND {predicate}
    GROUP BY day
    ORDER BY day
    FORMAT JSONEachRow
    """
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=240.0) as client:
                response = client.post(clickhouse_url, content=sql.encode("utf-8"))
                response.raise_for_status()
            rows: list[dict[str, Any]] = []
            for line in response.text.splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                rows.append(
                    {
                        "day": str(item["day"])[:10],
                        "topic": topic_slug,
                        "stars": int(item["stars"]),
                        "pushes": int(item["pushes"]),
                        "pull_requests": int(item["pull_requests"]),
                        "issues": int(item["issues"]),
                        "source": "clickhouse",
                    }
                )
            return rows
        except Exception as exc:  # noqa: BLE001 - retry transient playground failures
            last_error = exc
            sleep_s = min(2 ** attempt, 20)
            print(f"{topic_slug}: attempt {attempt}/{retries} failed ({exc}); retry in {sleep_s}s")
            time.sleep(sleep_s)
    raise RuntimeError(f"ClickHouse backfill failed for {topic_slug}: {last_error}")


def backfill(
    start: date,
    end: date,
    clickhouse_url: str,
    *,
    only: set[str] | None = None,
) -> int:
    sync_topics()
    selected = [topic for topic in TOPICS if only is None or topic.slug in only]
    if only and not selected:
        raise SystemExit(f"no matching topics for {sorted(only)}")
    total = 0
    failures: list[str] = []
    for index, topic in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] fetching {topic.slug}…")
        try:
            rows = fetch_topic_days(topic.slug, start, end, clickhouse_url)
            total += upsert_daily_facts(rows)
            print(f"{topic.slug}: {len(rows)} days")
        except Exception as exc:  # noqa: BLE001 - continue remaining topics
            failures.append(topic.slug)
            print(f"{topic.slug}: FAILED ({exc})")
            record_etl_run(
                "clickhouse_backfill",
                "error",
                f"{topic.slug}: {exc}",
                rows_written=0,
            )
    status = "ok" if not failures else ("partial" if total else "error")
    detail = f"{start} to {end}"
    if failures:
        detail += f"; failed={','.join(failures)}"
    record_etl_run("clickhouse_backfill", status, detail, rows_written=total)
    if status == "error":
        raise SystemExit(f"backfill failed for all topics: {failures}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill GitPulse facts from ClickHouse")
    parser.add_argument("--days", type=int, default=180, help="How many days ending before yesterday")
    parser.add_argument("--start", type=str, default="")
    parser.add_argument("--end", type=str, default="")
    parser.add_argument(
        "--topics",
        type=str,
        default="",
        help="Comma-separated topic slugs to backfill (default: all)",
    )
    args = parser.parse_args()

    settings = get_settings()
    end = date.fromisoformat(args.end) if args.end else resolve_end_date(_default_end(), settings.clickhouse_url)
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days)
    only = {part.strip() for part in args.topics.split(",") if part.strip()} or None
    written = backfill(start, end, settings.clickhouse_url, only=only)
    print(f"wrote {written} fact rows")


if __name__ == "__main__":
    main()
