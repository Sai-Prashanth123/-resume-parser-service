
import re
from app.parsing.skills import extract_from_text

ROLE = re.compile(r"(engineer|developer|manager|analyst|intern|consultant)", re.I)

def parse_experience(text):
    blocks = text.split("\n\n")
    out = []
    for b in blocks:
        if ROLE.search(b):
            out.append({
                "description": b.strip(),
                "skills": extract_from_text(b)
            })
    return out
