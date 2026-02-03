
import io
import os
import hashlib
import re
import zipfile
from xml.etree import ElementTree as ET
import fitz
from PIL import Image
import pytesseract
from app.s3_client import get_s3_for_bucket
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from app.parsing.normalize import normalize_text

def _text_quality_metrics(text: str) -> dict:
    if not text:
        return {"length": 0, "alphaRatio": 0.0, "digitRatio": 0.0, "lineCount": 0}
    s = text
    length = len(s)
    alpha = sum(ch.isalpha() for ch in s)
    digit = sum(ch.isdigit() for ch in s)
    line_count = s.count("\n") + 1
    return {
        "length": length,
        "alphaRatio": (alpha / length) if length else 0.0,
        "digitRatio": (digit / length) if length else 0.0,
        "lineCount": line_count,
    }

def _pdf_layout_text(page: fitz.Page) -> str:
    try:
        blocks = page.get_text("blocks") or []
        blocks_sorted = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
        parts: list[str] = []
        for b in blocks_sorted:
            t = (b[4] or "").strip()
            if t:
                parts.append(t)
        return "\n".join(parts).strip()
    except Exception:
        return (page.get_text("text") or "").strip()

def _ocr_image_to_text(img: Image.Image) -> str:
    try:
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        gray = img.convert("L")
        cfg = os.getenv("RESUME_PARSER_OCR_TESSERACT_CONFIG", "--oem 3 --psm 6")
        return (pytesseract.image_to_string(gray, config=cfg) or "").strip()
    except Exception:
        return (pytesseract.image_to_string(img) or "").strip()

def _normalize_file_type(file_type: str | None) -> str:
    if not file_type:
        raise RuntimeError("fileType is required")

    ft = (file_type or "").strip()
    if not ft:
        raise RuntimeError("fileType is required")

    ft_lower = ft.lower()

    if "/" in ft_lower:
        if ft_lower == "application/pdf":
            return "PDF"
        if ft_lower == "application/msword" or "msword" in ft_lower:
            return "DOC"
        if "officedocument.wordprocessingml.document" in ft_lower or "wordprocessingml" in ft_lower:
            return "DOCX"
        if "image/png" in ft_lower or ft_lower.endswith("png"):
            return "PNG"
        if "image/jpeg" in ft_lower or "image/jpg" in ft_lower or "jpeg" in ft_lower or "jpg" in ft_lower:
            return "JPG"

    token = ft_lower[1:] if ft_lower.startswith(".") else ft_lower
    if token in {"pdf", "docx", "doc", "png", "jpg", "jpeg"}:
        return token.upper() if token != "jpeg" else "JPEG"

    upper = ft.upper()
    if upper in {"PDF", "DOCX", "DOC", "PNG", "JPG", "JPEG"}:
        return upper

    raise RuntimeError(f"Unsupported fileType: {file_type}")

def _iter_block_items(parent):
    parent_elm = getattr(parent, "element", None)
    if parent_elm is not None and hasattr(parent_elm, "body"):
        parent_elm = parent_elm.body
    else:
        parent_elm = getattr(parent, "_element", None) or getattr(parent, "element", None)

    if parent_elm is None:
        return

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def _paragraph_text(p: Paragraph) -> str:
    parts: list[str] = []
    try:
        for node in p._p.iter():
            tag = getattr(node, "tag", "")
            if tag.endswith("}t"):
                if node.text:
                    parts.append(node.text)
            elif tag.endswith("}tab"):
                parts.append("\t")
            elif tag.endswith("}br") or tag.endswith("}cr"):
                parts.append("\n")
    except Exception:
        return p.text or ""

    return "".join(parts)

def _is_list_paragraph(p: Paragraph) -> bool:
    try:
        ppr = p._p.pPr
        if ppr is not None and getattr(ppr, "numPr", None) is not None:
            return True
    except Exception:
        pass
    try:
        style_name = (p.style.name or "").lower() if p.style is not None else ""
        if "list" in style_name or "bullet" in style_name or "number" in style_name:
            return True
    except Exception:
        pass
    return False

