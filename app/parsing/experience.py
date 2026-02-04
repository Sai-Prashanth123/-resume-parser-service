
import re
from dataclasses import dataclass
from typing import Optional

from dateutil import parser as date_parser

EXPERIENCE_SECTION_HEADINGS = frozenset({
    "work experience", "experience", "professional experience", "work history",
    "employment history", "career history", "professional history", "work & experience",
})

def parse_experience(text):
    if not text or not text.strip():
        return []

    ROLE_KEYWORDS = {
        "developer", "engineer", "manager", "analyst", "intern", "consultant", "designer",
        "architect", "lead", "specialist", "coordinator", "director", "associate",
        "assistant", "administrator", "officer", "executive", "supervisor", "owner",
        "president", "vice", "vp", "product", "project", "program",
        "founder", "ceo", "coo", "cto", "cfo", "co-founder", "cofounder",
        "summer", "freelance", "self-employed", "volunteer",
    }

    WORK_MODE_TOKENS = {
        "remote",
        "hybrid",
        "onsite",
        "on-site",
        "on site",
        "work from home",
        "wfh",
    }

    MONTH = (
        r"(?:"
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|"
        r"Janvier|F[ée]vrier|Mars|Avril|Mai|Juin|Juillet|Ao[uû]t|Septembre|Octobre|Novembre|D[ée]cembre|"
        r"Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre"
        r")"
    )
    SEASON = r"(?:Spring|Summer|Fall|Autumn|Winter)"
    QUARTER = r"(?:Q[1-4])"
    YEAR = r"\d{4}"
    DATE_TOKEN = rf"(?:{MONTH}\s+{YEAR}|{SEASON}\s+{YEAR}|{QUARTER}\s+{YEAR}|\d{{1,2}}/\d{{4}}|\d{{2}}\.\d{{4}}|{YEAR})"
    RANGE_RE = re.compile(
        rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to|\uFFFD)\s*(?P<end>{DATE_TOKEN}|present|current|now)",
        re.IGNORECASE,
    )

    def _is_bullet_line(line: str) -> bool:
        s = (line or "").lstrip()
        return bool(s) and s[0] in {"•", "-", "*", "◦", "▪", "→"}

    def _looks_like_garbage(line: str) -> bool:
        if not line:
            return False
        s = line.strip()
        if not s:
            return False
        letters_or_digits = sum(1 for ch in s if ch.isalnum())
        if letters_or_digits == 0:
            return True
        weird = sum(1 for ch in s if ord(ch) > 127 and not ch.isspace() and not ch.isalnum())
        return weird > 0 and weird / max(len(s), 1) > 0.4

    def _looks_like_role(text_line: str) -> bool:
        low = (text_line or "").lower()
        # Use word boundary matching to avoid false positives like 'FACTORY' matching 'cto'
        for kw in ROLE_KEYWORDS:
            # Match keyword as a whole word (with word boundaries)
            if re.search(rf'\b{re.escape(kw)}\b', low):
                return True
        return False

    def _extract_date_range(line: str) -> tuple[Optional[str], Optional[str], bool]:
        if not line:
            return None, None, False
        m = RANGE_RE.search(line)
        if not m:
            if re.search(r"\b(present|current|now)\b", line, re.I):
                m2 = re.search(DATE_TOKEN, line, re.I)
                if m2:
                    return m2.group(0), None, True
            m_open = re.search(rf"({DATE_TOKEN})\s*(?:-|–|—)\s*$", line, re.I)
            if m_open:
                return m_open.group(1), None, False
            return None, None, False
        start = m.group("start")
        end_raw = m.group("end")
        is_current = bool(re.fullmatch(r"(present|current|now)", end_raw.strip(), re.I))
        end = None if is_current else end_raw
        return start, end, is_current

    def _clean_header_line(line: str) -> str:
        s = (line or "").strip()
        s = re.sub(r"^[\s•\-\*|]+", "", s)
        s = re.sub(r"^,\s*", "", s)
        s = re.sub(r"[\s|]+$", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    def _strip_date_range_from_line(line: str) -> str:
        if not line:
            return ""
        s = RANGE_RE.sub("", line)
        s = re.sub(DATE_TOKEN, "", s, flags=re.I)
        s = re.sub(r"[\s\-–—,]{2,}", " ", s).strip(" -–—,")
        return s.strip()

    def _split_by_separators(s: str) -> list[str]:
        if not s:
            return []
        parts = re.split(r"\s*(?:\||@|\s+at\s+|\s+[-–—]\s+)\s*", s, flags=re.I)
        parts = [p.strip() for p in parts if p and p.strip()]
        return parts

    def _split_two_column_line(raw_line: str) -> list[str]:
        s = (raw_line or "").rstrip()
        if not s:
            return []
        if "\t" not in s and not re.search(r"\s{3,}", s):
            return [s]
        parts = [p.strip() for p in re.split(r"(?:\t+|\s{3,})", s) if p and p.strip()]
        if len(parts) < 2:
            return [s]
        left = " ".join(parts[:-1]).strip()
        right = parts[-1].strip()
        if not left or not right:
            return [s]

        st, ed, cur = _extract_date_range(right)
        if st or cur:
            return [left, right]
        if re.fullmatch(r"\d{4}", right) or re.fullmatch(r"Q[1-4]\s+\d{4}", right, flags=re.I):
            return [left, right]
        if re.fullmatch(r"\d{4}", left) or re.fullmatch(r"Q[1-4]\s+\d{4}", left, flags=re.I):
            return [left, right]
        if _looks_like_location(right) or any(tok in right.lower() for tok in WORK_MODE_TOKENS):
            return [left, right]
        return [s]

    def _extract_inline_location_tail(s: str) -> tuple[str, Optional[str]]:
        if not s:
            return "", None
        t = _clean_header_line(s)
        if "," not in t:
            return t, None
        last_comma = t.rfind(",")
        left = t[:last_comma].strip(" -–—|")
        right = t[last_comma + 1 :].strip()
        if not right:
            return t, None
        if right.lower() in WORK_MODE_TOKENS:
            return left if left else t, right.title()
        if _looks_like_location(right):
            return left if left else t, right
        return t, None

    def _looks_like_entry_header(line: str) -> bool:
        if not line:
            return False
        s = line.strip()
        if len(s) < 3 or len(s) > 140:
            return False
        st, ed, cur = _extract_date_range(s)
        if st or cur:
            return True
        if s.isupper() and 3 <= len(s) <= 80 and "," not in s and not s.endswith("."):
            return True
        if re.search(r"\s+[-–—]\s+", s) and not s.endswith("."):
            return True
        if "|" in s and not s.endswith("."):
            return True
        if _looks_like_location(s) and not s.endswith("."):
            return True
        if _looks_like_role(s) and len(s) <= 80 and not s.endswith("."):
            return True
        return False

    def _looks_like_location(s: str) -> bool:
        if not s:
            return False
        t = s.strip()
        if len(t) < 3 or len(t) > 80:
            return False
        if t.lower() in WORK_MODE_TOKENS:
            return True

        def _looks_like_location_simple(x: str) -> bool:
            x = (x or "").strip()
            if not x:
                return False
            if x.lower() in WORK_MODE_TOKENS:
                return True

            if "," in x:
                left, right = x.rsplit(",", 1)
                left = left.strip()
                right = right.strip()
                if not left or not right:
                    return False
                right_tokens = right.split()
                if 0 < len(right_tokens) <= 3 and right[0].isupper() and re.fullmatch(
                    r"[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*)*", right
                ):
                    return True
                return False

            if re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*)*\s+[A-Z]{2,3}", x):
                return True
            return False

        if "&" in t:
            parts = [p.strip() for p in t.split("&") if p and p.strip()]
            if len(parts) >= 2:
                left_ok = _looks_like_location_simple(parts[0])
                right_ok = _looks_like_location_simple(parts[1]) or re.fullmatch(r"[A-Za-z][A-Za-z.' \-]{2,40}", parts[1]) is not None
                return bool(left_ok and right_ok)
        return _looks_like_location_simple(t)

    def _sanitize_city_value(city: Optional[str]) -> Optional[str]:
        if not city:
            return None
        t = (city or "").strip()
        if not t:
            return None
        # Filter out obviously invalid short tokens that often come from NER noise.
        bad_tokens = {"ai", "ml", "dl", "city"}
        if t.lower() in bad_tokens:
            return None
        if len(t) > 80:
            return None
        if not any(ch.isalpha() for ch in t):
            return None
        words = re.split(r"[\s,]+", t)
        if len(words) > 8:
            return None
        if t.lower() in WORK_MODE_TOKENS:
            return t
        if _looks_like_location(t):
            return t
        return None

    def _extract_employer_from_company_line(line: str) -> Optional[str]:
        if not line:
            return None
        s = _clean_header_line(line)
        if not s:
            return None
        if _looks_like_role(s) or "|" in s.lower():
            return None
        
        # Handle format: "COMPANY NAME - Description" or "COMPANY NAME - Location"
        parts = re.split(r"\s+[-–—]\s+", s, maxsplit=1)
        company = parts[0].strip() if parts else s
        
        # If there's a dash, check if the right part is a description/subtitle
        if len(parts) == 2:
            right_part = parts[1].strip()
            # If right part looks like a company description (lowercase start, contains common words)
            # then use the left part as company name
            if right_part and (right_part[0].islower() or 
                any(word in right_part.lower() for word in ["commerce", "grocery", "retail", "manufacturing", "technology"])):
                company = parts[0].strip()
        
        if _looks_like_location(company):
            return None
        if company.strip().lower() in WORK_MODE_TOKENS:
            return None
        return company if len(company) >= 2 else None

    def _extract_employer_from_dash_line(line: str) -> Optional[str]:
        if not line:
            return None
        s = _clean_header_line(line)
        if not s:
            return None
        if _looks_like_role(s) or "|" in s:
            return None
        m = re.split(r"\s+[-–—]\s+", s, maxsplit=1)
        if len(m) >= 2:
            left = m[0].strip()
            right = m[1].strip() if len(m) > 1 else ""
            if left and not _looks_like_location(left):
                if left.strip().lower() in WORK_MODE_TOKENS:
                    return None
                # Check if right part looks like a company description (not a role, not a location)
                # This handles "FRESH FOOD FACTORY - E-Commerce Grocery" format
                if right and not _looks_like_role(right) and not _looks_like_location(right):
                    # Right part is likely a description, left is the company
                    return left
                # Also return left if it's clearly a company name (uppercase, contains company keywords)
                if left.isupper() or any(kw in left.lower() for kw in ["factory", "mill", "services", "consulting", "university", "college", "constructions"]):
                    return left
                return left
        return None

    def _split_trailing_location(line: str) -> tuple[str, Optional[str]]:
        s = _clean_header_line(line)
        if not s:
            return "", None
        if "," not in s:
            parts = s.split()
            if len(parts) >= 3:
                loc2 = " ".join(parts[-2:])
                if _looks_like_location(loc2):
                    main = " ".join(parts[:-2]).strip(" -–—,|")
                    if len(main) >= 3:
                        return main, loc2
            return s, None

        ORG_STOP_WORDS = {
            "university", "college", "institute", "school", "academy",
            "services", "consulting", "factory", "mills", "mill", "construction", "constructions",
            "company", "corp", "inc", "ltd", "llc", "grocery", "e-commerce",
        }

        # Find the rightmost comma - this is typically before the location
        last_comma = s.rfind(",")
        right = s[last_comma + 1 :].strip()
        left = s[:last_comma].rstrip()
        if not right or not left:
            return s, None

        if right.lower() in WORK_MODE_TOKENS:
            main = left.strip(" -–—,|")
            return main if main else s, right.title()

        # Check if right part looks like a valid location (City, State or City)
        # If it contains only 1-3 capitalized words, it's likely a location
        right_words = right.split()
        if len(right_words) <= 3 and all(w[0].isupper() if w else False for w in right_words):
            # This looks like a simple location, use it directly
            if _looks_like_location(right):
                return left.strip(" -–—,|"), right
        
        # Otherwise, try to extract city from the left part before the comma
        words = left.split()
        city_words: list[str] = []
        for w in reversed(words):
            wl = w.lower().strip(".,")
            if wl in ORG_STOP_WORDS:
                break
            if w and (w[0].isupper() or w.isupper()):
                city_words.append(w)
                continue
            break

        if not city_words:
            return s, None

        city = " ".join(reversed(city_words))
        loc = f"{city}, {right}"
        if not _looks_like_location(loc):
            return s, None

        suffix = loc
        if not s.endswith(suffix):
            s_norm = re.sub(r"\s{2,}", " ", s)
            suffix_norm = re.sub(r"\s{2,}", " ", suffix)
            if s_norm.endswith(suffix_norm):
                s = s_norm
                suffix = suffix_norm

        main = s[: -len(suffix)].strip(" -–—,|")
        if len(main) < 3:
            return s, None
        return main, loc

    def _title_from_pipe_line(line: str) -> Optional[str]:
        if not line:
            return None
        s = _clean_header_line(line)
        if not s:
            return None
        if "|" not in s:
            return None
        parts = [p.strip() for p in s.split("|") if p and p.strip()]
        if not parts:
            return None
        for p in parts:
            if _looks_like_role(p):
                return p
        return parts[0]

    def _employer_from_pipe_line(line: str) -> Optional[str]:
        if not line:
            return None
        s = _clean_header_line(line)
        if not s or "|" not in s:
            return None
        parts = [p.strip() for p in s.split("|") if p and p.strip()]
        if len(parts) < 2:
            return None
        if not _looks_like_role(parts[0]):
            return None
        
        # Field of study / department keywords that should not be employers
        FIELD_KEYWORDS = {
            "management", "engineering", "technology", "operations", "finance", 
            "marketing", "sales", "administration", "human resources", "supply chain",
            "business", "analytics", "data science", "computer science", "information",
            "accounting", "economics", "strategy", "consulting"
        }
        
        for candidate in parts[1:3]:
            low = candidate.lower()
            if low in WORK_MODE_TOKENS:
                continue
            if re.search(DATE_TOKEN, candidate, re.I):
                continue
            if low.startswith("key "):
                continue
            # Skip if it looks like a field of study or department name
            if any(keyword in low for keyword in FIELD_KEYWORDS):
                continue
            # Skip if it looks like another role description
            if _looks_like_role(candidate):
                continue
            return candidate
        return None

    def _extract_title_employer_from_dash_line(line: str) -> tuple[Optional[str], Optional[str]]:
        if not line:
            return None, None
        s = _clean_header_line(line)
        if not s:
            return None, None
        if "|" in s:
            return None, None
        parts = re.split(r"\s+[-–—]\s+", s, maxsplit=1)
        if len(parts) != 2:
            return None, None
        left, right = parts[0].strip(), parts[1].strip()
        if not left or not right:
            return None, None
        if _looks_like_location(left) or _looks_like_location(right):
            return None, None
        if _looks_like_role(left) and not _looks_like_role(right):
            return left, right
        return None, None

    def _parse_pipe_date_blocks(text: str) -> list[dict]:
        if not text:
            return []

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        blocks: list[dict] = []
        i = 0
        while i < len(lines) - 1:
            title_line = lines[i]
            date_line = lines[i + 1]

            if "|" not in title_line or not _looks_like_role(title_line):
                i += 1
                continue

            st, ed, cur = _extract_date_range(date_line)
            if not (st or cur):
                i += 1
                continue

            desc_lines: list[str] = []
            j = i + 2
            while j < len(lines):
                l = lines[j]
                if "|" in l and _looks_like_role(l):
                    break
                desc_lines.append(l)
                j += 1

            job = _title_from_pipe_line(title_line)
            employer = _employer_from_pipe_line(title_line)

            _, loc_tail = _extract_inline_location_tail(date_line)
            city = None
            work_mode = None
            if loc_tail and loc_tail.lower() in WORK_MODE_TOKENS:
                work_mode = loc_tail.title()
            elif loc_tail:
                city = loc_tail

            e = _Entry(
                jobTitle=job,
                employer=employer,
                startDate=st,
                endDate=ed,
                isCurrent=cur,
                city=city,
                workMode=work_mode,
                desc_lines=desc_lines,
            )
            blocks.append(e.to_dict())
            i = j
        return blocks

    @dataclass
    class _Entry:
        jobTitle: Optional[str] = None
        employer: Optional[str] = None
        startDate: Optional[str] = None
        endDate: Optional[str] = None
        isCurrent: bool = False
        city: Optional[str] = None
        experienceType: Optional[str] = None
        experienceCategory: Optional[str] = None
        workMode: Optional[str] = None
        isSelfEmployed: bool = False
        isPromotion: bool = False
        confidenceScore: Optional[int] = None
        desc_lines: list[str] = None

        def to_dict(self) -> dict:
            def _strip_bullet(s: str) -> str:
                t = (s or "").lstrip()
                while t and t[0] in r"•\-*◦▪→\u2022\u2023\u25E6\u25AA\u25CF":
                    t = t[1:].lstrip()
                return t
            lines = [ _strip_bullet(ln) for ln in (self.desc_lines or []) ]
            description = "\n".join(lines).strip() if lines else None

            score = 0
            if self.jobTitle:
                score += 1
            if self.employer:
                score += 1
            if self.startDate:
                score += 1
            if self.endDate or self.isCurrent:
                score += 1
            if description:
                score += 1

            return {
                "jobTitle": self.jobTitle,
                "employer": self.employer,
                "startDate": self.startDate,
                "endDate": self.endDate,
                "isCurrent": self.isCurrent,
                "city": self.city,
                 "experienceType": self.experienceType,
                 "experienceCategory": self.experienceCategory,
                 "workMode": self.workMode,
                 "isSelfEmployed": self.isSelfEmployed,
                 "isPromotion": self.isPromotion,
                 "confidenceScore": score,
                "description": description or None,
            }

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

    pipe_blocks = _parse_pipe_date_blocks(text)
    if len(pipe_blocks) >= 2:
        return pipe_blocks

    lines = [ln.rstrip() for ln in text.splitlines()]
    expanded_lines: list[str] = []
    for ln in lines:
        expanded_lines.extend(_split_two_column_line(ln))
    lines = expanded_lines

    cleaned_lines: list[str] = []
    for idx, ln in enumerate(lines):
        s = (ln or "").strip()
        if re.fullmatch(r"\d{4}", s) and idx + 1 < len(lines):
            n = (lines[idx + 1] or "").strip()
            st, ed, cur = _extract_date_range(n)
            if st or cur:
                continue
        cleaned_lines.append(ln)
    lines = cleaned_lines

    out: list[_Entry] = []
    current: Optional[_Entry] = None
    pending_headers: list[str] = []
    tech_list_continuation = False
    
    # Track last seen company info for multi-role entries under same company
    last_company_name: Optional[str] = None
    last_company_city: Optional[str] = None

    def _start_new_entry(start: Optional[str], end: Optional[str], is_current: bool, header_parts: list[str]):
        nonlocal current, out
        if current:
            out.append(current)

        start, end = _maybe_swap_dates(start, end)
        e = _Entry(startDate=start, endDate=end, isCurrent=is_current, desc_lines=[])

        header_items: list[dict] = []
        city = None
        for raw in header_parts:
            raw_s = raw or ""
            is_leading_dash = raw_s.lstrip().startswith(("-", "–", "—"))
            cleaned = _clean_header_line(raw_s)
            if not cleaned:
                continue
            main, loc = _split_trailing_location(cleaned)
            if loc and not city:
                city = loc
            header_items.append(
                {
                    "raw": raw_s,
                    "clean": cleaned,
                    "main": main or cleaned,
                    "loc": loc,
                    "leading_dash": is_leading_dash,
                }
            )

        cleaned_parts = [it["main"] for it in header_items if it.get("main")]

        job_from_dash, employer_from_dash = None, None
        for it in header_items:
            tit, emp = _extract_title_employer_from_dash_line(it["clean"])
            if tit and emp:
                job_from_dash, employer_from_dash = tit, emp
                break

        employer = employer_from_dash
        if not employer:
            # Try to extract employer from lines with dash separator (e.g., "COMPANY - Description")
            for it in header_items:
                # First try with the main field (location stripped)
                employer = _extract_employer_from_dash_line(it["main"])
                if employer:
                    break
                # Then try with the clean field (full line)
                employer = _extract_employer_from_dash_line(it["clean"])
                if employer:
                    break
        if not employer:
            for it in header_items:
                employer = _employer_from_pipe_line(it["clean"])
                if employer:
                    break
        if not employer:
            for p in cleaned_parts:
                employer = _extract_employer_from_company_line(p)
                if employer:
                    break

        if not city:
            for p in cleaned_parts:
                if _looks_like_location(p) and not _looks_like_role(p):
                    city = p
                    break

        if employer:
            employer2, tail_loc = _extract_inline_location_tail(employer)
            if tail_loc and not city:
                city = tail_loc
            employer = employer2

        job = job_from_dash
        if not job:
            for it in reversed(header_items):
                t = _title_from_pipe_line(it["clean"])
                if t:
                    job = t
                    break
        if not job:
            role_line = next((p for p in cleaned_parts if _looks_like_role(p)), None)
            if role_line:
                parts = _split_by_separators(role_line)
                job = parts[0] if parts else role_line

        if not job:
            # First try to find a line that looks like a role
            for p in cleaned_parts:
                if _looks_like_role(p) and not _looks_like_location(p):
                    job = p
                    break
            # If still no job, take the first non-location line
            if not job:
                for p in cleaned_parts:
                    if not _looks_like_location(p):
                        job = p
                        break

        # Common technical terms/acronyms that should NOT be employers
        INVALID_EMPLOYER_TERMS = {
            "erp", "wms", "tms", "sap", "crm", "sql", "python", "excel", "power bi",
            "tableau", "alteryx", "hana", "s/4hana", "smart networks", "smart networks'",
            "lean six sigma", "dmaic", "scor", "s&op", "kpi", "roi", "etl",
            "city",  # Placeholder text
        }
        
        def _is_valid_employer(emp: str) -> bool:
            if not emp:
                return False
            emp_lower = emp.strip().lower().rstrip("'\"")
            # Reject if it's a known invalid term
            if emp_lower in INVALID_EMPLOYER_TERMS:
                return False
            # Reject if it's too short (likely an acronym)
            if len(emp_lower) <= 3 and emp_lower.isupper():
                return False
            # Reject if it contains quotes (likely extracted from description)
            if "'" in emp or '"' in emp:
                return False
            return True

        if not employer:
            for p in [it["main"] for it in header_items if not it.get("leading_dash")] + cleaned_parts:
                if p == job:
                    continue
                if _looks_like_location(p):
                    continue
                if _looks_like_role(p) or "|" in p:
                    continue
                if isinstance(p, str) and p.strip().lower() in WORK_MODE_TOKENS:
                    continue
                if not _is_valid_employer(p):
                    continue
                employer = p
                break

        # Validate the extracted employer
        if employer and not _is_valid_employer(employer):
            employer = None

        if employer and job and employer.strip().lower() == job.strip().lower():
            employer = _extract_employer_from_dash_line(" - ".join([employer, "x"])) or None

        # Use nonlocal to access and update last_company tracking variables
        nonlocal last_company_name, last_company_city
        
        # If we found a new employer, update the tracking variables
        if employer:
            last_company_name = employer
            if city:
                last_company_city = city
        else:
            # No employer found in header - use last seen company if available
            # This handles multiple roles under the same company header
            if last_company_name and job:
                employer = last_company_name
                if not city and last_company_city:
                    city = last_company_city

        header_text = " ".join(cleaned_parts).lower()
        exp_type = "PROFESSIONAL"
        job_low = (job or "").lower()
        if any(tok in header_text for tok in ("volunteer", "volunteering", "ngo", "non-profit", "nonprofit", "board")):
            exp_type = "VOLUNTEER"
        if any(tok in header_text for tok in ("internship", "intern ", "apprentice")) or "intern" in job_low:
            exp_type = "INTERNSHIP"
        if any(tok in header_text for tok in ("career break", "sabbatical", "maternity leave", "paternity leave")) or any(
            tok in job_low for tok in ("career break", "sabbatical", "maternity leave", "paternity leave")
        ):
            exp_type = "BREAK"

        experience_category = None
        is_self_employed = False
        combined = (" ".join([job or "", employer or ""])).lower()
        if any(tok in combined for tok in ("freelance", "contract", "consultant", "self-employed", "self employed")):
            experience_category = "FREELANCE"
            is_self_employed = True
        if any(tok in combined for tok in ("founder", "co-founder", "owner")):
            is_self_employed = True

        def _normalize_work_mode(s: str | None) -> Optional[str]:
            if not s:
                return None
            low = s.lower()
            if "remote" in low or "wfh" in low or "work from home" in low:
                return "Remote"
            if "hybrid" in low:
                return "Hybrid"
            if "on-site" in low or "onsite" in low or "on site" in low:
                return "On-site"
            return None

        work_mode: Optional[str] = None
        for txt in cleaned_parts + ([city] if city else []):
            wm = _normalize_work_mode(txt)
            if wm:
                work_mode = wm
                break

        e.jobTitle = job
        e.employer = employer
        e.city = _sanitize_city_value(city)
        e.experienceType = exp_type
        e.experienceCategory = experience_category
        e.isSelfEmployed = is_self_employed
        e.workMode = work_mode
        current = e

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        if _looks_like_garbage(line):
            continue

        inline_label_match = bool(re.match(
            r"^(key\s+(responsibilities|technologies|highlights|achievements)|technologies\s+used|tools\s+used|tech\s+stack)\s*:?",
            line.strip(),
            re.IGNORECASE,
        ))
        if current and inline_label_match:
            current.desc_lines.append(line.strip())
            if re.match(r"^(key\s+technologies|technologies\s+used|tools\s+used|tech\s+stack)\b", line.strip(), re.I):
                tech_list_continuation = True
            continue

        if current and tech_list_continuation:
            st, ed, cur = _extract_date_range(line)
            if st or cur or "|" in line or re.search(r"\s+[-–—]\s+", line) or _looks_like_role(line):
                tech_list_continuation = False
            else:
                if current.desc_lines:
                    current.desc_lines[-1] = f"{current.desc_lines[-1].rstrip()} {line.strip()}".strip()
                else:
                    current.desc_lines.append(line.strip())
                continue

        if _is_bullet_line(line):
            if current:
                current.desc_lines.append(line)
            continue

        if current and not current.desc_lines and not _is_bullet_line(line):
            start, end, is_current = _extract_date_range(line)
            if not start and not is_current and "," in line:
                cleaned_line = _clean_header_line(line)
                main, loc = _split_trailing_location(cleaned_line)
                if (not loc and main and "," in main) or (main == cleaned_line and "," in cleaned_line):
                    parts = [p.strip() for p in cleaned_line.split(",", 1) if p.strip()]
                    if len(parts) == 2 and _looks_like_location(parts[1]):
                        main, loc = parts[0], parts[1]
                if main and (loc or "," in line):
                    emp = _extract_employer_from_company_line(main) or (main if not _looks_like_location(main) else None)
                    if emp and not _looks_like_role(emp):
                        if not current.employer:
                            current.employer = emp
                        if loc and not current.city:
                            candidate_city = _sanitize_city_value(loc)
                            if candidate_city:
                                current.city = candidate_city
                        continue
            
            # Check if this line is a company name without location (uppercase, no role keywords)
            # This handles cases where company appears on its own line above the role
            if not start and not is_current and not "," in line:
                cleaned_line = _clean_header_line(line)
                if cleaned_line and len(cleaned_line) >= 3 and len(cleaned_line) <= 80:
                    # If line is mostly uppercase or title case and doesn't look like a role
                    if (cleaned_line.isupper() or cleaned_line.istitle()) and not _looks_like_role(cleaned_line):
                        emp = _extract_employer_from_company_line(cleaned_line)
                        if emp and not current.employer:
                            current.employer = emp
                            continue

        if current and _looks_like_location(line):
            cleaned_loc_line = _clean_header_line(line)
            if re.search(r"\b(university|college|school|factory|consulting|services|company|corp|inc|llc)\b", cleaned_loc_line, re.I):
                pass
            else:
                if not current.employer and "," in cleaned_loc_line:
                    parts = [_clean_header_line(p) for p in cleaned_loc_line.split(",", 1) if p.strip()]
                    if len(parts) == 2 and _looks_like_location(parts[1]):
                        current.employer = parts[0]
                        current.city = parts[1]
                        continue
                if not current.city:
                    candidate_city = _sanitize_city_value(cleaned_loc_line)
                    if candidate_city:
                        current.city = candidate_city
                continue

        start, end, is_current = _extract_date_range(line)
        if start or is_current:
            residue = _strip_date_range_from_line(line)
            header_parts = pending_headers[-5:] + ([residue] if residue else [])
            _start_new_entry(start, end, is_current, header_parts)
            pending_headers = []
            continue

        if current is None:
            st2, ed2, cur2 = _extract_date_range(line)
            if st2 or cur2:
                left, _, desc = line.partition(" - ")
                header = _strip_date_range_from_line(left)
                tmp_headers = [header] if header else []
                _start_new_entry(st2, ed2, cur2, tmp_headers)
                if desc.strip():
                    current.desc_lines.append(desc.strip())
                continue

        if current and current.desc_lines:
            if re.match(
                r"^(key\s+(responsibilities|technologies|highlights|achievements)|technologies\s+used|tools\s+used|tech\s+stack)\s*:?",
                line.strip(),
                re.IGNORECASE,
            ):
                current.desc_lines.append(line.strip())
                continue

            if _looks_like_entry_header(line):
                cleaned = _clean_header_line(line)
                if cleaned:
                    pending_headers.append(cleaned)
                    if len(pending_headers) > 6:
                        pending_headers = pending_headers[-6:]
                continue

            last = current.desc_lines[-1]
            if last and not last.endswith((".", ":", ";")):
                current.desc_lines[-1] = f"{last} {line}"
            else:
                current.desc_lines.append(line)
            continue

        if current and not current.desc_lines:
            if not _looks_like_entry_header(line) and not _looks_like_location(line):
                current.desc_lines.append(line)
                continue

        cleaned = _clean_header_line(line)
        if cleaned and len(cleaned) <= 140:
            pending_headers.append(cleaned)
            if len(pending_headers) > 4:
                pending_headers = pending_headers[-4:]

    if current:
        out.append(current)

    result = []
    for e in out:
        d = e.to_dict()
        if any(d.get(k) for k in ("jobTitle", "employer", "startDate", "endDate", "description")):
            if d.get("city"):
                d["city"] = _sanitize_city_value(d.get("city"))
            result.append(d)

    if len(result) == 0:
        block_result = _parse_experience_blocks(
            text,
            RANGE_RE=RANGE_RE,
            _extract_date_range=_extract_date_range,
            _strip_date_range_from_line=_strip_date_range_from_line,
            _clean_header_line=_clean_header_line,
            _split_trailing_location=_split_trailing_location,
            _looks_like_location=_looks_like_location,
            _looks_like_role=_looks_like_role,
            _extract_employer_from_dash_line=_extract_employer_from_dash_line,
            _employer_from_pipe_line=_employer_from_pipe_line,
            _title_from_pipe_line=_title_from_pipe_line,
            _extract_title_employer_from_dash_line=_extract_title_employer_from_dash_line,
            _is_bullet_line=_is_bullet_line,
            _maybe_swap_dates=_maybe_swap_dates,
            WORK_MODE_TOKENS=WORK_MODE_TOKENS,
        )
        if len(block_result) > len(result):
            result = block_result

    for d in result:
        if isinstance(d, dict) and d.get("city"):
            d["city"] = _sanitize_city_value(d.get("city"))

    return result


