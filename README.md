# OmniDoc AI

Enterprise intelligent document processing pipeline. Phase 1 runs the local infrastructure: MongoDB, MinIO, and RabbitMQ.

The MinIO service uses the Chainguard MinIO image. Upstream `minio/minio` and `quay.io/minio/minio` are no longer anonymously pullable; the API, console, and `MINIO_*` settings are unchanged.

## Start

```bash
cp .env.example .env
docker compose up -d
```

## Verify

```bash
docker compose ps
```

MongoDB, MinIO, and RabbitMQ should be healthy. `minio-init` should have exited with code 0.

- MinIO console: http://localhost:9001 — sign in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env`. The bucket `omnidoc-documents` should exist.
- RabbitMQ management: http://localhost:15672 — sign in with `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` from `.env`. The queue `document-processing-queue` should exist.
- MongoDB listens on `localhost:27017`. Use `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` from `.env`, authentication database `admin`.

## Stop

```bash
docker compose down
```

`docker compose down -v` also removes the named volumes.
