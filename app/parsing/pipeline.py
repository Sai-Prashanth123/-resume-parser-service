
from app.parsing.text_extract import extract_text
from app.parsing.llm_parser import parse_with_llm
import os

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

def parse_resume(payload: dict) -> dict:
    # Extract text from S3 file
    raw_text = extract_text(payload)
    
    # Use LLM for parsing if GROQ_API_KEY is set, otherwise fallback to basic parser
    use_llm = os.getenv("GROQ_API_KEY") is not None
    
    if use_llm:
        try:
            # Use Groq LLM for intelligent parsing
            result = parse_with_llm(raw_text)
            return _to_profile_service_shape(result)
        except Exception as e:
            # If LLM fails, fallback to regex parser so flow still works.
            from app.parsing.sectioner import split_sections
            from app.parsing.personal import extract_personal
            from app.parsing.experience import parse_experience
            from app.parsing.education import parse_education
            from app.parsing.skills import consolidate_skills

            sections = split_sections(raw_text)
            personal = extract_personal(raw_text)
            experience = parse_experience(sections.get("experience",""))
            education = parse_education(sections.get("education",""))
            skills = consolidate_skills(sections, experience, education)

            return _to_profile_service_shape({
                "personal": personal,
                "experience": experience,
                "education": education,
                "skills": skills,
                "socialLinks": [],
                "meta": {
                    "sectionsFound": list(sections.keys()),
                    "partial": not experience or not education,
                    "parsed": True,
                    "parser": "regex",
                    "llmFailed": True,
                    "llmError": str(e),
                }
            })
    else:
        # Fallback to basic regex parser (not recommended for production)
        from app.parsing.sectioner import split_sections
        from app.parsing.personal import extract_personal
        from app.parsing.experience import parse_experience
        from app.parsing.education import parse_education
        from app.parsing.skills import consolidate_skills
        
        sections = split_sections(raw_text)
        personal = extract_personal(raw_text)
        experience = parse_experience(sections.get("experience",""))
        education = parse_education(sections.get("education",""))
        skills = consolidate_skills(sections, experience, education)

        return _to_profile_service_shape({
            "personal": personal,
            "experience": experience,
            "education": education,
            "skills": skills,
            "socialLinks": [],
            "meta": {
                "sectionsFound": list(sections.keys()),
                "partial": not experience or not education,
                "parsed": True,
                "parser": "regex"
            }
        })
