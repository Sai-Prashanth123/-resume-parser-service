
import os
import re


_LOCATION_LINE_RE = re.compile(r"^(?P<city>[A-Za-z][A-Za-z.' \-]{1,40}),\s*(?P<country>[A-Za-z]{2,20})$")
_LOCATION_SEGMENT_RE = re.compile(
    r"(?P<city>[A-Za-z][A-Za-z.' \-]{1,40})\s*,\s*(?P<region>[A-Za-z]{2,3}|[A-Za-z][A-Za-z.' \-]{1,30})(?:\s*,\s*(?P<country>[A-Za-z][A-Za-z.' \-]{1,30}))?$"
)

def extract_personal(text):
    """
    Flexible personal details parser.
    Extracts name, email, phone from resume.
    Tries city/country only from top header lines (safe heuristics).
    """
    if not text:
        return {
            "firstName": None,
            "lastName": None,
            "email": None,
            "phoneNumber": None,
            "address": "",
            "city": "",
            "country": ""
        }
    
    lines = [l for l in text.splitlines() if l.strip()]
    
    # Extract name from first line
    first_name = None
    last_name = None
    if lines:
        name_parts = lines[0].strip().split()
        # Only extract if it looks like a name (alphabetic characters, 1-4 words)
        if 1 <= len(name_parts) <= 4:
            valid_name = all(part.replace('-', '').replace("'", '').replace('.', '').isalpha() for part in name_parts)
            if valid_name:
                first_name = name_parts[0]
                last_name = name_parts[-1] if len(name_parts) > 1 else None
    
    # Extract email - standard email pattern
    email_match = re.search(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', text)
    email = email_match.group(0) if email_match else None
    
    # Extract phone number - flexible pattern for international formats
    phone_patterns = [
        r'\+\d{1,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}[\s.-]?\d{4}',  # +91 1234567890
        r'\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}',  # (123) 456-7890
        r'\d{3}[\s.-]?\d{3}[\s.-]?\d{4}',  # 123-456-7890
        r'\+\d{10,15}'  # +911234567890
    ]
    
    phone_number = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            phone_number = phone_match.group(0).strip()
            break
    
    # Location extraction (safe): only from the first few lines near contact info.
    # This avoids picking up cities/countries from experience section.
    city = ""
    country = ""
    max_header_lines = int(os.getenv("RESUME_PARSER_PERSONAL_HEADER_LINES", "8"))
    for ln in lines[:max_header_lines]:
        ln = ln.strip()
        if not ln:
            continue
        low = ln.lower()
        if any(w in low for w in ["university", "college", "institute", "school", "company", "services", "consulting"]):
            continue

        # Many resumes put location + email + phone + links on one line separated by pipes.
        # Example: "O'Fallon, MO | email | (202) ... | linkedin.com/..."
        # Allow long contact lines, but avoid scanning huge paragraphs.
        if len(ln) > 220 and "|" not in ln and "•" not in ln and "·" not in ln:
            continue
        segments = re.split(r"[|•·]", ln)
        segments = [s.strip() for s in segments if s and s.strip()]

        # Prefer early segments (location is usually first)
        for seg in segments[:3]:
            # Skip segments that are clearly not location
            if "@" in seg or "http" in seg.lower():
                continue
            if any(ch.isdigit() for ch in seg):
                continue

            m = _LOCATION_SEGMENT_RE.fullmatch(seg)
            if not m:
                continue
            c1 = m.group("city").strip()
            region = (m.group("region") or "").strip()
            ctry = (m.group("country") or "").strip()

            # We only return city + country. If country is present, use it.
            # Otherwise, use the region/state as "country" (UI uses this field for location).
            city = c1
            country = ctry if ctry else region
            break
        if city:
            break
    
    return {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phoneNumber": phone_number,
        # Important for data consistency:
        # return empty strings for unknowns so downstream merges don't keep stale values.
        "address": "",
        "city": city,
        "country": country
    }
