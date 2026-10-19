import logging
from pathlib import Path

from omnidoc_worker.cleaning import clean_text
from omnidoc_worker.config import Settings
from omnidoc_worker.extraction import ExtractionResult, extract_pdf
from omnidoc_worker.models import DocumentUploadedEvent
from omnidoc_worker.repository import DocumentRepository
from omnidoc_worker.storage import MinioStorage
from omnidoc_worker.summarizer import DocumentSummarizer

log = logging.getLogger(__name__)


class DocumentPipeline:
    def __init__(
        self,
        storage: MinioStorage,
        repository: DocumentRepository,
        settings: Settings,
        summarizer: DocumentSummarizer,
    ) -> None:
        self._storage = storage
        self._repository = repository
        self._settings = settings
        self._summarizer = summarizer

    def process(self, event: DocumentUploadedEvent) -> ExtractionResult:
        path = self._storage.download(event.bucket, event.object_key)
        try:
            extraction = extract_pdf(
                path,
                lang=self._settings.tesseract_lang,
                min_page_chars=self._settings.ocr_min_page_chars,
            )
        finally:
            Path(path).unlink(missing_ok=True)

        cleaned = clean_text(extraction.raw_text)
        preview = cleaned.replace("\n", " ")
        if len(preview) > 180:
            preview = preview[:180] + "..."
        log.info("Cleaned document %s with %s: %s", event.document_id, extraction.method, preview or "<empty>")
        try:
            insight = self._summarizer.analyze(cleaned)
        except Exception:
            self._repository.save_cleaned_text(event.document_id, cleaned, extraction)
            raise
        self._repository.complete(
            event.document_id,
            cleaned,
            extraction,
            insight,
            self._summarizer.model_name,
        )
        log.info("Document %s summary: %s", event.document_id, insight.summary)
        return extraction
