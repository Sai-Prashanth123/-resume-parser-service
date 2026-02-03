from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from dateutil import parser as date_parser


def _parse_date_loose(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return date_parser.parse(str(s), default=datetime(2000, 1, 1), fuzzy=True)
    except Exception:
        return None


def _dedupe_list_of_dicts(items: list[dict], key_fields: list[str]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        key = tuple((it.get(f) or "").strip().lower() if isinstance(it.get(f), str) else it.get(f) for f in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _sort_experience(items: list[dict]) -> list[dict]:
    def key(it: dict):
        sd = _parse_date_loose(it.get("startDate"))
        ed = _parse_date_loose(it.get("endDate"))
        is_current = bool(it.get("isCurrent")) or (it.get("endDate") in (None, "", "null") and sd is not None)
        return (
            0 if is_current else 1,
            -(sd.timestamp() if sd else 0),
            -(ed.timestamp() if ed else 0),
        )

    return sorted(items, key=key)


def _sort_education(items: list[dict]) -> list[dict]:
    def key(it: dict):
        ed = _parse_date_loose(it.get("endDate"))
        sd = _parse_date_loose(it.get("startDate"))
        return (-(ed.timestamp() if ed else 0), -(sd.timestamp() if sd else 0))

    return sorted(items, key=key)


def _split_inline_promotions_title(title: str | None) -> list[str]:
    if not title or not isinstance(title, str):
        return []
    parts = re.split(r"\s*(?:→|->|/)\s*", title)
    return [p.strip() for p in parts if p and p.strip()]


def _collect_experience_warnings(items: list[dict]) -> list[str]:
    warnings: list[str] = []

    def _looks_full_time(e: dict) -> bool:
        title = (e.get("jobTitle") or "").lower()
        return not any(tok in title for tok in ("part-time", "part time", "intern", "internship", "contract"))

    for i, a in enumerate(items):
        if not _looks_full_time(a):
            continue
        sa = _parse_date_loose(a.get("startDate"))
        ea = _parse_date_loose(a.get("endDate")) or (datetime.max if a.get("isCurrent") else None)
        if not sa or not ea:
            continue
        for b in items[i + 1 :]:
            if not _looks_full_time(b):
                continue
            sb = _parse_date_loose(b.get("startDate"))
            eb = _parse_date_loose(b.get("endDate")) or (datetime.max if b.get("isCurrent") else None)
            if not sb or not eb:
                continue
            latest_start = max(sa, sb)
            earliest_end = min(ea, eb)
            if latest_start <= earliest_end:
                msg = (
                    f"Overlapping full-time roles: "
                    f"{a.get('jobTitle')} at {a.get('employer')} and "
                    f"{b.get('jobTitle')} at {b.get('employer')}."
                )
                warnings.append(msg)
                break
    return warnings


def _description_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0

    def _tokens(s: str) -> set[str]:
        return {
            w
            for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(w) >= 3
        }

    sa = _tokens(a)
    sb = _tokens(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    if inter == 0:
        return 0.0
    union = len(sa | sb)
    return inter / union if union else 0.0


def _dedupe_near_duplicate_experience(items: list[dict], threshold: float = 0.8) -> list[dict]:
    out: list[dict] = []
    for e in items:
        if not isinstance(e, dict):
            continue
        is_dup = False
        title_e = (e.get("jobTitle") or "").strip().lower()
        employer_e = (e.get("employer") or "").strip().lower()
        desc_e = e.get("description") or ""
        for kept in out:
            title_k = (kept.get("jobTitle") or "").strip().lower()
            employer_k = (kept.get("employer") or "").strip().lower()
            if not title_e or not employer_e:
                continue
            if title_e != title_k or employer_e != employer_k:
                continue
            sim = _description_similarity(desc_e, kept.get("description") or "")
            if sim >= threshold:
                is_dup = True
                break
        if not is_dup:
            out.append(e)
    return out


def postprocess_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result

    personal = result.get("personal") or result.get("personalDetails")
    if isinstance(personal, dict):
        p = dict(personal)
        p.setdefault("address", "")
        p.setdefault("city", "")
        p.setdefault("country", "")
        for k, v in list(p.items()):
            if isinstance(v, str) and not v.strip():
                if k in {"address", "city", "country"}:
                    p[k] = ""
                else:
                    p[k] = None
        result["personal"] = p

    exp = result.get("experience") or result.get("workExperiences") or []
    if isinstance(exp, list):
        cleaned = []
        for e in exp:
            if not isinstance(e, dict):
                continue
            e = dict(e)
            title_raw = (e.get("jobTitle") or "").strip()
            employer_raw = (e.get("employer") or "").strip()
            desc_raw = (e.get("description") or "").strip()
            lower_all = f"{title_raw} {employer_raw} {desc_raw}".lower()

            # Drop obvious non-employment noise that comes from project / GitHub lines
            # when there are no dates at all.
            if not e.get("startDate") and not e.get("endDate"):
                url_tokens = ("github.com", "gitlab.com", "bitbucket.org", "sourceforge.net")
                if any(tok in lower_all for tok in url_tokens):
                    continue
                # Template/project labels that should not appear as jobs.
                if title_raw.lower() in {"university projects", "academic projects"}:
                    continue

            for k, v in list(e.items()):
                if isinstance(v, str) and not v.strip():
                    e[k] = None
            if e.get("endDate") in (None, "") and e.get("startDate"):
                if e.get("isCurrent") is None:
                    e["isCurrent"] = False
            cleaned.append(e)
        cleaned = _dedupe_list_of_dicts(cleaned, ["jobTitle", "employer", "startDate", "endDate"])
        cleaned = _sort_experience(cleaned)

        expanded: list[dict] = []
        for e in cleaned:
            roles = _split_inline_promotions_title(e.get("jobTitle"))
            if len(roles) <= 1:
                expanded.append(e)
                continue
            for idx, role in enumerate(roles):
                clone = dict(e)
                clone["jobTitle"] = role
                clone["isPromotion"] = idx > 0
                expanded.append(clone)
        cleaned = expanded

        cleaned = _dedupe_near_duplicate_experience(cleaned)

        result["experience"] = cleaned

        warnings = _collect_experience_warnings(cleaned)
        if warnings:
            meta = result.setdefault("meta", {})
            existing = meta.get("experienceWarnings") or []
            meta["experienceWarnings"] = existing + warnings

    edu = result.get("education") or result.get("educations") or []
    if isinstance(edu, list):
        cleaned = []
        for e in edu:
            if not isinstance(e, dict):
                continue
            e = dict(e)
            for k, v in list(e.items()):
                if isinstance(v, str) and not v.strip():
                    e[k] = None
            cleaned.append(e)
        cleaned = _dedupe_list_of_dicts(cleaned, ["schoolName", "degree", "endDate", "startDate"])
        cleaned = _sort_education(cleaned)
        result["education"] = cleaned

    skills = result.get("skills") or []
    if isinstance(skills, list):
        seen = set()
        uniq = []
        for s in skills:
            if not isinstance(s, dict):
                continue
            name = (s.get("skillName") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            uniq.append(s)
        result["skills"] = uniq

    return result
