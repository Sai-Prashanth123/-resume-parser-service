
import re
from typing import Optional

from dateutil import parser as date_parser

def parse_education(text):
    """
    Education parser that handles common resume formats and fixes swapped date ranges.
    """
    if not text or not text.strip():
        return []
    
    # Keywords to identify education sections
    UNIVERSITY_KEYWORDS = ['university', 'college', 'institute', 'school', 'academy', 'polytechnic']
    DEGREE_KEYWORDS = ['bachelor', 'master', 'phd', 'doctorate', 'b.s', 'm.s', 'b.a', 'm.a', 
                       'b.tech', 'm.tech', 'b.e', 'm.e', 'associate', 'diploma', 'certificate']
    
    # Flexible date token pattern - matches various formats
    MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    DATE_TOKEN = rf"(?:{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
    RANGE_RE = re.compile(
        rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to)\s*(?P<end>{DATE_TOKEN}|present|current|now)",
        re.IGNORECASE,
    )

    def _extract_date_range(block: str) -> tuple[Optional[str], Optional[str]]:
        if not block:
            return None, None
        m = RANGE_RE.search(block)
        if m:
            start = m.group("start")
            end_raw = m.group("end")
            if re.fullmatch(r"(present|current|now)", end_raw.strip(), re.I):
                return start, None
            return start, end_raw
        # fallback: first two tokens in order of appearance
        tokens = re.findall(DATE_TOKEN, block, flags=re.I)
        start = tokens[0] if len(tokens) >= 1 else None
        end = tokens[1] if len(tokens) >= 2 else None
        if re.search(r"\b(present|current|now)\b", block, re.I):
            end = None
        return start, end

    def _maybe_swap_dates(start: Optional[str], end: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not start or not end:
            return start, end
        try:
            sdt = date_parser.parse(start, default=date_parser.parse("2000-01-01"))
            edt = date_parser.parse(end, default=date_parser.parse("2000-01-01"))
            if sdt > edt:
                return end, start
        except Exception:
            pass
        return start, end
    
    def _is_school_line(line: str) -> bool:
        if not line:
            return False
        low = line.lower()
        if any(k in low for k in UNIVERSITY_KEYWORDS):
            return True
        # Common explicit forms without keywords list
        if re.search(r"\b(university|college|institute|school|academy)\b", low):
            return True
        return False

    def _is_location_line(line: str) -> bool:
        if not line:
            return False
        s = line.strip()
        # "Washington, DC" / "Guntur, India"
        if re.fullmatch(r"[A-Za-z.\s']+,\s*[A-Za-z.\s]{2,}", s):
            return True
        # "O'Fallon, MO" style
        if re.fullmatch(r"[A-Za-z.\s']+,\s*[A-Z]{2}\b", s):
            return True
        return False

    out: list[dict] = []
    current: dict | None = None
    desc_lines: list[str] = []
    pending_degree_line: str | None = None

    def _flush():
        nonlocal current, desc_lines, pending_degree_line
        if not current:
            return
        if desc_lines:
            current["description"] = "\n".join(desc_lines).strip() or None
        desc_lines = []
        pending_degree_line = None
        # Only keep meaningful entries
        if current.get("schoolName") and (current.get("degree") or current.get("startDate") or current.get("endDate") or current.get("description")):
            out.append(current)
        current = None

    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]

    for ln in lines:
        # If we previously saw a degree line but not a school yet, allow the next school line
        # to start an entry (helps formats like "B.S. Computer Science" then "Some University").
        # Start a new entry on a school line
        if _is_school_line(ln):
            _flush()
            school_name = ln.split(",")[0].strip()
            current = {
                "schoolName": school_name,
                "degree": None,
                "startDate": None,
                "endDate": None,
                "city": None,
                "description": None,
            }
            if pending_degree_line and not current.get("degree"):
                degree = RANGE_RE.sub("", pending_degree_line)
                degree = re.sub(DATE_TOKEN, "", degree, flags=re.I).strip(" -–—,|")
                current["degree"] = degree or None
            continue

        if not current:
            # Cache a degree line so we can attach it if the next line is the school.
            if any(keyword in ln.lower() for keyword in DEGREE_KEYWORDS) or re.search(
                r"\b(MBA|B\.?TECH|M\.?TECH|B\.?E|M\.?E|B\.?S|M\.?S|B\.?A|M\.?A)\b", ln, re.I
            ):
                pending_degree_line = ln
            # Ignore until we hit a school line
            continue

        if _is_location_line(ln) and not current.get("city"):
            current["city"] = ln
            continue

        # Degree line
        if (not current.get("degree")) and (
            any(keyword in ln.lower() for keyword in DEGREE_KEYWORDS) or re.search(r"\b(MBA|B\.?TECH|M\.?TECH|B\.?E|M\.?E|B\.?S|M\.?S|B\.?A|M\.?A)\b", ln, re.I)
        ):
            degree = RANGE_RE.sub("", ln)
            degree = re.sub(DATE_TOKEN, "", degree, flags=re.I).strip(" -–—,|")
            current["degree"] = degree or None
            continue

        # Dates
        if re.search(DATE_TOKEN, ln, re.I) or re.search(r"\b(present|current|now)\b", ln, re.I):
            low_ln = ln.lower()
            start_date, end_date = _extract_date_range(ln)

            # Handle "Expected Graduation: 2027" style lines (end date only)
            if "expected" in low_ln and "gradu" in low_ln and start_date and not end_date:
                current["endDate"] = current.get("endDate") or start_date
                continue

            # If line indicates present/current, treat extracted start_date as startDate
            if re.search(r"\b(present|current|now)\b", low_ln):
                if start_date:
                    current["startDate"] = current.get("startDate") or start_date
                # Education "present" means ongoing; keep endDate empty
                current["endDate"] = None
                continue

            # If we have a true range, set both
            if start_date and end_date:
                start_date, end_date = _maybe_swap_dates(start_date, end_date)
                current["startDate"] = current.get("startDate") or start_date
                current["endDate"] = current.get("endDate") or end_date
                continue

            # Single date token (no range, no present): usually graduation date => endDate.
            if start_date and not end_date:
                if not current.get("endDate"):
                    current["endDate"] = start_date
                elif not current.get("startDate"):
                    # If endDate already exists and startDate missing, treat this as startDate.
                    current["startDate"] = start_date
                continue

        # Description bullets
        if ln.startswith(("•", "-", "*", "◦")):
            desc_lines.append(ln)
            continue

        # Relevant/honors lines
        if any(kw in ln.lower() for kw in ["gpa", "cgpa", "coursework", "honors", "activities", "relevant", "scholarship", "fellow"]):
            desc_lines.append(ln)
            continue

    _flush()
    return out
