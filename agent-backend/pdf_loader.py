"""
pdf_loader.py
-------------
Extracts text from uploaded PDF files using pypdf.
Falls back to PyMuPDF (fitz) for image-heavy or scanned PDFs.
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


class PDFLoadError(Exception):
    pass


def extract_text_from_pdf(file_path: str) -> list[dict]:
    """
    Extract text from a PDF file page by page.

    Returns:
        List of dicts: [{"page_number": int, "text": str}, ...]

    Raises:
        PDFLoadError if the file cannot be read.
    """
    path = Path(file_path)
    if not path.exists():
        raise PDFLoadError(f"File not found: {file_path}")
    if path.stat().st_size == 0:
        raise PDFLoadError("Uploaded PDF is empty (0 bytes).")

    pages = _extract_with_pypdf(file_path)

    # If pypdf yielded nothing useful, try fitz
    total_text = sum(len(p["text"]) for p in pages)
    if total_text < 100 and HAS_FITZ:
        logger.info("pypdf extracted little text; trying PyMuPDF for %s", file_path)
        pages = _extract_with_fitz(file_path) or pages

    non_empty = [p for p in pages if p["text"].strip()]
    if not non_empty:
        raise PDFLoadError(
            "No extractable text was found in this PDF. "
            "If it is a scanned image-only PDF, please use a text-layer PDF instead."
        )
    return pages


def _extract_with_pypdf(file_path: str) -> list[dict]:
    if not HAS_PYPDF:
        return []
    try:
        reader = PdfReader(file_path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise PDFLoadError("PDF is password-protected. Please upload an unlocked version.")
        if len(reader.pages) == 0:
            raise PDFLoadError("PDF has no pages.")
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            pages.append({"page_number": i, "text": text})
        return pages
    except PDFLoadError:
        raise
    except Exception as e:
        logger.warning("pypdf failed for %s: %s", file_path, e)
        return []


def _extract_with_fitz(file_path: str) -> list[dict]:
    if not HAS_FITZ:
        return []
    try:
        doc = fitz.open(file_path)
        pages = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            pages.append({"page_number": i, "text": text})
        doc.close()
        return pages
    except Exception as e:
        logger.warning("PyMuPDF failed for %s: %s", file_path, e)
        return []


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """
    Extract all text from PDF bytes as a single string.
    Used internally when a PDF is fetched from the NNRG website.
    """
    if not HAS_PYPDF:
        return ""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(texts).strip()
    except Exception as e:
        logger.warning("Failed to extract PDF bytes: %s", e)
        return ""
