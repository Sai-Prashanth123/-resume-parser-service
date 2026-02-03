
import os

from app.parsing.text_extract import extract_text_and_meta
from app.parsing.sectioner import split_sections
from app.parsing.personal import extract_personal
from app.parsing.experience import parse_experience
from app.parsing.education import parse_education
from app.parsing.skills import consolidate_skills
from app.parsing.social_links import extract_social_links
from app.parsing.postprocess import postprocess_result
from app.parsing.nlp_enrich import enrich_experience_entries


def _truncate(s: str, limit: int) -> tuple[str, bool]:
    if s is None:
        return "", False
    if limit <= 0:
        return "", True
    if len(s) <= limit:
        return s, False
    return s[:limit], True

def _to_profile_service_shape(result: dict) -> dict:
    if result is None:
        return {
            "personalDetails": None,
            "professionalSummary": None,
            "workExperiences": [],
            "educations": [],
            "skills": [],
            "socialLinks": [],
        }

    personal = result.get("personalDetails") or result.get("personal") or {}
    if "phone" in personal and "phoneNumber" not in personal:
        personal["phoneNumber"] = personal.get("phone")

    work = result.get("workExperiences") or result.get("workExperience") or result.get("experience") or []
    edu = result.get("educations") or result.get("education") or []

    normalized_work = []
    for item in work or []:
        if not isinstance(item, dict):
            continue
        if "isCurrentlyWorking" in item and "isCurrent" not in item:
            item["isCurrent"] = item.get("isCurrentlyWorking")
        normalized_work.append(item)

    normalized_edu = []
    for item in edu or []:
        if not isinstance(item, dict):
            continue
        if "institution" in item and "schoolName" not in item:
            item["schoolName"] = item.get("institution")
        normalized_edu.append(item)

    out = {
        "personalDetails": personal if personal else None,
        "professionalSummary": result.get("professionalSummary") or result.get("summary") or None,
        "workExperiences": normalized_work,
        "educations": normalized_edu,
        "skills": result.get("skills") or [],
        "socialLinks": result.get("socialLinks") or [],
        "meta": result.get("meta") or {},
    }
    return out

def _convert_date_to_frontend_format(date_str):
    if not date_str:
        return None
    
    import re
    from datetime import datetime
    from dateutil import parser as date_parser

    date_str = (date_str or "").strip()
    if not date_str:
        return None

    date_str = date_str.replace("–", "-").replace("—", "-")
    date_str = re.sub(r"[\(\)]", "", date_str).strip()

    if re.fullmatch(r"(present|current|now)", date_str, flags=re.I):
        return None

    mm_yyyy_match = re.fullmatch(r"(\d{1,2})/(\d{4})", date_str)
    if mm_yyyy_match:
        month, year = mm_yyyy_match.groups()
        return f"{year}-{int(month):02d}-01"

    year_match = re.fullmatch(r"(\d{4})", date_str)
    if year_match:
        return f"{date_str}-01-01"

    try:
        default = datetime(2000, 1, 1)
        dt = date_parser.parse(date_str, default=default, fuzzy=True, dayfirst=False)
        return f"{dt.year:04d}-{dt.month:02d}-01"
    except Exception:
        return date_str

def _extract_professional_summary(sections, raw_text):
    for key in ['summary', 'objective', 'profile', 'about']:
        if key in sections and sections[key].strip():
            summary_text = sections[key].strip()
            summary_text = " ".join(summary_text.split())
            return summary_text[:1200] if len(summary_text) > 1200 else summary_text
    
    lines = raw_text.split('\n')
    
    section_start_line = -1
    section_keywords = ['experience', 'education', 'skills', 'technical skills', 'projects', 'certifications']
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in section_keywords):
            section_start_line = i
            break
    
    if section_start_line > 5:
        summary_lines = []
        for i in range(5, min(section_start_line, 20)):
            line = lines[i].strip()
            if line and not line.endswith(':') and len(line) > 20:
                summary_lines.append(line)
        
        if summary_lines:
            summary_text = ' '.join(summary_lines)
            summary_text = " ".join(summary_text.split())
            return summary_text[:1200] if len(summary_text) > 1200 else summary_text
    
    return None

def parse_resume(payload: dict) -> dict:
    raw_text, extract_meta = extract_text_and_meta(payload)
    
    sections = split_sections(raw_text)
    personal = extract_personal(raw_text)

    exp_text = sections.get("experience", "") or ""
    for alt in ("volunteering", "leadership", "internships"):
        if sections.get(alt):
            exp_text += "\n\n" + (sections.get(alt) or "")

    experience = parse_experience(exp_text)
    experience = enrich_experience_entries(experience, exp_text, raw_text)
    education = parse_education(sections.get("education", ""))
    skills = consolidate_skills(sections, experience, education)
    social_links = extract_social_links(raw_text)
    professional_summary = _extract_professional_summary(sections, raw_text)

    meta_section_chars = int(os.getenv("RESUME_PARSER_META_SECTION_CHARS", "4000"))
    meta_raw_text_chars = int(os.getenv("RESUME_PARSER_META_RAWTEXT_CHARS", "2000"))
    raw_preview, raw_truncated = _truncate(raw_text, meta_raw_text_chars)
    raw_sections_meta: dict = {}
    for k, v in sections.items():
        preview, truncated = _truncate(v, meta_section_chars)
        raw_sections_meta[k] = {
            "length": len(v or ""),
            "preview": preview,
            "truncated": truncated,
        }
    
    for exp in experience:
        if exp.get('startDate'):
            exp['startDate'] = _convert_date_to_frontend_format(exp['startDate'])
        if exp.get('endDate'):
            exp['endDate'] = _convert_date_to_frontend_format(exp['endDate'])
    
    for edu in education:
        if edu.get('startDate'):
            edu['startDate'] = _convert_date_to_frontend_format(edu['startDate'])
        if edu.get('endDate'):
            edu['endDate'] = _convert_date_to_frontend_format(edu['endDate'])

    parsed = {
        "personal": personal,
        "professionalSummary": professional_summary,
        "experience": experience,
        "education": education,
        "skills": skills,
        "socialLinks": social_links,
        "meta": {
            "sectionsFound": list(sections.keys()),
            "partial": not experience or not education,
            "parsed": True,
            "parser": "regex",
            "document": extract_meta,
            "rawText": {
                "length": len(raw_text or ""),
                "preview": raw_preview,
                "truncated": raw_truncated,
            },
            "rawSections": raw_sections_meta,
        }
    }

    parsed = postprocess_result(parsed)

    return _to_profile_service_shape(parsed)
