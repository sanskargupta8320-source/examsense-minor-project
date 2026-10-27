import os
import re
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger("examsense.pdf_service")

# Lazy/conditional imports to prevent startup crashes if OCR/Fitz are missing
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF (fitz) is not installed. Text extraction may be limited.")

try:
    import pytesseract
    from PIL import Image
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.info("pytesseract/PIL not available for scanned PDF OCR fallback.")


def sanitize_filename(filename: str) -> str:
    """Sanitize the uploaded file name to prevent directory traversal or invalid characters."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^a-zA-Z0-9_\.\-]", "_", base)
    return clean[:100]  # truncate to safe length


def extract_text_from_pdf(file_path: str) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Extracts text from a given PDF file.
    
    Returns:
        (extracted_text, is_ocr, metadata_dict)
    
    Raises:
        ValueError: If file is corrupted, not a valid PDF, or empty.
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 15.0:
        raise ValueError(f"File size ({file_size_mb:.1f} MB) exceeds maximum allowed size (10 MB).")

    if not FITZ_AVAILABLE:
        # Fallback if fitz is not installed
        raise ValueError("PyMuPDF (fitz) engine is not available on this server.")

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"Could not open PDF file. It may be corrupted or password-protected: {str(e)}")

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise ValueError("The uploaded PDF has 0 pages.")

    full_text_parts = []
    is_ocr = False

    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:
            full_text_parts.append(text)

    combined_text = "\n\n".join(full_text_parts).strip()

    # If PyMuPDF returned almost no text (less than 60 characters for a whole document),
    # the PDF is likely scanned or image-based.
    if len(combined_text) < 60:
        logger.info(f"PDF {file_path} appears to be scanned (only {len(combined_text)} characters extracted). Attempting OCR...")
        if OCR_AVAILABLE:
            try:
                ocr_text_parts = []
                for page_num in range(page_count):
                    page = doc[page_num]
                    # Render page to high-res image
                    pix = page.get_pixmap(dpi=200)
                    img_data = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_data))
                    ocr_page_text = pytesseract.image_to_string(image)
                    if ocr_page_text.strip():
                        ocr_text_parts.append(ocr_page_text.strip())
                
                ocr_combined = "\n\n".join(ocr_text_parts).strip()
                if len(ocr_combined) >= 60:
                    combined_text = ocr_combined
                    is_ocr = True
                else:
                    raise ValueError(
                        "Scanned PDF detected, but OCR could not recognize enough legible English text. "
                        "Please provide a clearer digital scan or standard PDF."
                    )
            except Exception as ocr_err:
                logger.warning(f"OCR attempt failed: {ocr_err}")
                raise ValueError(
                    "This PDF appears to be a scanned image with no digital text. "
                    "OCR fallback could not process it (Tesseract OCR engine is not installed or unreadable). "
                    "Please upload a standard digital PDF or clean copy."
                )
        else:
            raise ValueError(
                "This PDF appears to be a scanned image without selectable text. "
                "Optical Character Recognition (OCR) is not configured on this host. "
                "Please upload a standard text PDF or use Demo Mode to explore all features."
            )

    doc.close()

    metadata = {
        "page_count": page_count,
        "char_count": len(combined_text),
        "word_count": len(combined_text.split()),
        "file_size_mb": round(file_size_mb, 2),
    }

    return combined_text, is_ocr, metadata
