
import os
import re


_LOCATION_LINE_RE = re.compile(r"^(?P<city>[A-Za-z][A-Za-z.' \-]{1,40}),\s*(?P<country>[A-Za-z]{2,20})$")
_LOCATION_SEGMENT_RE = re.compile(
    r"(?P<city>[A-Za-z][A-Za-z.' \-]{1,40})\s*,\s*(?P<region>[A-Za-z]{2,3}|[A-Za-z][A-Za-z.' \-]{1,30})(?:\s*,\s*(?P<country>[A-Za-z][A-Za-z.' \-]{1,30}))?$"
)

def extract_personal(text):
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

    first_name = None
    last_name = None
    max_header_lines = int(os.getenv("RESUME_PARSER_PERSONAL_HEADER_LINES", "8"))

    def _looks_like_contact_or_header(ln: str) -> bool:
        low = ln.lower()
        if "@" in ln:
            return True
        if "http://" in low or "https://" in low or "www." in low:
            return True
        if any(ch.isdigit() for ch in ln):
            return True
        if any(k in low for k in ["linkedin", "github", "portfolio", "curriculum vitae", "resume"]):
            return True
        if low.strip() in {"summary", "professional summary", "experience", "work experience", "education", "skills", "projects"}:
            return True
        return False

    for ln in lines[: max(25, max_header_lines * 3)]:
        ln = ln.strip()
        if not ln:
            continue
        seg = re.split(r"[|•·]", ln)[0].strip()
        if not seg or _looks_like_contact_or_header(seg):
            continue

        name_parts = seg.split()
        if not (1 <= len(name_parts) <= 4):
            continue
        valid_name = all(part.replace('-', '').replace("'", '').replace('.', '').isalpha() for part in name_parts)
        if not valid_name:
            continue

        first_name = name_parts[0]
        last_name = name_parts[-1] if len(name_parts) > 1 else None
        break
    
    email_match = re.search(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', text)
    email = email_match.group(0) if email_match else None
    
    phone_patterns = [
        r'\+\d{1,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}[\s.-]?\d{4}',
        r'\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}',
        r'\d{3}[\s.-]?\d{3}[\s.-]?\d{4}',
        r'\+\d{10,15}'
    ]
    
    phone_number = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            phone_number = phone_match.group(0).strip()
            break
    
    city = ""
    country = ""
    for ln in lines[:max_header_lines]:
        ln = ln.strip()
        if not ln:
            continue
        low = ln.lower()
        if any(w in low for w in ["university", "college", "institute", "school", "company", "services", "consulting"]):
            continue

        if len(ln) > 220 and "|" not in ln and "•" not in ln and "·" not in ln:
            continue
        segments = re.split(r"[|•·]", ln)
        segments = [s.strip() for s in segments if s and s.strip()]

        for seg in segments[:3]:
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

            city = c1
            # Only use region as country if it's not a 2-3 letter US state code
            # This prevents US states like "MO" from being mapped as countries
            if ctry:
                country = ctry
            elif region and len(region) > 3:
                # If region is longer than 3 chars, it's likely a country name
                country = region
            else:
                # Short region codes (2-3 chars) are likely US states, leave country empty
                country = ""
            break
        if city:
            break
    
    return {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phoneNumber": phone_number,
        "address": "",
        "city": city,
        "country": country
    }
