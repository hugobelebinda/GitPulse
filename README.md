# OmniDoc AI

Enterprise intelligent document processing pipeline. Upload a PDF and the worker returns a summary plus the key facts from the document.

The MinIO service uses the Chainguard MinIO image. Upstream `minio/minio` and `quay.io/minio/minio` are no longer anonymously pullable; the API, console, and `MINIO_*` settings are unchanged.

## Start

```bash
./omnidoc run
```

This creates `.env` from `.env.example` when it is missing, then builds and starts MongoDB, MinIO, RabbitMQ, the ingestion service, and the Python worker. The first build downloads Maven dependencies, PyTorch, and the named-entity model.

`./omnidoc status` shows the stack. `./omnidoc logs` follows logs. `./omnidoc stop` stops it and keeps the data volumes.

## Verify

```bash
docker compose ps
```

MongoDB, MinIO, RabbitMQ, and the ingestion service should be healthy. `minio-init` should have exited with code 0. The worker should be running.

- MinIO console: http://localhost:9001 — sign in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env`. The bucket `omnidoc-documents` should exist.
- RabbitMQ management: http://localhost:15672 — sign in with `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` from `.env`. The queue `document-processing-queue` should exist.
- MongoDB listens on `localhost:27017`. Use `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` from `.env`, authentication database `admin`.

Open http://localhost:8080, choose a PDF in the system file window, and the page shows the summary and key facts when processing finishes.

The same upload is available from the command line:

```bash
curl -sS -F "file=@invoice.pdf;type=application/pdf" http://localhost:8080/api/documents/upload
curl -sS http://localhost:8080/api/documents/{documentId}
```

The upload returns `202 Accepted`. After processing, `GET /api/documents/{id}` includes `summary` and `keyInformation`, and the status is `COMPLETED`.

Inside Compose, the apps use the service hostnames `mongodb`, `minio`, and `rabbitmq`. Host ports stay on localhost.

## Ingestion service

To run the API on the host instead of in Compose, stop the `ingestion-service` container first so port 8080 is free. From `ingestion-service`:

```bash
./mvnw spring-boot:run
```

Upload a PDF:

```bash
curl -sS -F "file=@invoice.pdf;type=application/pdf" http://localhost:8080/api/documents/upload
```

The response is `202 Accepted` with `status` `PENDING`. Fetch the same record with `GET /api/documents/{documentId}`. Health: http://localhost:8080/actuator/health

## Python worker

Compose runs the worker with Tesseract installed in the image. To run it on the host instead, stop the `worker` container, install Tesseract (`sudo apt install tesseract-ocr tesseract-ocr-eng`), and from `worker`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m omnidoc_worker
```

The worker reads `.env` from the repository root. It downloads each uploaded PDF from MinIO, reads text with PyMuPDF, and OCRs pages that have almost no text. Pandas normalizes the lines. A free local instruct model (`SUMMARY_MODEL`, default Qwen2.5 7B Instruct) writes a summary and a list of key facts. Pydantic validates that result, and the worker stores `summary` and `keyInformation` on the MongoDB document with status `COMPLETED`. The page at http://localhost:8080 lists recent documents and can export the summary as a text file. The Docker image downloads the model at build time.

`python -m omnidoc_worker --once` processes the messages already in the queue and exits.

## Stop

```bash
./omnidoc stop
```

`docker compose down -v` also removes the named volumes.
