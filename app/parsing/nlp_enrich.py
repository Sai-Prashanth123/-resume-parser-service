from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("resume-parser")

_NLP = None
_NLP_UNAVAILABLE = False


def _should_use_nlp() -> bool:
    flag = os.getenv("RESUME_PARSER_USE_NLP", "true").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _get_nlp():
    global _NLP, _NLP_UNAVAILABLE
    if _NLP is not None or _NLP_UNAVAILABLE:
        return _NLP

    try:
        import spacy
    except ImportError:
        _NLP_UNAVAILABLE = True
        logger.warning(
            "spaCy not installed. NLP enrichment disabled. Install with: pip install spacy && python -m spacy download en_core_web_sm"
        )
        return None

    model_name = os.getenv("RESUME_PARSER_SPACY_MODEL", "en_core_web_sm")
    try:
        _NLP = spacy.load(model_name)
    except OSError:
        _NLP_UNAVAILABLE = True
        logger.warning(
            "spaCy model '%s' not found. NLP enrichment disabled. Run: python -m spacy download %s",
            model_name, model_name,
        )
        _NLP = None
    return _NLP


def _clean(s: Optional[str]) -> str:
    return (s or "").strip()


_MAX_SNIPPET_CHARS = 800


def _find_entry_block_in_text(exp_text: str, job_title: str, employer: str) -> str:
    if not exp_text or not (job_title or employer):
        return ""
    search_terms = [t for t in (job_title, employer) if t and len(t) >= 3]
    if not search_terms:
        return ""
    blocks = exp_text.split("\n\n")
    for block in blocks:
        block_lower = block.lower()
        if any(term.lower() in block_lower for term in search_terms):
            return block[:_MAX_SNIPPET_CHARS]
    return ""


def enrich_experience_entries(
    entries: List[Dict[str, Any]] | None,
    exp_text: str,
    raw_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not entries:
        return []

    if not _should_use_nlp():
        return list(entries)

    nlp = _get_nlp()
    if nlp is None:
        return list(entries)

    out: List[Dict[str, Any]] = []
    for e in entries:
        if not isinstance(e, dict):
            out.append(e)
            continue

        item = dict(e)
        header_bits: list[str] = []
        for key in ("jobTitle", "employer", "city"):
            val = _clean(item.get(key))
            if val:
                header_bits.append(val)

        desc = _clean(item.get("description"))
        if desc:
            desc_snippet = desc.replace("\n", " ").strip()[:_MAX_SNIPPET_CHARS]
            header_bits.append(desc_snippet)
        elif exp_text:
            block = _find_entry_block_in_text(exp_text, item.get("jobTitle") or "", item.get("employer") or "")
            if block:
                header_bits.append(block)

        snippet = " | ".join(header_bits).strip()
        if not snippet:
            out.append(item)
            continue

        doc = nlp(snippet)
        ents = getattr(doc, "ents", []) or []

        if not _clean(item.get("employer")):
            orgs = [ent.text.strip() for ent in ents if ent.label_ == "ORG"]
            if orgs:
                best = max(orgs, key=lambda x: (len(x) >= 3, len(x)))
                if len(best) >= 2:
                    item["employer"] = best

        if not _clean(item.get("city")):
            locs = [ent.text.strip() for ent in ents if ent.label_ in {"GPE", "LOC"}]
            if locs:
                skip_regions = ("united states", "united kingdom", "north america", "europe", "asia")
                bad_tokens = {"ai", "ml", "dl", "city"}

                def _is_valid_city_token(text: str) -> bool:
                    t = (text or "").strip()
                    if not t:
                        return False
                    low = t.lower()
                    if low in bad_tokens:
                        return False
                    if any(x in low for x in skip_regions):
                        return False
                    # Require at least 3 characters of signal.
                    if len(t) < 3:
                        return False
                    return True

                candidates = [t for t in locs if _is_valid_city_token(t)]
                if candidates:
                    # Prefer shorter, city-like strings once filtered.
                    item["city"] = min(candidates, key=len)
                else:
                    # Fall back only if the first LOC/GPE looks reasonable.
                    first = locs[0]
                    item["city"] = first if _is_valid_city_token(first) else item.get("city")

        out.append(item)

    return out
