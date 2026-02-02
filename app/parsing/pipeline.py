
import os

from app.parsing.text_extract import extract_text_and_meta
from app.parsing.sectioner import split_sections
from app.parsing.personal import extract_personal
from app.parsing.experience import parse_experience
from app.parsing.education import parse_education
from app.parsing.skills import consolidate_skills
from app.parsing.social_links import extract_social_links
from app.parsing.postprocess import postprocess_result


def _truncate(s: str, limit: int) -> tuple[str, bool]:
    if s is None:
        return "", False
    if limit <= 0:
        return "", True
    if len(s) <= limit:
        return s, False
    return s[:limit], True

def _to_profile_service_shape(result: dict) -> dict:
    """
    Normalize parser output to the shape expected by profile-service (ResumeParseResultDTO):
      - personalDetails
      - professionalSummary
      - workExperiences
      - educations
      - skills
      - socialLinks
    """
    if result is None:
        return {
            "personalDetails": None,
            "professionalSummary": None,
            "workExperiences": [],
            "educations": [],
            "skills": [],
            "socialLinks": [],
        }

    # Common key renames
    personal = result.get("personalDetails") or result.get("personal") or {}
    if "phone" in personal and "phoneNumber" not in personal:
        personal["phoneNumber"] = personal.get("phone")

    work = result.get("workExperiences") or result.get("workExperience") or result.get("experience") or []
    edu = result.get("educations") or result.get("education") or []

    # Normalize experience items
    normalized_work = []
    for item in work or []:
        if not isinstance(item, dict):
            continue
        if "isCurrentlyWorking" in item and "isCurrent" not in item:
            item["isCurrent"] = item.get("isCurrentlyWorking")
        # If only "description" exists (regex fallback), keep it
        normalized_work.append(item)

    # Normalize education items
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
    """
    Convert various date formats to yyyy-mm-dd format for frontend.
    Handles: "January 2025", "Jan 2025", "01/2025", "2025"
    Returns: "2025-01-01" (first day of month if only month/year given)
    Frontend parseFlexibleDate expects yyyy-mm-dd format.
    """
    if not date_str:
        return None
    
    import re
    from datetime import datetime
    from dateutil import parser as date_parser

    date_str = (date_str or "").strip()
    if not date_str:
        return None

    # Normalize unicode dashes and remove parentheses
    date_str = date_str.replace("–", "-").replace("—", "-")
    date_str = re.sub(r"[\(\)]", "", date_str).strip()

    # Present/current should be represented as null endDate upstream
    if re.fullmatch(r"(present|current|now)", date_str, flags=re.I):
        return None

    # Parse mm/yyyy quickly
    mm_yyyy_match = re.fullmatch(r"(\d{1,2})/(\d{4})", date_str)
    if mm_yyyy_match:
        month, year = mm_yyyy_match.groups()
        return f"{year}-{int(month):02d}-01"

    # Parse bare year
    year_match = re.fullmatch(r"(\d{4})", date_str)
    if year_match:
        return f"{date_str}-01-01"

    # Fallback: dateutil fuzzy parsing for "May 2018", "Sep 2020", etc.
    try:
        default = datetime(2000, 1, 1)
        dt = date_parser.parse(date_str, default=default, fuzzy=True, dayfirst=False)
        # If the string contains only month+year (or only year), normalize to first day
        return f"{dt.year:04d}-{dt.month:02d}-01"
    except Exception:
        return date_str

def _extract_professional_summary(sections, raw_text):
    """Extract professional summary/objective from resume."""
    # Check for summary/objective sections
    for key in ['summary', 'objective', 'profile', 'about']:
        if key in sections and sections[key].strip():
            summary_text = sections[key].strip()
            # Normalize whitespace; allow longer summaries (avoid truncating mid-sentence)
            summary_text = " ".join(summary_text.split())
            return summary_text[:1200] if len(summary_text) > 1200 else summary_text
    
    # If no dedicated section, look for summary-like text after contact info
    lines = raw_text.split('\n')
    
    # Find where sections start (Experience, Education, Skills, etc.)
    section_start_line = -1
    section_keywords = ['experience', 'education', 'skills', 'technical skills', 'projects', 'certifications']
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in section_keywords):
            section_start_line = i
            break
    
    # Look for summary text between contact info (first 5 lines) and first section
    if section_start_line > 5:
        summary_lines = []
        for i in range(5, min(section_start_line, 20)):
            line = lines[i].strip()
            # Skip empty lines and section headers
            if line and not line.endswith(':') and len(line) > 20:
                summary_lines.append(line)
        
        if summary_lines:
            summary_text = ' '.join(summary_lines)
            summary_text = " ".join(summary_text.split())
            return summary_text[:1200] if len(summary_text) > 1200 else summary_text
    
    return None

def parse_resume(payload: dict) -> dict:
    # Extract text from S3 file
    raw_text, extract_meta = extract_text_and_meta(payload)
    
    # Use regex parser for resume parsing
    sections = split_sections(raw_text)
    personal = extract_personal(raw_text)
    experience = parse_experience(sections.get("experience",""))
    education = parse_education(sections.get("education",""))
    skills = consolidate_skills(sections, experience, education)
    social_links = extract_social_links(raw_text)
    professional_summary = _extract_professional_summary(sections, raw_text)

    # Always keep a bounded copy of raw sections in meta so nothing is "lost"
    # even when structured parsing misses edge-cases.
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
    
    # Convert dates to frontend format (dd-mm-yyyy)
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
            # Helps detect accidental cross-resume mixups or caching issues
            "document": extract_meta,
            "rawText": {
                "length": len(raw_text or ""),
                "preview": raw_preview,
                "truncated": raw_truncated,
            },
            "rawSections": raw_sections_meta,
        }
    }

    # Apply consistency rules (dedupe, sorting, etc.) before shaping for profile-service.
    parsed = postprocess_result(parsed)

    return _to_profile_service_shape(parsed)
