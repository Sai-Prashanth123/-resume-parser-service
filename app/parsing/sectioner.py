
HEADERS = ["experience", "education", "skills", "projects", "summary", "objective", "profile", "about"]

# Map alternative section names to standard names
SECTION_MAPPING = {
    "work experience": "experience",
    "employment history": "experience",
    "professional experience": "experience",
    "work history": "experience",
    "academic background": "education",
    "educational background": "education",
    "qualifications": "education",
    "technical skills": "skills",
    "core competencies": "skills",
    "expertise": "skills",
    "technologies": "skills",
    "professional summary": "summary",
    "career summary": "summary",
    "career objective": "objective",
    "professional profile": "summary",
    "about me": "summary"
}

def split_sections(text):
    sections = {}
    current = None
    
    for line in text.splitlines():
        low = line.lower().strip(": -•")
        
        # Check if line is a section header
        is_header = False
        
        # Direct match
        if low in HEADERS:
            current = low
            sections[current] = ""
            is_header = True
        # Check mapping
        elif low in SECTION_MAPPING:
            current = SECTION_MAPPING[low]
            if current not in sections:
                sections[current] = ""
            is_header = True
        # Partial match for common variations
        else:
            for alt_name, standard_name in SECTION_MAPPING.items():
                if alt_name in low and len(low) < len(alt_name) + 10:
                    current = standard_name
                    if current not in sections:
                        sections[current] = ""
                    is_header = True
                    break
        
        # Add content to current section
        if not is_header and current:
            sections[current] += line + "\n"
    
    return sections
