
import re

HEADERS = [
    "experience",
    "education",
    "skills",
    "projects",
    "summary",
    "objective",
    "profile",
    "about",
    "certifications",
    "awards",
    "publications",
    "volunteering",
    "volunteer",
    "languages",
    "interests",
]

SECTION_MAPPING = {
    "work experience": "experience",
    "work & experience": "experience",
    "employment": "experience",
    "employment history": "experience",
    "professional experience": "experience",
    "work history": "experience",
    "career history": "experience",
    "professional history": "experience",
    "leadership experience": "experience",
    "board experience": "experience",
    "professional activities": "experience",
    "internships": "experience",
    "internship experience": "experience",
    "experience": "experience",
    "academic background": "education",
    "educational background": "education",
    "qualifications": "education",
    "education": "education",
    "technical skills": "skills",
    "core competencies": "skills",
    "expertise": "skills",
    "technologies": "skills",
    "technical proficiencies": "skills",
    "tools & technologies": "skills",
    "tools and technologies": "skills",
    "skills": "skills",
    "professional summary": "summary",
    "career summary": "summary",
    "career objective": "objective",
    "professional profile": "summary",
    "about me": "summary",
    "certifications": "certifications",
    "licenses": "certifications",
    "certificates": "certifications",
    "awards": "awards",
    "honors": "awards",
    "publications": "publications",
    "volunteer experience": "volunteering",
    "volunteering": "volunteering",
    "languages": "languages",
    "interests": "interests",
    "activities": "interests",
    "project works": "projects",
    "project work": "projects",
    "projects": "projects",
    "projects & work": "projects",
    "project experience": "projects",
    "certifications & achievements": "certifications",
    "certifications and achievements": "certifications",
}

def split_sections(text):
    sections: dict[str, str] = {}
    current: str | None = None

    def _normalize_header_candidate(line: str) -> str:
        s = (line or "").strip()
        s = re.sub(r"^[\s•\-\*\u2022\u2023\u25E6\u25AA\u25CF]+", "", s)
        s = re.sub(r"[\s:–—\-•\|]+$", "", s)
        s = re.sub(r"^\s*(\d+[\.\)]\s*|\d+\s*[-–—]\s*)", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip().lower()
        return s

    def _looks_like_header(original: str, normalized: str) -> str | None:
        if not normalized:
            return None

        inline_labels = {
            "key responsibilities",
            "responsibilities",
            "key technologies",
            "technologies used",
            "tools used",
            "tech stack",
            "stack",
            "highlights",
            "achievements",
            "key achievements",
        }
        if normalized in inline_labels or normalized.startswith("key "):
            return None

        if normalized in {"in", "at", "and", "the", "with", "for"}:
            return None

        if normalized in HEADERS:
            return normalized
        if normalized in SECTION_MAPPING:
            return SECTION_MAPPING[normalized]

        orig = (original or "").strip()
        is_short = len(orig) <= 50
        cleaned_for_alpha = orig.replace("-", " ").replace("—", " ").replace("–", " ").strip()
        mostly_alpha = bool(re.fullmatch(r"[A-Za-z0-9\s/&]+", cleaned_for_alpha))
        if is_short and mostly_alpha:
            for alt_name, standard_name in SECTION_MAPPING.items():
                if alt_name in normalized and len(normalized) <= len(alt_name) + 10:
                    return standard_name
            for h in HEADERS:
                if h in normalized and len(normalized) <= len(h) + 10:
                    return h

        if orig.endswith(":"):
            for alt_name, standard_name in SECTION_MAPPING.items():
                if alt_name in normalized:
                    return standard_name
            for h in HEADERS:
                if h in normalized:
                    return h

        return None

    for line in (text or "").splitlines():
        normalized = _normalize_header_candidate(line)
        mapped = _looks_like_header(line, normalized)
        if mapped:
            current = mapped
            sections.setdefault(current, "")
            continue

        if not current:
            current = "headerless"
            sections.setdefault(current, "")
        sections[current] += line + "\n"

    return {k: v for k, v in sections.items() if v and v.strip()}
