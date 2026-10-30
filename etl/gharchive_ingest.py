"""Download GH Archive hours into MinIO and aggregate matched topics into Postgres."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from minio.error import S3Error

from etl.minio_client import ensure_bucket, get_minio
from gitpulse.config import get_settings
from gitpulse.db import record_etl_run, sync_topics, upsert_daily_facts
from gitpulse.topics import match_topic_slugs


def hour_url(day: date, hour: int, base: str) -> str:
    return f"{base.rstrip('/')}/{day.isoformat()}-{hour}.json.gz"


def object_key(day: date, hour: int) -> str:
    return f"gharchive/{day.isoformat()}/{hour:02d}.json.gz"


def object_exists(day: date, hour: int) -> bool:
    settings = get_settings()
    client = get_minio()
    try:
        client.stat_object(settings.minio_bucket, object_key(day, hour))
        return True
    except S3Error:
        return False


def download_hour(day: date, hour: int, *, skip_existing: bool = True) -> tuple[str, int, bool]:
    """Return (key, size, downloaded). downloaded=False when reused from MinIO."""
    settings = get_settings()
    bucket = ensure_bucket()
    key = object_key(day, hour)
    client = get_minio()
    if skip_existing and object_exists(day, hour):
        stat = client.stat_object(bucket, key)
        return key, int(stat.size or 0), False

    url = hour_url(day, hour, settings.gharchive_base_url)
    with httpx.Client(timeout=180.0, follow_redirects=True) as http:
        with http.stream("GET", url) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                for chunk in response.iter_bytes():
                    tmp.write(chunk)
                tmp_path = Path(tmp.name)
    size = tmp_path.stat().st_size
    client.fput_object(bucket, key, str(tmp_path), content_type="application/gzip")
    tmp_path.unlink(missing_ok=True)
    return key, size, True


def aggregate_hour_from_minio(day: date, hour: int) -> dict[tuple[str, str], dict[str, int]]:
    settings = get_settings()
    client = get_minio()
    key = object_key(day, hour)
    response = client.get_object(settings.minio_bucket, key)
    try:
        raw = response.read()
    finally:
        response.close()
        response.release_conn()

    tallies: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"stars": 0, "pushes": 0, "pull_requests": 0, "issues": 0}
    )
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
        for line in gz:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            repo = ((event.get("repo") or {}).get("name")) or ""
            topics = match_topic_slugs(repo)
            if not topics:
                continue
            event_type = event.get("type") or ""
            field = {
                "WatchEvent": "stars",
                "PushEvent": "pushes",
                "PullRequestEvent": "pull_requests",
                "IssuesEvent": "issues",
            }.get(event_type)
            if not field:
                continue
            day_key = day.isoformat()
            for topic in topics:
                tallies[(day_key, topic)][field] += 1
    return tallies


def ingest_day(
    day: date,
    hours: range | None = None,
    *,
    skip_existing: bool = True,
    promote_facts: bool = False,
) -> int:
    sync_topics()
    hours = hours or range(24)
    merged: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"stars": 0, "pushes": 0, "pull_requests": 0, "issues": 0}
    )
    downloaded = 0
    reused = 0
    for hour in hours:
        try:
            _key, _size, was_download = download_hour(day, hour, skip_existing=skip_existing)
            if was_download:
                downloaded += 1
            else:
                reused += 1
        except Exception as exc:  # noqa: BLE001 - continue other hours
            print(f"skip {day} hour {hour}: {exc}")
            continue
        try:
            part = aggregate_hour_from_minio(day, hour)
        except Exception as exc:  # noqa: BLE001
            print(f"aggregate failed {day} hour {hour}: {exc}")
            continue
        for key, values in part.items():
            for field, amount in values.items():
                merged[key][field] += amount

    hour_list = list(hours)
    full_day = hour_list == list(range(24))
    should_promote = promote_facts or full_day
    if not should_promote:
        print(
            f"{day}: stored/reused MinIO hours {hour_list[0]}-{hour_list[-1]} "
            f"(downloaded={downloaded}, reused={reused}); skip Postgres "
            f"(pass --promote-facts for full-day cutovers only when intentional)"
        )
        record_etl_run(
            "gharchive_ingest",
            "ok",
            f"{day} minio_only hours={hour_list[0]}-{hour_list[-1]} downloaded={downloaded} reused={reused}",
            rows_written=0,
        )
        return 0

    if not full_day:
        from sqlalchemy import text

        from gitpulse.db import connect

        with connect() as conn:
            clash = conn.execute(
                text(
                    """
                    SELECT 1 FROM daily_facts
                    WHERE day = :day AND source = 'clickhouse'
                    LIMIT 1
                    """
                ),
                {"day": day.isoformat()},
            ).first()
        if clash:
            print(f"{day}: refusing to overwrite ClickHouse facts with partial-hour lake aggregate")
            record_etl_run(
                "gharchive_ingest",
                "ok",
                f"{day} blocked_partial_overwrite",
                rows_written=0,
            )
            return 0

    rows = [
        {
            "day": day_key,
            "topic": topic,
            "stars": values["stars"],
            "pushes": values["pushes"],
            "pull_requests": values["pull_requests"],
            "issues": values["issues"],
            "source": "gharchive",
        }
        for (day_key, topic), values in merged.items()
    ]
    written = upsert_daily_facts(rows)
    status = "ok" if (downloaded + reused) else "partial"
    record_etl_run(
        "gharchive_ingest",
        status,
        f"{day} hours_downloaded={downloaded} reused={reused}",
        rows_written=written,
    )
    print(f"{day}: wrote {written} rows (downloaded={downloaded}, reused={reused})")
    return written


def ingest_range(
    start: date,
    end: date,
    hours: range | None = None,
    *,
    skip_existing: bool = True,
    promote_facts: bool = False,
) -> int:
    """Ingest inclusive [start, end] day range into MinIO (+ optional Postgres)."""
    if end < start:
        raise SystemExit("end date must be on or after start date")
    total = 0
    day = start
    while day <= end:
        total += ingest_day(
            day,
            hours,
            skip_existing=skip_existing,
            promote_facts=promote_facts,
        )
        day += timedelta(days=1)
    record_etl_run(
        "gharchive_ingest_range",
        "ok",
        f"{start} to {end}",
        rows_written=total,
    )
    return total


def _parse_hours(spec: str) -> range:
    start_h, end_h = (int(part) for part in spec.split("-", maxsplit=1))
    if not (0 <= start_h <= end_h <= 23):
        raise SystemExit("hours must be an inclusive range within 0-23")
    return range(start_h, end_h + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest GH Archive into MinIO + Postgres")
    parser.add_argument("--day", type=str, default="", help="Single UTC day YYYY-MM-DD")
    parser.add_argument("--start", type=str, default="", help="Range start YYYY-MM-DD")
    parser.add_argument("--end", type=str, default="", help="Range end YYYY-MM-DD (inclusive)")
    parser.add_argument("--hours", type=str, default="0-23", help="Inclusive hour range, e.g. 0-23")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download hours even if already present in MinIO",
    )
    parser.add_argument(
        "--promote-facts",
        action="store_true",
        help="Upsert aggregates into Postgres (default for full 0-23 days; required for partial hours)",
    )
    args = parser.parse_args()
    hours = _parse_hours(args.hours)
    skip_existing = not args.force_download

    if args.start or args.end:
        if not (args.start and args.end):
            raise SystemExit("provide both --start and --end for a range ingest")
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
        written = ingest_range(
            start,
            end,
            hours,
            skip_existing=skip_existing,
            promote_facts=args.promote_facts,
        )
        print(f"wrote {written} total rows for {start}→{end}")
        return

    day = date.fromisoformat(args.day) if args.day else datetime.now(timezone.utc).date() - timedelta(days=2)
    written = ingest_day(
        day,
        hours,
        skip_existing=skip_existing,
        promote_facts=args.promote_facts,
    )
    print(f"wrote {written} rows for {day}")


if __name__ == "__main__":
    main()
