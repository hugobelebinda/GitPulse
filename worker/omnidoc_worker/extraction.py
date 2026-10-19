import io
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

log = logging.getLogger(__name__)

OcrFunc = Callable[[Image.Image, str], str]


@dataclass(frozen=True)
class PageText:
    text: str
    method: str


@dataclass(frozen=True)
class ExtractionResult:
    raw_text: str
    method: str
    page_count: int


def extract_pdf(
    path: Path,
    *,
    lang: str = "eng",
    min_page_chars: int = 20,
    ocr: OcrFunc | None = None,
) -> ExtractionResult:
    reader = ocr or _ocr_image
    document = pymupdf.open(path)
    pages: list[PageText] = []
    try:
        for index, page in enumerate(document, start=1):
            pages.append(_extract_page(page, index, lang, min_page_chars, reader))
        page_count = document.page_count
    finally:
        document.close()

    methods = {page.method for page in pages}
    if methods == {"pymupdf"}:
        method = "pymupdf"
    elif methods == {"tesseract"}:
        method = "tesseract"
    elif not methods:
        method = "pymupdf"
    else:
        method = "mixed"

    raw_text = "\n\n".join(page.text for page in pages if page.text.strip())
    return ExtractionResult(raw_text=raw_text, method=method, page_count=page_count)


def _extract_page(page: pymupdf.Page, index: int, lang: str, min_page_chars: int, ocr: OcrFunc) -> PageText:
    text = page.get_text("text") or ""
    if len(text.strip()) >= min_page_chars:
        log.debug("Page %s extracted with PyMuPDF (%s chars)", index, len(text.strip()))
        return PageText(text=text, method="pymupdf")

    log.info("Page %s has little embedded text; running Tesseract OCR", index)
    pixmap = page.get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        ocr_text = ocr(image, lang) or ""
    finally:
        image.close()
    return PageText(text=ocr_text, method="tesseract")


def _ocr_image(image: Image.Image, lang: str) -> str:
    command = os.environ.get("TESSERACT_CMD")
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    return pytesseract.image_to_string(image, lang=lang)