def _docx_to_text(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    lines: list[str] = []

    def add_line(s: str):
        s = (s or "").replace("\t", " ").strip()
        if not s:
            lines.append("")
            return
        if len(s) <= 3 and not re.search(r"[A-Za-z@+]", s):
            return
        lines.append(s)

    include_headers = os.getenv("RESUME_PARSER_DOCX_INCLUDE_HEADERS", "true").lower() in {"1", "true", "yes"}
    if include_headers:
        try:
            for sec in doc.sections:
                for p in getattr(sec.header, "paragraphs", []) or []:
                    add_line(_paragraph_text(p))
                for p in getattr(sec.footer, "paragraphs", []) or []:
                    add_line(_paragraph_text(p))
        except Exception:
            pass
        if lines:
            lines.append("")

    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            txt = (_paragraph_text(block) or "").strip()
            if not txt:
                continue
            prefix = "- " if _is_list_paragraph(block) else ""
            if prefix and txt.lstrip().startswith(("-", "•", "*")):
                prefix = ""
            add_line(prefix + txt)
        elif isinstance(block, Table):
            if lines and lines[-1] != "":
                lines.append("")
            try:
                for row in block.rows:
                    cell_texts: list[str] = []
                    for cell in row.cells:
                        cell_parts = []
                        for cp in cell.paragraphs:
                            t = (_paragraph_text(cp) or "").strip()
                            if t:
                                cell_parts.append(t)
                        cell_texts.append(" ".join(cell_parts).strip())
                    row_line = " | ".join(t for t in cell_texts if t)
                    if row_line.strip():
                        add_line(row_line)
            except Exception:
                try:
                    add_line(block._tbl.text)
                except Exception:
                    pass
            lines.append("")

    return "\n".join(lines).strip()

def _docx_extract_contact_hints(data: bytes) -> list[str]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return []

    candidates = []
    for name in z.namelist():
        n = name.lower()
        if not n.endswith(".xml"):
            continue
        if n.startswith("word/") and (
            "document.xml" in n
            or "header" in n
            or "footer" in n
            or "footnotes" in n
            or "endnotes" in n
        ):
            candidates.append(name)

    raw_texts: list[str] = []
    for name in candidates:
        try:
            xml_bytes = z.read(name)
            root = ET.fromstring(xml_bytes.decode("utf-8", errors="ignore"))
            for el in root.iter():
                tag = getattr(el, "tag", "")
                if isinstance(tag, str) and tag.endswith("}t"):
                    if el.text:
                        raw_texts.append(el.text)
        except Exception:
            continue

    blob = " ".join(raw_texts)
    if not blob:
        return []

    emails = set(re.findall(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", blob))
    urls = set(re.findall(r"\bhttps?://[^\s)>\"]+\b", blob, flags=re.I))
    urls |= set(re.findall(r"\b(?:www\.)?(?:linkedin\.com|github\.com|bitbucket\.org|gitlab\.com)/[^\s|,;]+", blob, flags=re.I))

    phone_patterns = [
        r"\+\d{1,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}[\s.-]?\d{4}",
        r"\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}",
        r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b",
        r"\+\d{10,15}",
    ]
    phones = set()
    for pat in phone_patterns:
        for m in re.findall(pat, blob):
            phones.add(m.strip())

    hints: list[str] = []
    for e in sorted(emails):
        hints.append(e)
    for p in sorted(phones):
        hints.append(p)
    for u in sorted(urls):
        hints.append(u)

    return hints[:12]

def _download_bytes_from_presigned_url(url: str) -> bytes:
    try:
        with urlopen(url, timeout=60) as resp:
            return resp.read()
    except HTTPError as e:
        raise RuntimeError(f"Failed to download resume (HTTP {e.code})") from e
    except URLError as e:
        raise RuntimeError("Failed to download resume (network error)") from e

def extract_text_and_meta(payload) -> tuple[str, dict]:
    presigned = payload.get("s3PresignedUrl") or payload.get("presignedUrl") or payload.get("s3Url")
    if presigned:
        data = _download_bytes_from_presigned_url(presigned)
    else:
        bucket = payload["s3Bucket"]
        key = payload["s3Key"]
        s3 = get_s3_for_bucket(bucket)
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
    ft = _normalize_file_type(payload.get("fileType"))

    meta: dict = {
        "fileType": ft,
        "bytesLength": len(data) if data is not None else None,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "ocr": {},
        "pages": None,
        "truncatedToMaxPages": False,
    }

    if ft == "PDF":
        ocr_mode = os.getenv("RESUME_PARSER_OCR", "auto").lower()
        max_pages = int(os.getenv("RESUME_PARSER_MAX_PAGES", "50"))
        ocr_dpi = int(os.getenv("RESUME_PARSER_OCR_DPI", "200"))

        doc = fitz.open(stream=data, filetype="pdf")
        meta["pages"] = doc.page_count
        meta["ocr"] = {"mode": ocr_mode, "dpi": ocr_dpi, "pagesOcred": 0, "pagesWithText": 0}
        meta["pdf"] = {"extractMode": os.getenv("RESUME_PARSER_PDF_EXTRACT_MODE", "auto").lower()}

        page_texts: list[str] = []
        for idx, page in enumerate(doc):
            if idx >= max_pages:
                meta["truncatedToMaxPages"] = True
                break
            extract_mode = meta["pdf"]["extractMode"]
            txt_simple = (page.get_text("text") or "").strip()
            txt_layout = _pdf_layout_text(page) if extract_mode in {"auto", "layout"} else ""

            if extract_mode == "layout":
                txt = txt_layout
            elif extract_mode == "text":
                txt = txt_simple
            else:
                m_simple = _text_quality_metrics(txt_simple)
                m_layout = _text_quality_metrics(txt_layout)
                score_simple = m_simple["length"] + int(2000 * m_simple["alphaRatio"])
                score_layout = m_layout["length"] + int(2000 * m_layout["alphaRatio"])
                txt = txt_layout if score_layout >= score_simple else txt_simple

            if txt and ocr_mode != "always":
                meta["ocr"]["pagesWithText"] += 1
                page_texts.append(txt)
                continue

            if ocr_mode == "never":
                if txt:
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)
                continue
            try:
                pix = page.get_pixmap(dpi=ocr_dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr = _ocr_image_to_text(img)
                if ocr:
                    meta["ocr"]["pagesOcred"] += 1
                    page_texts.append(ocr)
                elif txt:
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)
            except Exception:
                if txt:
                    meta["ocr"]["pagesWithText"] += 1
                    page_texts.append(txt)

        return normalize_text("\n\n".join(page_texts)), meta
    if ft == "DOCX":
        hints = _docx_extract_contact_hints(data)
        body = _docx_to_text(data)
        if hints:
            meta["docx"] = {"contactHintsAdded": len(hints)}
            combined = "\n".join(hints) + "\n\n" + body
        else:
            meta["docx"] = {"contactHintsAdded": 0}
            combined = body
        return normalize_text(combined), meta
    if ft == "DOC":
        raise RuntimeError("Legacy .doc files are not supported. Please upload a .docx file.")
    if ft in ["JPG","PNG","JPEG"]:
        return normalize_text(pytesseract.image_to_string(Image.open(io.BytesIO(data)))), meta
    return normalize_text(data.decode(errors="ignore")), meta


def extract_text(payload):
    text, _meta = extract_text_and_meta(payload)
    return text
