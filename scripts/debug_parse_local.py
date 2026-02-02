import os
import sys
import json
import hashlib

import fitz

# Ensure imports work when run as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.parsing.education import parse_education
from app.parsing.experience import parse_experience
from app.parsing.personal import extract_personal
from app.parsing.sectioner import split_sections
from app.parsing.skills import consolidate_skills
from app.parsing.social_links import extract_social_links
from app.parsing.normalize import normalize_text


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else r"d:\Cluco\-resume-parser-service\Jayaprakash_Resume (1).pdf"
    with open(path, "rb") as f:
        data = f.read()
    doc_hash = hashlib.sha256(data).hexdigest()
    doc = fitz.open(path)
    raw = "\n\n".join(pg.get_text("text") for pg in doc)
    raw = normalize_text(raw)

    sections = split_sections(raw)
    exp = parse_experience(sections.get("experience", ""))
    edu = parse_education(sections.get("education", ""))
    skills = consolidate_skills(sections, exp, edu)

    out = {
        "file": path,
        "sha256": doc_hash,
        "sectionsFound": list(sections.keys()),
        "experienceTextSample": sections.get("experience", "")[:1800],
        "experienceNonAsciiChars": sorted(
            {f"U+{ord(ch):04X} {repr(ch)}" for ch in sections.get("experience", "") if ord(ch) > 127}
        )[:30],
        "educationTextSample": sections.get("education", "")[:1800],
        "personal": extract_personal(raw),
        "socialLinks": extract_social_links(raw),
        "experienceCount": len(exp),
        "educationCount": len(edu),
        "skillsCount": len(skills),
        "experienceHeads": [
            {
                "jobTitle": e.get("jobTitle"),
                "employer": e.get("employer"),
                "city": e.get("city"),
                "startDate": e.get("startDate"),
                "endDate": e.get("endDate"),
                "isCurrent": e.get("isCurrent"),
            }
            for e in exp[:8]
        ],
        "experienceSnippetFounder": (sections.get("experience", "").split("SREE")[1][:900] if "SREE" in sections.get("experience", "") else None),
        "experienceSnippetVirtusa": (sections.get("experience", "").split("VIRTUSA")[1][:900] if "VIRTUSA" in sections.get("experience", "") else None),
        "experienceSnippetFreshFood": (sections.get("experience", "").split("FRESH FOOD FACTORY")[1][:900] if "FRESH FOOD FACTORY" in sections.get("experience", "") else None),
        "education": edu,
        "firstSkills": [s.get("skillName") for s in skills[:25]],
    }
    # Windows console can choke on some unicode bullet glyphs; always write UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

