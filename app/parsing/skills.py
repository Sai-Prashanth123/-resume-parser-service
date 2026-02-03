
import re

KNOWN_SKILLS = {
    'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 'Go', 'Rust', 'Swift', 'Kotlin', 'Scala', 'PHP', 'Perl',
    'React', 'Angular', 'Vue', 'Node.js', 'Express', 'Django', 'Flask', 'Spring', 'FastAPI', 'Next.js', 'Nuxt.js',
    'HTML', 'CSS', 'SASS', 'LESS', 'Tailwind', 'Bootstrap', 'Material-UI', 'Ant Design',
    'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Cassandra', 'DynamoDB', 'Oracle', 'SQLite',
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'Git', 'GitHub', 'GitLab', 'Bitbucket',
    'REST', 'GraphQL', 'gRPC', 'WebSocket', 'OAuth', 'JWT', 'SAML',
    'TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy', 'Matplotlib',
    'Agile', 'Scrum', 'Kanban', 'JIRA', 'Confluence', 'Slack', 'Trello',
    'Linux', 'Unix', 'Windows', 'macOS', 'Bash', 'PowerShell', 'Shell',
    'Terraform', 'Ansible', 'CloudFormation', 'CI/CD', 'DevOps', 'Microservices',
    'Machine Learning', 'Deep Learning', 'AI', 'NLP', 'Computer Vision', 'Data Science'
}

_SECTION_LIKE = {
    "technical proficiencies",
    "technical proficiency",
    "technical skills",
    "skills",
    "core competencies",
    "competencies",
    "expertise",
    "technologies",
    "tools",
    "tools & technologies",
    "key responsibilities",
    "key technologies",
}

_STOP_TOKENS = {
    "and", "or", "with", "from", "the", "a", "an", "to", "in", "of", "for",
}

def _clean_token(token: str) -> str:
    t = (token or "").strip()
    t = re.sub(r"^[•\-\*\u2022\u2023\u25E6\u25AA\u25CF]+\s*", "", t)
    t = t.strip(" \t\r\n,;|•-–—")
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

def _split_skill_candidates(text: str) -> list[str]:
    if not text:
        return []

    s = text.replace("\n", ",").replace("•", ",")
    raw = re.split(r"[,;]", s)
    out: list[str] = []
    for item in raw:
        item = _clean_token(item)
        if not item:
            continue

        if ":" in item and len(item) <= 80:
            left, right = item.split(":", 1)
            left = _clean_token(left)
            right = _clean_token(right)
            if left:
                out.append(left)
            if right:
                for p in re.split(r"[|/]", right):
                    p = _clean_token(p)
                    if p:
                        out.append(p)
            continue

        if "|" in item:
            for p in item.split("|"):
                p = _clean_token(p)
                if p:
                    out.append(p)
            continue

        out.append(item)

    return out

def extract_from_text(text):
    if not text:
        return []
    
    skills: list[str] = []

    candidates = _split_skill_candidates(text)
    for cand in candidates:
        cleaned = _clean_token(cand)
        if not cleaned:
            continue
        if len(cleaned) < 2 or len(cleaned) > 60:
            continue

        low = cleaned.lower()
        if low in _SECTION_LIKE:
            continue
        if low in _STOP_TOKENS:
            continue
        if not re.search(r"[A-Za-z]", cleaned):
            continue
        if re.fullmatch(r"\d+(\.\d+)?", cleaned):
            continue

        matched = None
        for known in KNOWN_SKILLS:
            if known.lower() == low:
                matched = known
                break
            if re.search(rf"\b{re.escape(known)}\b", cleaned, re.I):
                matched = known
                break
        if matched:
            skills.append(matched)
            continue

        if re.fullmatch(r"[A-Z&/]{2,8}", cleaned):
            skills.append(cleaned)
            continue
        if cleaned[0].isupper() and 3 <= len(cleaned) <= 45:
            if len(cleaned.split()) <= 6 and not cleaned.endswith("."):
                skills.append(cleaned)

    seen = set()
    uniq = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq

def consolidate_skills(sections, exp, edu):
    raw_skills: list[tuple[str, int | None]] = []
    
    if "skills" in sections:
        for s in extract_from_text(sections["skills"]):
            raw_skills.append((s, None))
    
    for section_name, section_text in sections.items():
        if any(keyword in section_name.lower() for keyword in ['skill', 'technical', 'technology', 'tools', 'expertise']):
            for s in extract_from_text(section_text):
                raw_skills.append((s, None))

    exp_section = sections.get("experience", "") or ""
    if exp_section:
        for line in exp_section.splitlines():
            low = line.lower().strip()
            if low.startswith("key technologies") or low.startswith("technologies used") or low.startswith("tech stack"):
                tech = line.split(":", 1)[1] if ":" in line else line
                for s in extract_from_text(tech):
                    raw_skills.append((s, None))

    for idx, e in enumerate(exp or []):
        if isinstance(e, dict):
            desc = e.get("description")
            if isinstance(desc, str) and desc.strip():
                for s in extract_from_text(desc):
                    raw_skills.append((s, idx))
    
    skill_objects = []
    seen = set()
    for skill, src_idx in raw_skills:
        if not skill:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        obj = {
            "skillName": skill,
            "experienceLevel": None,
            "hideExperienceLevel": True,
        }
        if src_idx is not None:
            obj["sourceExperienceIndex"] = src_idx
        skill_objects.append(obj)
    
    return skill_objects
