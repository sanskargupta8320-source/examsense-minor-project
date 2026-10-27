import os
import re
import logging
from typing import Tuple, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

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


MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "40"))


def sanitize_filename(filename: str) -> str:
    """Sanitize the uploaded file name to prevent directory traversal or invalid characters."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^a-zA-Z0-9_\.\-]", "_", base)
    return clean[:100]  # truncate to safe length


def split_pdf_into_batches(file_path: str, max_pages_per_batch: int = 15) -> List[str]:
    """
    For PDFs over ~15 MB or over 40 pages, splits into page batches (10-15 pages per AI call using PyMuPDF).
    Returns a list of file paths (either original or batch files).
    """
    if not FITZ_AVAILABLE or not os.path.exists(file_path):
        return [file_path]

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if total_pages <= 40 and file_size_mb <= 15.0:
            doc.close()
            return [file_path]

        batches = []
        base, ext = os.path.splitext(file_path)
        for start in range(0, total_pages, max_pages_per_batch):
            end = min(start + max_pages_per_batch, total_pages)
            batch_doc = fitz.open()
            batch_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
            batch_path = f"{base}_batch_{start+1}_{end}{ext}"
            batch_doc.save(batch_path)
            batch_doc.close()
            batches.append(batch_path)

        doc.close()
        logger.info(f"Split {file_path} ({total_pages} pages) into {len(batches)} batches.")
        return batches
    except Exception as e:
        logger.warning(f"Could not split PDF into batches: {e}")
        return [file_path]


def extract_text_from_image(file_path: str) -> Tuple[str, bool, Dict[str, Any]]:
    """Extracts text from an image file (JPG, PNG, WEBP) using OCR if available."""
    if not os.path.exists(file_path):
        raise ValueError("We could not find the uploaded file on the server. Please try uploading again.")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise ValueError(
            f"File size ({file_size_mb:.1f} MB) exceeds maximum allowed size ({MAX_UPLOAD_SIZE_MB} MB). "
            "Try splitting the PDF or compressing it at ilovepdf.com."
        )

    extracted_text = ""
    if OCR_AVAILABLE:
        try:
            image = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(image).strip()
        except Exception as ocr_err:
            logger.info(f"Tesseract OCR skipped/failed for image {file_path}: {ocr_err}")

    metadata = {
        "page_count": 1,
        "char_count": len(extracted_text),
        "word_count": len(extracted_text.split()),
        "file_size_mb": round(file_size_mb, 2),
    }
    return extracted_text, True, metadata


def preprocess_extracted_exam_text(text: str) -> str:
    """
    Injects clean newline breaks before inline question markers (Q.1, Q1., Question 1,
    1(a), (b), OR, [5 Marks], etc.) to prevent multi-question merging in inline or
    two-column layouts, while preserving equations and formulas intact.
    """
    if not text:
        return ""

    # 1. Break before standard Question markers: "Q.1", "Q1.", "Question 1", etc.
    text = re.sub(
        r"(?<=[^\n])\s+(Q(?:uestion)?\s*\.?\s*\d+[\.\:\-\)])",
        r"\n\1",
        text,
        flags=re.IGNORECASE,
    )
    # 2. Break before numbered questions at word boundary: " 1. ", " 2) ", " 1(a) "
    text = re.sub(
        r"(?<=[^\n])\s+(\b\d{1,2}[\.\)]\s*(?:\([a-zA-Z0-9]+\))?)",
        r"\n\1",
        text,
    )
    # 3. Break before sub-question letters e.g. " (a) ", " (b) ", " (i) ", " (ii) "
    text = re.sub(
        r"(?<=[^\n])\s+(\([a-z0-9]{1,3}\)\s*)",
        r"\n\1",
        text,
        flags=re.IGNORECASE,
    )
    # 4. Break before "OR" between elective questions
    text = re.sub(
        r"(?<=[^\n])\s+(\bOR\b|\b[O|o][R|r]\b)(?=\s+[A-Za-z0-9(Q])",
        r"\n\n--- OR ---\n",
        text,
    )
    # 5. Break after marks tags e.g. "[5 Marks]", "(7M)" if followed immediately by next question
    text = re.sub(
        r"(\[\s*\d+\s*(?:marks|m)?\s*\]|\(\s*\d+\s*(?:marks|m)?\s*\))\s+(?=(?:Q(?:uestion)?|\d+[\.\)]|\([a-zA-Z0-9]+\)))",
        r"\1\n",
        text,
        flags=re.IGNORECASE,
    )
    # Normalize excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_text_from_pdf(file_path: str) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Extracts text from a given PDF file using PyMuPDF and optional OCR fallback.
    Preserves natural reading order via block sorting and prevents inline question merging.
    """
    if not os.path.exists(file_path):
        raise ValueError("File not found on server. Please try uploading again.")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise ValueError(
            f"File size ({file_size_mb:.1f} MB) exceeds maximum allowed size ({MAX_UPLOAD_SIZE_MB} MB). "
            "Try splitting the PDF or compressing it at ilovepdf.com."
        )

    if not FITZ_AVAILABLE:
        raise ValueError("PDF text extraction engine is not available on this server.")

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        logger.warning(f"Could not open PDF {file_path}: {e}")
        raise ValueError("Could not read this PDF. It may be corrupted, password-protected, or in an unsupported format.")

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise ValueError("The uploaded PDF appears to have no pages.")

    full_text_parts = []
    is_ocr = False

    for page_num in range(page_count):
        page = doc[page_num]
        try:
            # Use sort=True on blocks to preserve natural top-to-bottom reading order in two-column PDFs
            blocks = page.get_text("blocks", sort=True)
            block_texts = []
            for b in blocks:
                if len(b) >= 5 and b[4] and b[4].strip():
                    block_texts.append(b[4].strip())
            if block_texts:
                page_text = "\n".join(block_texts)
            else:
                page_text = page.get_text("text").strip()
        except Exception:
            page_text = page.get_text("text").strip()

        if page_text:
            cleaned_page = preprocess_extracted_exam_text(page_text)
            full_text_parts.append(cleaned_page)

    combined_text = "\n\n".join(full_text_parts).strip()

    # If PyMuPDF returned minimal text and OCR is available, try OCR
    if len(combined_text) < 60 and OCR_AVAILABLE:
        logger.info(f"PDF {file_path} appears scanned. Attempting OCR...")
        try:
            ocr_text_parts = []
            for page_num in range(min(page_count, 15)):  # Cap OCR to first 15 pages to prevent server timeout
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                ocr_page_text = pytesseract.image_to_string(image)
                if ocr_page_text.strip():
                    ocr_text_parts.append(ocr_page_text.strip())

            ocr_combined = "\n\n".join(ocr_text_parts).strip()
            if len(ocr_combined) >= 40:
                combined_text = ocr_combined
                is_ocr = True
        except Exception as ocr_err:
            logger.info(f"Tesseract OCR skipped on PDF {file_path}: {ocr_err}")

    doc.close()

    is_scanned = len(combined_text) < 60
    if is_scanned:
        is_ocr = True

    metadata = {
        "page_count": page_count,
        "char_count": len(combined_text),
        "word_count": len(combined_text.split()),
        "file_size_mb": round(file_size_mb, 2),
        "is_scanned": is_scanned,
    }

    return combined_text, is_ocr, metadata


