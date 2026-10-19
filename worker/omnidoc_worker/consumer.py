import logging
import sys
import time

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from pydantic import ValidationError

from omnidoc_worker.config import Settings, configure_logging, configure_tesseract
from omnidoc_worker.models import DocumentUploadedEvent
from omnidoc_worker.summarizer import DocumentSummarizer
from omnidoc_worker.pipeline import DocumentPipeline
from omnidoc_worker.repository import DocumentRepository, RepositoryError
from omnidoc_worker.storage import MinioStorage, StorageError

log = logging.getLogger(__name__)

RETRY_HEADER = "x-omnidoc-retry"


class QueueConsumer:
    def __init__(self, settings: Settings, pipeline: DocumentPipeline, repository: DocumentRepository) -> None:
        self._settings = settings
        self._pipeline = pipeline
        self._repository = repository

    def consume_forever(self) -> None:
        delay = 2
        while True:
            try:
                connection = self._connect()
                channel = connection.channel()
                channel.queue_declare(queue=self._settings.rabbit_queue, passive=True)
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(self._settings.rabbit_queue, self._on_message, auto_ack=False)
                log.info("Listening on queue %s", self._settings.rabbit_queue)
                delay = 2
                channel.start_consuming()
            except KeyboardInterrupt:
                log.info("Worker stopped")
                return
            except pika.exceptions.AMQPError:
                log.exception("RabbitMQ connection failed; retrying in %s seconds", delay)
                time.sleep(delay)
                delay = min(delay * 2, 30)

    def process_available(self) -> int:
        connection = self._connect()
        channel = connection.channel()
        channel.queue_declare(queue=self._settings.rabbit_queue, passive=True)
        processed = 0
        while True:
            method, properties, body = channel.basic_get(self._settings.rabbit_queue, auto_ack=False)
            if method is None:
                break
            self._handle(channel, method, properties, body)
            processed += 1
        connection.close()
        log.info("Processed %s queued document(s)", processed)
        return processed

    def _connect(self) -> pika.BlockingConnection:
        credentials = pika.PlainCredentials(self._settings.rabbit_user, self._settings.rabbit_password)
        parameters = pika.ConnectionParameters(
            host=self._settings.rabbit_host,
            port=self._settings.rabbit_port,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=30,
        )
        return pika.BlockingConnection(parameters)

    def _on_message(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ) -> None:
        self._handle(channel, method, properties, body)

    def _handle(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties | None,
        body: bytes,
    ) -> None:
        try:
            event = DocumentUploadedEvent.model_validate_json(body)
        except ValidationError:
            log.exception("Rejected message %s: invalid DocumentUploadedEvent", method.delivery_tag)
            channel.basic_nack(method.delivery_tag, requeue=False)
            return

        try:
            self._pipeline.process(event)
        except (StorageError, RepositoryError) as exc:
            if exc.transient and self._retry(channel, method, properties, body, event.document_id, str(exc)):
                return
            log.exception("Document %s failed", event.document_id)
            self._repository.mark_failed(event.document_id, str(exc))
        except Exception as exc:
            log.exception("Document %s failed", event.document_id)
            self._repository.mark_failed(event.document_id, str(exc))

        channel.basic_ack(method.delivery_tag)

    def _retry(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties | None,
        body: bytes,
        document_id: str,
        reason: str,
    ) -> bool:
        headers = dict((properties.headers if properties and properties.headers else {}) or {})
        attempt = int(headers.get(RETRY_HEADER, 0))
        if attempt >= self._settings.max_retries:
            log.error("Document %s exhausted retries: %s", document_id, reason)
            return False

        headers[RETRY_HEADER] = attempt + 1
        channel.basic_publish(
            exchange="",
            routing_key=self._settings.rabbit_queue,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                headers=headers,
            ),
        )
        channel.basic_ack(method.delivery_tag)
        log.warning("Requeued document %s (attempt %s): %s", document_id, attempt + 1, reason)
        return True


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    configure_tesseract(settings)
    repository = DocumentRepository(settings.mongodb_uri, settings.mongodb_database)
    repository.connect()
    storage = MinioStorage(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key)
    summarizer = DocumentSummarizer(
        settings.summary_model,
        settings.summary_model_file,
        settings.ner_device,
    )
    pipeline = DocumentPipeline(storage, repository, settings, summarizer)
    consumer = QueueConsumer(settings, pipeline, repository)
    try:
        if "--once" in sys.argv:
            consumer.process_available()
        else:
            consumer.consume_forever()
    finally:
        repository.close()
