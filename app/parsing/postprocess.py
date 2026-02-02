from __future__ import annotations

from datetime import datetime
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
        # Current jobs should float to top among equal start dates
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


def postprocess_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Enforce output consistency without inventing new content:
    - drop empty strings
    - set isCurrent when endDate is missing and 'present/current' logic likely applied upstream
    - dedupe skills/experience/education
    - sort experience/education by date
    """
    if not isinstance(result, dict):
        return result

    # Personal details: ensure stable shape and avoid stale merges downstream.
    personal = result.get("personal") or result.get("personalDetails")
    if isinstance(personal, dict):
        p = dict(personal)
        # Standard keys always present
        p.setdefault("address", "")
        p.setdefault("city", "")
        p.setdefault("country", "")
        # Drop whitespace-only
        for k, v in list(p.items()):
            if isinstance(v, str) and not v.strip():
                # Keep address/city/country as empty strings explicitly
                if k in {"address", "city", "country"}:
                    p[k] = ""
                else:
                    p[k] = None
        result["personal"] = p

    # Experience
    exp = result.get("experience") or result.get("workExperiences") or []
    if isinstance(exp, list):
        cleaned = []
        for e in exp:
            if not isinstance(e, dict):
                continue
            e = dict(e)
            for k, v in list(e.items()):
                if isinstance(v, str) and not v.strip():
                    e[k] = None
            if e.get("endDate") in (None, "") and e.get("startDate"):
                # Don't overwrite explicit isCurrent false if present
                if e.get("isCurrent") is None:
                    e["isCurrent"] = False
            cleaned.append(e)
        cleaned = _dedupe_list_of_dicts(cleaned, ["jobTitle", "employer", "startDate", "endDate"])
        cleaned = _sort_experience(cleaned)
        result["experience"] = cleaned

    # Education
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

    # Skills
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

