
import re

def parse_experience(text):
    """
    Flexible work experience parser that works with various resume formats.
    Extracts: job title, employer, dates, description.
    Leaves fields empty if not found.
    """
    if not text or not text.strip():
        return []
    
    # Job title keywords to identify work experience blocks
    ROLE_KEYWORDS = ['developer', 'engineer', 'manager', 'analyst', 'intern', 'consultant', 
                     'designer', 'architect', 'lead', 'specialist', 'coordinator', 'director',
                     'associate', 'assistant', 'administrator', 'officer', 'executive']
    
    # Flexible date pattern
    DATE_PATTERN = r'((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\d{1,2}/\d{4}|\d{4})'
    
    blocks = text.split("\n\n")
    out = []
    
    for b in blocks:
        if not b.strip() or len(b.strip()) < 15:
            continue
        
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if not lines:
            continue
        
        # Check if this block contains a job title
        first_line_lower = lines[0].lower()
        has_role = any(role in first_line_lower for role in ROLE_KEYWORDS)
        
        if not has_role:
            continue
        
        # Extract job title - it's typically the first part before separators
        first_line_text = lines[0]
        
        # Find all dates in the first line
        dates_in_line = re.findall(DATE_PATTERN, first_line_text, re.I)
        
        # Remove dates to isolate job title and company
        line_without_dates = re.sub(DATE_PATTERN, '', first_line_text, flags=re.I).strip()
        line_without_dates = re.sub(r'\s*[-–—]\s*$', '', line_without_dates).strip()
        
        # Split by separators: " - ", " at ", " @ ", "|", ","
        # Try different separators in order of likelihood
        job_title = None
        employer = None
        
        # Try splitting by " - " first
        if ' - ' in line_without_dates or ' – ' in line_without_dates or ' — ' in line_without_dates:
            parts = re.split(r'\s+[-–—]\s+', line_without_dates, maxsplit=1)
            job_title = parts[0].strip()
            if len(parts) > 1:
                employer = parts[1].strip()
        # Try splitting by " at "
        elif ' at ' in line_without_dates.lower():
            parts = re.split(r'\s+at\s+', line_without_dates, maxsplit=1, flags=re.I)
            job_title = parts[0].strip()
            if len(parts) > 1:
                employer = parts[1].strip()
        # Try splitting by "|"
        elif '|' in line_without_dates:
            parts = line_without_dates.split('|', maxsplit=1)
            job_title = parts[0].strip()
            if len(parts) > 1:
                employer = parts[1].strip()
        else:
            # No clear separator, use the whole line as job title
            job_title = line_without_dates.strip()
        
        # Clean employer name - remove tech stack if it got included
        if employer:
            # Check if employer looks like a list of tech terms (contains multiple commas)
            if employer.count(',') >= 2:
                # Likely a tech stack list, take first non-tech word
                employer_parts = employer.split(',')
                tech_terms = ['FastAPI', 'Azure', 'OpenAI', 'Docker', 'CI/CD', 'Jenkins', 'Kubernetes',
                             'React', 'Angular', 'Vue', 'Node', 'Python', 'Java', 'JavaScript',
                             'MongoDB', 'PostgreSQL', 'MySQL', 'Redis', 'AWS', 'GCP', 'Spring',
                             'Django', 'Flask', 'Express', 'Git', 'GitHub', 'HTML', 'CSS', 'API',
                             'REST', 'DBMS', 'System Design', 'OOPs', 'Database design']
                
                clean_employer = None
                for part in employer_parts:
                    part = part.strip()
                    # Check if this part is purely a tech term
                    is_tech = any(tech.lower() == part.lower() for tech in tech_terms)
                    if not is_tech and len(part) > 1:
                        clean_employer = part
                        break
                
                if clean_employer:
                    employer = clean_employer
                else:
                    # All parts are tech terms, set employer to None
                    employer = None
            # else: employer is a single word or simple phrase, keep it as-is
        
        # Extract dates
        start_date = dates_in_line[0] if len(dates_in_line) >= 1 else None
        end_date = dates_in_line[1] if len(dates_in_line) >= 2 else None
        
        # Check for "Present" or "Current"
        is_current = bool(re.search(r'\b(present|current)\b', first_line_text, re.I))
        if is_current:
            end_date = None
        
        # Extract description from bullet points
        description_lines = []
        for line in lines[1:]:
            if line.startswith(('•', '-', '*', '◦', '▪', '→')):
                description_lines.append(line)
        
        description = '\n'.join(description_lines) if description_lines else None
        
        # Add work experience entry
        out.append({
            "jobTitle": job_title,
            "employer": employer,
            "startDate": start_date,
            "endDate": end_date,
            "isCurrent": is_current,
            "city": None,
            "description": description
        })
    
    return out
