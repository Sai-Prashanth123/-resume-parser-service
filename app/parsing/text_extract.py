
import io
import os
import hashlib
import fitz
from PIL import Image
import pytesseract
from app.s3_client import get_s3_for_bucket
from docx import Document
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from app.parsing.normalize import normalize_text

def _download_bytes_from_presigned_url(url: str) -> bytes:
    try:
        with urlopen(url, timeout=60) as resp:
            return resp.read()
    except HTTPError as e:
        raise RuntimeError(f"Failed to download resume (HTTP {e.code})") from e
    except URLError as e:
        raise RuntimeError("Failed to download resume (network error)") from e

def extract_text_and_meta(payload) -> tuple[str, dict]:
    # Preferred: use pre-signed URL provided by profile-service (no AWS creds needed here)
    presigned = payload.get("s3PresignedUrl") or payload.get("presignedUrl") or payload.get("s3Url")
    if presigned:
        data = _download_bytes_from_presigned_url(presigned)
    else:
        bucket = payload["s3Bucket"]
        key = payload["s3Key"]
        s3 = get_s3_for_bucket(bucket)
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
    ft = payload["fileType"].upper()

    meta: dict = {
        "fileType": ft,
        "bytesLength": len(data) if data is not None else None,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "ocr": {},
        "pages": None,
        "truncatedToMaxPages": False,
    }

    if ft == "PDF":
        # OCR strategy:
        # - "auto" (default): only OCR pages with no extractable text
        # - "never": never OCR
        # - "always": OCR every page (slow; use only when needed)
        ocr_mode = os.getenv("RESUME_PARSER_OCR", "auto").lower()
        max_pages = int(os.getenv("RESUME_PARSER_MAX_PAGES", "50"))
        ocr_dpi = int(os.getenv("RESUME_PARSER_OCR_DPI", "200"))

        doc = fitz.open(stream=data, filetype="pdf")
        meta["pages"] = doc.page_count
        meta["ocr"] = {"mode": ocr_mode, "dpi": ocr_dpi, "pagesOcred": 0, "pagesWithText": 0}

        page_texts: list[str] = []
        for idx, page in enumerate(doc):
            if idx >= max_pages:
                meta["truncatedToMaxPages"] = True
                break
            txt = (page.get_text("text") or "").strip()
            if txt and ocr_mode != "always":
                meta["ocr"]["pagesWithText"] += 1
                page_texts.append(txt)
                continue

            # OCR fallback for scanned/empty-text PDFs (only when needed)
            if ocr_mode == "never":
                if txt:
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)
                continue
            try:
                pix = page.get_pixmap(dpi=ocr_dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr = (pytesseract.image_to_string(img) or "").strip()
                if ocr:
                    meta["ocr"]["pagesOcred"] += 1
                    page_texts.append(ocr)
                elif txt:
                    # Keep the extracted text if OCR returned nothing
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)
            except Exception:
                # If OCR fails, keep empty for this page
                if txt:
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)

        return normalize_text("\n\n".join(page_texts)), meta
    if ft == "DOCX":
        return normalize_text("\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)), meta
    if ft in ["JPG","PNG","JPEG"]:
        return normalize_text(pytesseract.image_to_string(Image.open(io.BytesIO(data)))), meta
    return normalize_text(data.decode(errors="ignore")), meta


def extract_text(payload):
    text, _meta = extract_text_and_meta(payload)
    return text
