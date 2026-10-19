import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pytesseract


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_project_env() -> None:
    root = Path(__file__).resolve().parents[2]
    load_env_file(root / ".env")


@dataclass(frozen=True)
class Settings:
    rabbit_host: str
    rabbit_port: int
    rabbit_user: str
    rabbit_password: str
    rabbit_queue: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    mongodb_uri: str
    mongodb_database: str
    tesseract_lang: str
    tesseract_cmd: str | None
    ocr_min_page_chars: int
    max_retries: int
    log_level: str
    ner_model: str
    ner_score_threshold: float
    ner_device: str
    summary_model: str
    summary_model_file: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_project_env()
        return cls(
            rabbit_host=_env("RABBITMQ_HOST", "localhost"),
            rabbit_port=int(_env("RABBITMQ_PORT", "5672")),
            rabbit_user=_env("RABBITMQ_DEFAULT_USER", "omnidoc"),
            rabbit_password=_env("RABBITMQ_DEFAULT_PASS", "omnidoc_dev_password"),
            rabbit_queue=_env("RABBITMQ_QUEUE", "document-processing-queue"),
            minio_endpoint=_env("MINIO_ENDPOINT", "http://localhost:9000"),
            minio_access_key=_env("MINIO_ROOT_USER", "omnidoc"),
            minio_secret_key=_env("MINIO_ROOT_PASSWORD", "omnidoc_dev_password"),
            minio_bucket=_env("MINIO_BUCKET", "omnidoc-documents"),
            mongodb_uri=_env(
                "MONGODB_URI",
                "mongodb://omnidoc:omnidoc_dev_password@localhost:27017/omnidoc?authSource=admin",
            ),
            mongodb_database=_env("MONGO_INITDB_DATABASE", "omnidoc"),
            tesseract_lang=_env("TESSERACT_LANG", "eng"),
            tesseract_cmd=os.environ.get("TESSERACT_CMD") or None,
            ocr_min_page_chars=int(_env("OCR_MIN_PAGE_CHARS", "20")),
            max_retries=int(_env("WORKER_MAX_RETRIES", "3")),
            log_level=_env("LOG_LEVEL", "INFO"),
            ner_model=_env("NER_MODEL", "nickprock/bert-finetuned-ner-ontonotes"),
            ner_score_threshold=float(_env("NER_SCORE_THRESHOLD", "0.5")),
            ner_device=_env("NER_DEVICE", "cpu"),
            summary_model=_env("SUMMARY_MODEL", "bartowski/Qwen2.5-7B-Instruct-GGUF"),
            summary_model_file=_env("SUMMARY_MODEL_FILE", "Qwen2.5-7B-Instruct-Q4_K_M.gguf"),
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("pika").setLevel(logging.WARNING)


def configure_tesseract(settings: Settings) -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    log = logging.getLogger(__name__)
    try:
        version = pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        log.warning("Tesseract is not installed. Scanned pages cannot be OCR'd until it is available.")
        return
    log.info("Tesseract %s is available", version)


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value or default
