from __future__ import annotations

import re
import unicodedata


# Include common unicode bullets and the Wingdings bullet used in some PDFs (U+F0B7).
_BULLET_CHARS = ("\u2022", "\u2023", "\u25E6", "\u25AA", "\u25CF", "\u2043", "\u2219", "\uf0b7")


def normalize_text(text: str) -> str:
    """
    Normalize resume text (PDF/DOCX/OCR) for more reliable parsing.
    Goal: reduce formatting noise without losing semantic information.
    """
    if not text:
        return ""

    # Unicode normalization (fixes "smart quotes", compatibility glyphs, etc.)
    text = unicodedata.normalize("NFKC", text)

    # Normalize pipe/vertical separators (common in resumes)
    text = (
        text.replace("│", "|")   # box drawings light vertical
        .replace("¦", "|")       # broken bar
        .replace("｜", "|")      # fullwidth vertical line
    )

    # Newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Some PDF extractions show unknown glyphs; try to normalize common ones.
    # NOTE: we keep the U+FFFD replacement char as-is in general, but for date separators
    # it often stands in for an en-dash; normalize to hyphen to help date parsing.
    text = text.replace("\uFFFD", "-")

    # Normalize bullets to "•"
    for b in _BULLET_CHARS:
        text = text.replace(b, "•")

    # Normalize common dash variants (but keep em/en dashes in content)
    # Include non-breaking hyphen and minus sign variants too.
    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("\u2010", "-")  # hyphen
        .replace("\u2011", "-")  # non-breaking hyphen
        .replace("\u2212", "-")  # minus sign
    )

    # Fix hyphenated line breaks: "Cost-to-\nServe" -> "Cost-to-Serve"
    text = re.sub(r"(?<=\w)-\n(?=\w)", "-", text)

    # Merge wrapped bullet continuations:
    # "• did X\n  continued" -> "• did X continued"
    lines = text.split("\n")
    merged: list[str] = []
    for ln in lines:
        s = ln.rstrip()
        if not s:
            merged.append("")
            continue
        # Handle PDFs that emit a bullet alone on a line, then the text on the next line.
        # We'll keep the bullet and let the next line join logic attach the text.
        if s.strip() == "•":
            merged.append("•")
            continue
        if merged and not s.lstrip().startswith("•") and merged[-1].lstrip().startswith("•"):
            # If previous line is a bullet and current line is indented continuation, join.
            if ln.startswith((" ", "\t")):
                merged[-1] = (merged[-1].rstrip() + " " + s.strip()).strip()
                continue
        merged.append(s)

    # Second pass: "•" line followed by text -> "• text"
    fixed: list[str] = []
    i = 0
    while i < len(merged):
        cur = merged[i].strip()
        if cur == "•" and i + 1 < len(merged):
            nxt = merged[i + 1].strip()
            if nxt and not nxt.startswith("•"):
                fixed.append(f"• {nxt}")
                i += 2
                continue
        fixed.append(merged[i])
        i += 1
    text = "\n".join(fixed)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse repeated spaces/tabs within lines
    text = "\n".join(re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in text.split("\n"))

    return text.strip()

