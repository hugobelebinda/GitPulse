FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gitpulse ./gitpulse
COPY etl ./etl
COPY ds ./ds
COPY api ./api
COPY web ./web
COPY sql ./sql
COPY scripts ./scripts
COPY tests ./tests
COPY ruff.toml ./ruff.toml

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
