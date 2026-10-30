"""MinIO helpers for the raw GH Archive lake."""

from __future__ import annotations

from minio import Minio

from gitpulse.config import get_settings


def get_minio() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> str:
    settings = get_settings()
    client = get_minio()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    return settings.minio_bucket
