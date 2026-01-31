
from app.parsing.text_extract import extract_text
from app.parsing.sectioner import split_sections
from app.parsing.personal import extract_personal
from app.parsing.experience import parse_experience
from app.parsing.education import parse_education
from app.parsing.skills import consolidate_skills

def parse_resume(payload: dict) -> dict:
    raw_text = extract_text(payload)
    sections = split_sections(raw_text)

    personal = extract_personal(raw_text)
    experience = parse_experience(sections.get("experience",""))
    education = parse_education(sections.get("education",""))
    skills = consolidate_skills(sections, experience, education)

    return {
        "personal": personal,
        "experience": experience,
        "education": education,
        "skills": skills,
        "meta": {
            "sectionsFound": list(sections.keys()),
            "partial": not experience or not education
        }
    }