def is_scanned_pdf(file_path: str) -> bool:
    """Returns True if the PDF has pages but contains less than 60 characters of text across first pages."""
    if not FITZ_AVAILABLE or not os.path.exists(file_path):
        return False
    try:
        doc = fitz.open(file_path)
        if len(doc) == 0:
            doc.close()
            return False
        sample_text = ""
        for p in doc[:3]:
            sample_text += p.get_text("text").strip()
        doc.close()
        return len(sample_text) < 60
    except Exception:
        return False


def render_pdf_pages_as_images(file_path: str, max_pages: int = 5, dpi: int = 150) -> List[Any]:
    """
    Renders the first max_pages of a PDF into PIL Images for Gemini Multimodal Vision.
    Enables 100% reliable extraction from scanned papers and CamScanner PDFs.
    """
    if not FITZ_AVAILABLE or not os.path.exists(file_path):
        return []
    try:
        from PIL import Image
        import io
        doc = fitz.open(file_path)
        images = []
        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
        doc.close()
        return images
    except Exception as e:
        logger.warning(f"Could not render PDF pages as images: {e}")
        return []


def extract_text_from_file(file_path: str) -> Tuple[str, bool, Dict[str, Any]]:
    """Universal extractor handling PDF and image files (JPG, PNG, WEBP)."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return extract_text_from_image(file_path)
    return extract_text_from_pdf(file_path)

