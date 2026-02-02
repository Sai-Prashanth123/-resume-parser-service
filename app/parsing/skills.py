
import re

# Common technical skills to recognize
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

    # Normalize separators to commas, but keep slashes and plus signs inside tokens
    s = text.replace("\n", ",").replace("•", ",")
    # Split on commas/semicolons; keep pipes as separators too
    raw = re.split(r"[,;]", s)
    out: list[str] = []
    for item in raw:
        item = _clean_token(item)
        if not item:
            continue

        # Break "ERP Systems: SAP HANA" into ["ERP Systems", "SAP HANA"]
        if ":" in item and len(item) <= 80:
            left, right = item.split(":", 1)
            left = _clean_token(left)
            right = _clean_token(right)
            if left:
                out.append(left)
            # Right side may still contain multiple items
            if right:
                for p in re.split(r"[|/]", right):
                    p = _clean_token(p)
                    if p:
                        out.append(p)
            continue

        # Break pipe-separated/grouped tokens
        if "|" in item:
            for p in item.split("|"):
                p = _clean_token(p)
                if p:
                    out.append(p)
            continue

        out.append(item)

    return out

def extract_from_text(text):
    """Extract skills from text by looking for known technical terms."""
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
        # Skip tokens that are mostly punctuation/numbers
        if not re.search(r"[A-Za-z]", cleaned):
            continue
        if re.fullmatch(r"\d+(\.\d+)?", cleaned):
            continue

        # Known skill match (prefer exact/word-boundary)
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

        # Heuristic acceptance for unknown skills:
        # - allow short all-caps acronyms (ERP, WMS, S&OP)
        # - allow Title Case / MixedCase phrases without being too long
        if re.fullmatch(r"[A-Z&/]{2,8}", cleaned):
            skills.append(cleaned)
            continue
        if cleaned[0].isupper() and 3 <= len(cleaned) <= 45:
            # reject obvious sentence fragments
            if len(cleaned.split()) <= 6 and not cleaned.endswith("."):
                skills.append(cleaned)

    # De-dupe case-insensitively, preserve order
    seen = set()
    uniq = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq

def consolidate_skills(sections, exp, edu):
    """Consolidate skills from all sections of the resume."""
    skills = []
    
    # Extract from dedicated skills section
    if "skills" in sections:
        skills.extend(extract_from_text(sections["skills"]))
    
    # Also check for "technical skills" or similar sections
    for section_name, section_text in sections.items():
        if any(keyword in section_name.lower() for keyword in ['skill', 'technical', 'technology', 'tools', 'expertise']):
            skills.extend(extract_from_text(section_text))

    # Extract skills mentioned inside experience blocks (common pattern: "Key Technologies: ...")
    exp_section = sections.get("experience", "") or ""
    if exp_section:
        # Key technologies lines
        for line in exp_section.splitlines():
            low = line.lower().strip()
            if low.startswith("key technologies") or low.startswith("technologies used") or low.startswith("tech stack"):
                # Take everything after ":" if present
                tech = line.split(":", 1)[1] if ":" in line else line
                skills.extend(extract_from_text(tech))

    # Also mine skills from parsed experience descriptions (bullet-heavy resumes)
    for e in exp or []:
        if isinstance(e, dict):
            desc = e.get("description")
            if isinstance(desc, str) and desc.strip():
                skills.extend(extract_from_text(desc))
    
    # Convert to skill objects with skillName
    skill_objects = []
    seen = set()
    for skill in skills:
        if skill and skill not in seen:
            seen.add(skill)
            skill_objects.append({
                "skillName": skill,
                "experienceLevel": None,
                "hideExperienceLevel": True
            })
    
    return skill_objects
