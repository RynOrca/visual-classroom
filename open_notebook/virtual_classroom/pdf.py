"""PDF helpers for V3 virtual classroom.

This module keeps PDF-specific concerns (file detection, text-layer
inspection, scanned-PDF detection) separate from OCR command execution. The
actual OCR subprocess adapter lives in ``open_notebook.virtual_classroom.ocr``.
"""

from pathlib import Path
from typing import Optional

from loguru import logger


def is_pdf_file(file_path: Optional[str]) -> bool:
    """Return True when the path points to a PDF file."""
    if not file_path:
        return False
    return Path(file_path).suffix.lower() == ".pdf"


def extract_pdf_text_layer(
    pdf_path: str, max_pages: int = 5, min_chars: int = 20
) -> Optional[str]:
    """Extract the embedded text layer from the first pages of a PDF.

    Returns ``None`` when the PDF cannot be inspected. For a scanned PDF this
    normally returns an empty/whitespace string (or ``None`` if the file is
    invalid), which callers can use to decide whether OCR is needed.
    """
    if not pdf_path or not Path(pdf_path).exists():
        return None
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning("pypdfium2 is not installed; cannot inspect PDFs")
        return None

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            total_pages = len(pdf)
            collected: list[str] = []
            for page_index in range(min(total_pages, max_pages)):
                page = pdf[page_index]
                try:
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range() or ""
                    finally:
                        textpage.close()
                    collected.append(text)
                finally:
                    page.close()
            joined = "\n".join(collected).strip()
            if len(joined) < min_chars:
                return ""
            return joined
        finally:
            pdf.close()
    except Exception as e:
        logger.warning(f"Could not inspect PDF text layer: {e}")
        return None


def pdf_has_text_layer(pdf_path: str, min_chars: int = 20) -> bool:
    """Return True when a PDF has a usable embedded text layer.

    Scanned PDFs normally contain only images and little or no selectable
    text.  We sample the first few pages to decide whether the UnlimitedOCR
    fallback should be used.  If the PDF cannot be inspected (for example a
    placeholder file in tests), it is treated as *not* scanned so the normal
    content-core pipeline still runs.
    """
    text = extract_pdf_text_layer(pdf_path, min_chars=min_chars)
    if text is None:
        return True
    return bool(text.strip())


def is_scanned_pdf(pdf_path: str, min_chars: int = 20) -> bool:
    """Return True when the PDF exists but has no meaningful text layer."""
    return is_pdf_file(pdf_path) and not pdf_has_text_layer(pdf_path, min_chars)
