
import re

def extract_from_text(text):
    tokens = re.split(r"[,.]", text)
    return list({t.strip() for t in tokens if len(t.strip()) > 2})

def consolidate_skills(sections, exp, edu):
    skills = []
    for e in exp:
        skills.extend(e.get("skills", []))
    if "skills" in sections:
        skills.extend(extract_from_text(sections["skills"]))
    return list(set(skills))
