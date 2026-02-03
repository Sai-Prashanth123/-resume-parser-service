from __future__ import annotations

import re
import unicodedata


_BULLET_CHARS = ("\u2022", "\u2023", "\u25E6", "\u25AA", "\u25CF", "\u2043", "\u2219", "\uf0b7")


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)

    text = (
        text.replace("│", "|")
        .replace("¦", "|")
        .replace("｜", "|")
    )

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    text = text.replace("\uFFFD", "-")

    for b in _BULLET_CHARS:
        text = text.replace(b, "•")

    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2212", "-")
    )

    text = re.sub(r"(?<=\w)-\n(?=\w)", "-", text)

    lines = text.split("\n")
    merged: list[str] = []
    for ln in lines:
        s = ln.rstrip()
        if not s:
            merged.append("")
            continue
        if s.strip() == "•":
            merged.append("•")
            continue
        if merged and not s.lstrip().startswith("•") and merged[-1].lstrip().startswith("•"):
            stripped = s.strip()
            if ln.startswith((" ", "\t")) and not (
                stripped.isupper() and 3 <= len(stripped) <= 80 and "," not in stripped
            ):
                merged[-1] = (merged[-1].rstrip() + " " + stripped).strip()
                continue
        merged.append(s)

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

    text = re.sub(r"\n{3,}", "\n\n", text)

    text = "\n".join(re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in text.split("\n"))

    return text.strip()
