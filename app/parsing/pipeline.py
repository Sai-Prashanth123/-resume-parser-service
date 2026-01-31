
from app.parsing.text_extract import extract_text
from app.parsing.llm_parser import parse_with_llm
import os

def parse_resume(payload: dict) -> dict:
    # Extract text from S3 file
    raw_text = extract_text(payload)
    
    # Use LLM for parsing if GROQ_API_KEY is set, otherwise fallback to basic parser
    use_llm = os.getenv("GROQ_API_KEY") is not None
    
    if use_llm:
        try:
            # Use Groq LLM for intelligent parsing
            result = parse_with_llm(raw_text)
            return result
        except Exception as e:
            # If LLM fails, return error
            return {
                "error": f"LLM parsing failed: {str(e)}",
                "personal": {},
                "experience": [],
                "education": [],
                "skills": [],
                "meta": {
                    "parsed": False,
                    "error": str(e)
                }
            }
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

        return {
            "personal": personal,
            "experience": experience,
            "education": education,
            "skills": skills,
            "meta": {
                "sectionsFound": list(sections.keys()),
                "partial": not experience or not education,
                "parsed": True,
                "parser": "regex"
            }
        }
