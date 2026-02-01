
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

def extract_from_text(text):
    """Extract skills from text by looking for known technical terms."""
    if not text:
        return []
    
    skills = []
    
    # Split by common delimiters
    tokens = re.split(r'[,;•\-\n]', text)
    
    for token in tokens:
        cleaned = token.strip()
        # Skip very short or very long tokens
        if len(cleaned) < 2 or len(cleaned) > 50:
            continue
        
        # Check if it matches a known skill (case-insensitive)
        for known_skill in KNOWN_SKILLS:
            if known_skill.lower() == cleaned.lower() or known_skill.lower() in cleaned.lower():
                skills.append(known_skill)
                break
        else:
            # If not a known skill, only add if it looks like a technical term
            # (capitalized, no common words, reasonable length)
            if cleaned[0].isupper() and len(cleaned) >= 3 and len(cleaned) <= 30:
                # Exclude common non-skill words
                excluded_words = {'The', 'And', 'For', 'With', 'From', 'This', 'That', 'Have', 'Been', 'Were', 'Was', 'Are', 'Is'}
                if cleaned not in excluded_words:
                    skills.append(cleaned)
    
    return list(set(skills))

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