def _parse_experience_blocks(
    text: str,
    *,
    RANGE_RE,
    _extract_date_range,
    _strip_date_range_from_line,
    _clean_header_line,
    _split_trailing_location,
    _looks_like_location,
    _looks_like_role,
    _extract_employer_from_dash_line,
    _employer_from_pipe_line,
    _title_from_pipe_line,
    _extract_title_employer_from_dash_line,
    _is_bullet_line,
    _maybe_swap_dates,
    WORK_MODE_TOKENS,
) -> list[dict]:
    if not text or not text.strip():
        return []
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for ln in lines:
        line = (ln or "").strip()
        if not line:
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue
        start, end, is_current = _extract_date_range(line)
        if start or is_current:
            if current_block:
                blocks.append(current_block)
                current_block = []
        current_block.append(line)
    if current_block:
        blocks.append(current_block)

    if len(blocks) < 2 and "\n\n" in text:
        raw_blocks = re.split(r"\n\s*\n", text)
        blocks = []
        for raw in raw_blocks:
            bl = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if bl:
                blocks.append(bl)

    out: list[dict] = []
    for block in blocks:
        if not block:
            continue
        start, end, is_current = None, None, False
        date_line_idx = -1
        for i, line in enumerate(block):
            s, e, cur = _extract_date_range(line)
            if s or cur:
                start, end, is_current = s, e, cur
                date_line_idx = i
                break
        start, end = _maybe_swap_dates(start, end) if start or end else (start, end)

        header_lines = []
        desc_lines = []
        for i, line in enumerate(block):
            if _is_bullet_line(line):
                desc_lines.append(line)
            elif i == date_line_idx:
                residue = _strip_date_range_from_line(line)
                if residue:
                    header_lines.append(_clean_header_line(residue))
            else:
                if date_line_idx >= 0 and i > date_line_idx and not _is_bullet_line(line):
                    desc_lines.append(line)
                else:
                    header_lines.append(_clean_header_line(line))

        job_title = None
        employer = None
        city = None
        for line in header_lines:
            t, emp = _extract_title_employer_from_dash_line(line)
            if t and emp:
                job_title = job_title or t
                employer = employer or emp
                continue
            emp = _extract_employer_from_dash_line(line)
            if emp:
                employer = employer or emp
                continue
            emp = _employer_from_pipe_line(line)
            if emp:
                employer = employer or emp
            tit = _title_from_pipe_line(line)
            if tit:
                job_title = job_title or tit
            main, loc = _split_trailing_location(line)
            if loc:
                city = city or loc
            if _looks_like_role(line) and not job_title:
                job_title = line
            if main and not _looks_like_location(main) and not _looks_like_role(main) and not employer:
                if main.lower() not in WORK_MODE_TOKENS:
                    employer = employer or main

        if not job_title and header_lines:
            job_title = next((h for h in header_lines if _looks_like_role(h)), header_lines[0] if header_lines else None)
        if not employer and header_lines:
            employer = next((h for h in header_lines if not _looks_like_location(h) and h != job_title and h.lower() not in WORK_MODE_TOKENS), None)

        def _strip_bullet(s: str) -> str:
            t = (s or "").lstrip()
            while t and t[0] in r"•\-*◦▪→\u2022\u2023\u25E6\u25AA\u25CF":
                t = t[1:].lstrip()
            return t
        description = "\n".join(_strip_bullet(ln) for ln in desc_lines).strip() if desc_lines else None

        if any([job_title, employer, start, end, description]):
            out.append({
                "jobTitle": job_title,
                "employer": employer,
                "startDate": start,
                "endDate": end,
                "isCurrent": is_current,
                "city": city,
                "description": description,
            })
    return out
