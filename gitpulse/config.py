"""Environment-driven settings for API, ETL, and DS jobs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    clickhouse_url: str
    gharchive_base_url: str
    data_dir: str
    results_path: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=_env(
            "DATABASE_URL",
            "postgresql+psycopg://gitpulse:gitpulse@localhost:5432/gitpulse",
        ),
        minio_endpoint=_env("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=_env("MINIO_ROOT_USER", "gitpulse"),
        minio_secret_key=_env("MINIO_ROOT_PASSWORD", "gitpulse_dev_password"),
        minio_bucket=_env("MINIO_BUCKET", "gitpulse-raw"),
        minio_secure=_env("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
        clickhouse_url=_env(
            "CLICKHOUSE_URL",
            "https://play.clickhouse.com/?user=explorer&default_format=JSONEachRow",
        ),
        gharchive_base_url=_env("GHARCHIVE_BASE_URL", "https://data.gharchive.org"),
        data_dir=_env("GITPULSE_DATA_DIR", "data"),
        results_path=_env("GITPULSE_RESULTS_PATH", "ds/results.json"),
    )
