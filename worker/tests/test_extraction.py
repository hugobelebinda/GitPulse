import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

from omnidoc_worker.extraction import extract_pdf
from omnidoc_worker.models import DocumentUploadedEvent


class EventTests(unittest.TestCase):
    def test_accepts_java_nanosecond_timestamp(self) -> None:
        event = DocumentUploadedEvent.model_validate_json(
            """
            {
              "documentId": "doc-1",
              "bucket": "omnidoc-documents",
              "objectKey": "documents/doc-1/invoice.pdf",
              "originalFilename": "invoice.pdf",
              "contentType": "application/pdf",
              "uploadedAt": "2026-10-14T02:48:36.971452097Z"
            }
            """
        )
        self.assertEqual(event.document_id, "doc-1")
        self.assertEqual(event.uploaded_at.microsecond, 971452)


class ExtractionTests(unittest.TestCase):
    def test_text_pdf_uses_pymupdf(self) -> None:
        path = _text_pdf("Invoice number 1001 for ACME Supplies")
        try:
            with patch("omnidoc_worker.extraction._ocr_image") as ocr:
                result = extract_pdf(path, min_page_chars=20)
            ocr.assert_not_called()
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result.method, "pymupdf")
        self.assertIn("ACME Supplies", result.raw_text)

    def test_image_only_pdf_uses_tesseract(self) -> None:
        if not _tesseract_available():
            self.skipTest("Tesseract is not available")
        path = _image_only_pdf("OMNIDOC INVOICE")
        try:
            result = extract_pdf(path, min_page_chars=20)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result.method, "tesseract")
        self.assertIn("OMNIDOC", result.raw_text.upper())


def _text_pdf(text: str) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=16)
    handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    handle.close()
    path = Path(handle.name)
    document.save(path)
    document.close()
    return path


def _image_only_pdf(text: str) -> Path:
    source = pymupdf.open()
    page = source.new_page(width=800, height=300)
    page.insert_text((40, 160), text, fontsize=48)
    pixmap = page.get_pixmap(dpi=200)
    source.close()

    image_pdf = pymupdf.open()
    image_page = image_pdf.new_page(width=pixmap.width, height=pixmap.height)
    image_page.insert_image(image_page.rect, pixmap=pixmap)
    handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    handle.close()
    path = Path(handle.name)
    image_pdf.save(path)
    image_pdf.close()
    return path


def _tesseract_available() -> bool:
    binary = os.environ.get("TESSERACT_CMD", "tesseract")
    return Path(binary).is_file() or _which(binary)


def _which(command: str) -> bool:
    return any((Path(entry) / command).is_file() for entry in os.environ.get("PATH", "").split(os.pathsep))


if __name__ == "__main__":
    unittest.main()
