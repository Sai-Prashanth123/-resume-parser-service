
import re

def parse_education(text):
    """
    Flexible education parser that works with various resume formats.
    Extracts: school name, degree, dates, description.
    Leaves fields empty if not found.
    """
    if not text or not text.strip():
        return []
    
    # Keywords to identify education sections
    UNIVERSITY_KEYWORDS = ['university', 'college', 'institute', 'school', 'academy', 'polytechnic']
    DEGREE_KEYWORDS = ['bachelor', 'master', 'phd', 'doctorate', 'b.s', 'm.s', 'b.a', 'm.a', 
                       'b.tech', 'm.tech', 'b.e', 'm.e', 'associate', 'diploma', 'certificate']
    
    # Flexible date pattern - matches various formats
    DATE_PATTERN = r'((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\d{1,2}/\d{4}|\d{4})'
    
    blocks = text.split("\n\n")
    out = []
    
    for b in blocks:
        if not b.strip() or len(b.strip()) < 10:
            continue
        
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if not lines:
            continue
        
        # Check if this block contains education-related keywords
        block_lower = b.lower()
        has_university = any(keyword in block_lower for keyword in UNIVERSITY_KEYWORDS)
        has_degree = any(keyword in block_lower for keyword in DEGREE_KEYWORDS)
        
        if not (has_university or has_degree):
            continue
        
        # Extract school name from first line, removing location if present
        school_name_raw = lines[0].strip()
        # Remove location pattern: "Name, City, Country" -> "Name"
        school_name = school_name_raw.split(',')[0].strip()
        
        # Extract degree - find line with degree keywords
        degree = None
        for line in lines:
            if any(keyword in line.lower() for keyword in DEGREE_KEYWORDS):
                # Clean the degree line
                degree = line.strip()
                # Remove dates from degree line
                degree = re.sub(DATE_PATTERN, '', degree, flags=re.I).strip()
                # Remove trailing separators
                degree = re.sub(r'[-–—,]\s*$', '', degree).strip()
                break
        
        # Extract dates - find all dates in the block
        dates = re.findall(DATE_PATTERN, b, re.I)
        start_date = dates[0] if len(dates) >= 1 else None
        end_date = dates[1] if len(dates) >= 2 else None
        
        # Check for "Present" or "Current"
        if re.search(r'\b(present|current)\b', b, re.I):
            end_date = None
        
        # Extract description (GPA, coursework, honors)
        description_lines = []
        for line in lines[1:]:
            # Skip school name and degree lines
            if line == school_name_raw or (degree and degree in line):
                continue
            # Include GPA, coursework, honors, activities
            if any(kw in line.lower() for kw in ['gpa', 'cgpa', 'coursework', 'honors', 'activities', 'relevant']):
                description_lines.append(line)
            # Include bullet points (but not tech skills)
            elif line.startswith(('•', '-', '*', '◦')):
                # Skip if it's clearly a tech skill list
                if not any(tech in line for tech in ['Python', 'Java', 'React', 'Node', 'Angular', 'Docker']):
                    description_lines.append(line)
        
        description = '\n'.join(description_lines) if description_lines else None
        
        # Add education entry
        out.append({
            "schoolName": school_name,
            "degree": degree,
            "startDate": start_date,
            "endDate": end_date,
            "city": None,
            "description": description
        })
    
    return out
