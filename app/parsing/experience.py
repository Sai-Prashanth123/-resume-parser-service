
import re
from dataclasses import dataclass
from typing import Optional

from dateutil import parser as date_parser

def parse_experience(text):
    """
    Work experience parser aimed at real-world PDF-extracted resumes.
    Extracts: jobTitle, employer, dates, description bullets.
    """
    if not text or not text.strip():
        return []

    ROLE_KEYWORDS = {
        "developer", "engineer", "manager", "analyst", "intern", "consultant", "designer",
        "architect", "lead", "specialist", "coordinator", "director", "associate",
        "assistant", "administrator", "officer", "executive", "supervisor", "owner",
        "president", "vice", "vp", "product", "project", "program",
        "founder", "ceo", "coo", "cto", "cfo",
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

    MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    DATE_TOKEN = rf"(?:{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
    # Include U+FFFD as some PDFs extract "–" as replacement char.
    RANGE_RE = re.compile(
        rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to|\uFFFD)\s*(?P<end>{DATE_TOKEN}|present|current|now)",
        re.IGNORECASE,
    )

    def _is_bullet_line(line: str) -> bool:
        s = (line or "").lstrip()
        return bool(s) and s[0] in {"•", "-", "*", "◦", "▪", "→"}

    def _looks_like_role(text_line: str) -> bool:
        low = (text_line or "").lower()
        return any(kw in low for kw in ROLE_KEYWORDS)

    def _extract_date_range(line: str) -> tuple[Optional[str], Optional[str], bool]:
        if not line:
            return None, None, False
        m = RANGE_RE.search(line)
        if not m:
            # Single date + "Present"
            if re.search(r"\b(present|current|now)\b", line, re.I):
                # Try to find a start token
                m2 = re.search(DATE_TOKEN, line, re.I)
                if m2:
                    return m2.group(0), None, True
            return None, None, False
        start = m.group("start")
        end_raw = m.group("end")
        is_current = bool(re.fullmatch(r"(present|current|now)", end_raw.strip(), re.I))
        end = None if is_current else end_raw
        return start, end, is_current

    def _clean_header_line(line: str) -> str:
        s = (line or "").strip()
        # Remove surrounding separators (common in PDF text)
        s = re.sub(r"^[\s•\-\*|]+", "", s)
        # Common when stripping dates: ",Remote" -> "Remote"
        s = re.sub(r"^,\s*", "", s)
        s = re.sub(r"[\s|]+$", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    def _strip_date_range_from_line(line: str) -> str:
        if not line:
            return ""
        s = RANGE_RE.sub("", line)
        # also remove lone date tokens remaining
        s = re.sub(DATE_TOKEN, "", s, flags=re.I)
        # Keep pipes ("|") - they're useful separators in many resumes.
        s = re.sub(r"[\s\-–—,]{2,}", " ", s).strip(" -–—,")
        return s.strip()

    def _split_by_separators(s: str) -> list[str]:
        if not s:
            return []
        # Prefer separators that often split title/employer/location
        parts = re.split(r"\s*(?:\||@|\s+at\s+|\s+[-–—]\s+)\s*", s, flags=re.I)
        parts = [p.strip() for p in parts if p and p.strip()]
        return parts

    def _looks_like_entry_header(line: str) -> bool:
        """
        Detect likely start-of-entry lines even when we're currently inside bullets.
        This prevents company/title lines from being swallowed into the previous job's description.
        """
        if not line:
            return False
        s = line.strip()
        if len(s) < 3 or len(s) > 140:
            return False
        # Dates always indicate entry boundary
        st, ed, cur = _extract_date_range(s)
        if st or cur:
            return True
        # Company lines often look like "COMPANY - descriptor City, Country"
        if re.search(r"\s+[-–—]\s+", s) and not s.endswith("."):
            return True
        # Role lines often use pipes
        if "|" in s and not s.endswith("."):
            return True
        # Location-only line
        if _looks_like_location(s) and not s.endswith("."):
            return True
        # Short role-looking line
        if _looks_like_role(s) and len(s) <= 80 and not s.endswith("."):
            return True
        return False

    def _looks_like_location(s: str) -> bool:
        """
        Heuristic: detect location-ish strings like "Washington, DC", "Hyderabad, India",
        or "Washington, DC & Vietnam".
        """
        if not s:
            return False
        t = s.strip()
        if len(t) < 3 or len(t) > 80:
            return False
        # Allow work-mode locations like "Remote" without a comma.
        if t.lower() in WORK_MODE_TOKENS:
            return True
        # Require a comma to reduce false positives (e.g., org names with "DC" in them)
        if "," not in t:
            return False
        # Has comma-separated place, optionally with state abbreviation / country
        if re.search(r"[A-Za-z]\s*,\s*[A-Za-z]", t):
            return True
        return False

    def _extract_employer_from_company_line(line: str) -> Optional[str]:
        """
        For lines like "VINAMILK - Vietnam’s largest dairy company", prefer employer "VINAMILK".
        """
        if not line:
            return None
        s = _clean_header_line(line)
        if not s:
            return None
        # If this looks like a role line, don't treat it as employer
        if _looks_like_role(s) or "|" in s.lower():
            return None
        # Prefer first part before dash as the company name
        parts = re.split(r"\s+[-–—]\s+", s, maxsplit=1)
        company = parts[0].strip() if parts else s
        # Avoid accidental location-only "Washington, DC"
        if _looks_like_location(company):
            return None
        if company.strip().lower() in WORK_MODE_TOKENS:
            return None
        # Avoid overly short employer
        return company if len(company) >= 2 else None

    def _extract_employer_from_dash_line(line: str) -> Optional[str]:
        """
        For lines like "Company Name - Tagline / unit / department ...", prefer employer "Company Name".
        """
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
            if left and not _looks_like_location(left):
                if left.strip().lower() in WORK_MODE_TOKENS:
                    return None
                return left
        return None

    def _split_trailing_location(line: str) -> tuple[str, Optional[str]]:
        """
        Split a line like "Georgetown University Washington, DC" into:
          ("Georgetown University", "Washington, DC")
        Also works for "... Hyderabad, India" / "... Washington, DC & Vietnam".
        """
        s = _clean_header_line(line)
        if not s:
            return "", None
        if "," not in s:
            return s, None

        # Heuristic extraction of "City, Rest" by walking backwards from the comma and
        # taking only capitalized words (stops before org words like University/Services/etc).
        ORG_STOP_WORDS = {
            "university", "college", "institute", "school", "academy",
            "services", "consulting", "factory", "mills", "mill", "construction", "constructions",
            "company", "corp", "inc", "ltd",
        }

        last_comma = s.rfind(",")
        right = s[last_comma + 1 :].strip()
        left = s[:last_comma].rstrip()
        if not right or not left:
            return s, None

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

        # Remove the trailing location from the string to get the "main" part
        suffix = loc
        if not s.endswith(suffix):
            # Try a more forgiving removal (extra spaces)
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
        """
        Extract a job title from a pipe-separated line:
          "Senior Engineer | Platform | Remote" -> "Senior Engineer"
        """
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
        # Prefer the first part that looks like a role, else first part.
        for p in parts:
            if _looks_like_role(p):
                return p
        return parts[0]

    def _employer_from_pipe_line(line: str) -> Optional[str]:
        """
        Extract an employer/company name from a pipe-separated line:
          "Product Designer | JobSpring" -> "JobSpring"
          "Full Stack Dev | JobSpring | Remote" -> "JobSpring"
        """
        if not line:
            return None
        s = _clean_header_line(line)
        if not s or "|" not in s:
            return None
        parts = [p.strip() for p in s.split("|") if p and p.strip()]
        if len(parts) < 2:
            return None
        # If the first part looks like a role, the next part is often the employer.
        if not _looks_like_role(parts[0]):
            return None
        for candidate in parts[1:3]:
            low = candidate.lower()
            if low in WORK_MODE_TOKENS:
                continue
            if re.search(DATE_TOKEN, candidate, re.I):
                continue
            # Skip obvious labels
            if low.startswith("key "):
                continue
            return candidate
        return None

    @dataclass
    class _Entry:
        jobTitle: Optional[str] = None
        employer: Optional[str] = None
        startDate: Optional[str] = None
        endDate: Optional[str] = None
        isCurrent: bool = False
        city: Optional[str] = None
        desc_lines: list[str] = None

        def to_dict(self) -> dict:
            description = "\n".join(self.desc_lines).strip() if self.desc_lines else None
            return {
                "jobTitle": self.jobTitle,
                "employer": self.employer,
                "startDate": self.startDate,
                "endDate": self.endDate,
                "isCurrent": self.isCurrent,
                "city": self.city,
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

    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[_Entry] = []
    current: Optional[_Entry] = None
    pending_headers: list[str] = []  # last non-bullet lines
    tech_list_continuation = False  # handles wrapped "Key Technologies" lines

    def _start_new_entry(start: Optional[str], end: Optional[str], is_current: bool, header_parts: list[str]):
        nonlocal current, out
        if current:
            out.append(current)

        start, end = _maybe_swap_dates(start, end)
        e = _Entry(startDate=start, endDate=end, isCurrent=is_current, desc_lines=[])

        # Infer jobTitle/employer/city from header parts (company line, location line, role line)
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

        # Prefer employer from a "Company - ..." style line (very common)
        employer = None
        for it in header_items:
            employer = _extract_employer_from_dash_line(it["clean"])
            if employer:
                break
        if not employer:
            # Common format: "Title | Company"
            for it in header_items:
                employer = _employer_from_pipe_line(it["clean"])
                if employer:
                    break
        if not employer:
            for p in cleaned_parts:
                employer = _extract_employer_from_company_line(p)
                if employer:
                    break

        # Prefer explicit location line if we didn't already extract trailing location
        if not city:
            for p in cleaned_parts:
                if _looks_like_location(p) and not _looks_like_role(p):
                    city = p
                    break

        # Choose jobTitle:
        # - prefer residue/lines that contain '|' (often "Title | Dept | ...")
        # - else prefer role keyword lines
        job = None
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

        # If no role line was found, fallback to any non-location line
        if not job:
            for p in cleaned_parts:
                if not _looks_like_location(p):
                    job = p
                    break

        # If employer wasn't found, infer from remaining non-role/non-location parts.
        # Prefer a non-leading-dash line (descriptor lines often start with "- ...").
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
                employer = p
                break

        # Avoid employer == jobTitle (common false-positive); keep employer if it looks like an org name, else drop it
        if employer and job and employer.strip().lower() == job.strip().lower():
            # If we have a dash line employer, keep it; otherwise null it
            employer = _extract_employer_from_dash_line(" - ".join([employer, "x"])) or None

        e.jobTitle = job
        e.employer = employer
        e.city = city
        current = e

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        # Always keep inline labels inside the current entry (even before bullets start).
        inline_label_match = bool(re.match(
            r"^(key\s+(responsibilities|technologies|highlights|achievements)|technologies\s+used|tools\s+used|tech\s+stack)\s*:?",
            line.strip(),
            re.IGNORECASE,
        ))
        if current and inline_label_match:
            current.desc_lines.append(line.strip())
            # If this is a technologies/stack label, the next line(s) may be a wrapped continuation list.
            if re.match(r"^(key\s+technologies|technologies\s+used|tools\s+used|tech\s+stack)\b", line.strip(), re.I):
                tech_list_continuation = True
            continue

        # If we are in a wrapped technologies list, treat short comma-separated continuations
        # as part of the current entry (not as a "location header" for the next job).
        if current and tech_list_continuation:
            # Stop continuation if a new entry header is clearly starting (role/company/date lines).
            st, ed, cur = _extract_date_range(line)
            if st or cur or "|" in line or re.search(r"\s+[-–—]\s+", line) or _looks_like_role(line):
                tech_list_continuation = False
            else:
                # Append continuation text (e.g., "Blob Storage, Docker")
                if current.desc_lines:
                    current.desc_lines[-1] = f"{current.desc_lines[-1].rstrip()} {line.strip()}".strip()
                else:
                    current.desc_lines.append(line.strip())
                continue

        if _is_bullet_line(line):
            if current:
                current.desc_lines.append(line)
            continue

        start, end, is_current = _extract_date_range(line)
        if start or is_current:
            # New entry begins around date range lines. Use recent header lines plus date-line residue.
            residue = _strip_date_range_from_line(line)
            # Keep more context: company line + location line + role line are often 3 lines.
            header_parts = pending_headers[-5:] + ([residue] if residue else [])
            _start_new_entry(start, end, is_current, header_parts)
            pending_headers = []
            continue

        # Non-bullet, non-date line:
        if current and current.desc_lines:
            # Preserve common inline labels inside experience blocks (do not merge into bullets).
            # Examples: "Key Responsibilities:", "Key Technologies: Python, FastAPI, React"
            if re.match(
                r"^(key\s+(responsibilities|technologies|highlights|achievements)|technologies\s+used|tools\s+used|tech\s+stack)\s*:?",
                line.strip(),
                re.IGNORECASE,
            ):
                current.desc_lines.append(line.strip())
                continue

            # If this looks like the next entry's header, don't swallow it into description.
            if _looks_like_entry_header(line):
                cleaned = _clean_header_line(line)
                if cleaned:
                    pending_headers.append(cleaned)
                    if len(pending_headers) > 6:
                        pending_headers = pending_headers[-6:]
                continue

            # Otherwise: continuation of description (wrapped lines) – append to last bullet for readability
            last = current.desc_lines[-1]
            if last and not last.endswith((".", ":", ";")):
                current.desc_lines[-1] = f"{last} {line}"
            else:
                current.desc_lines.append(line)
            continue

        # Otherwise treat as header candidate for the next entry
        cleaned = _clean_header_line(line)
        if cleaned and len(cleaned) <= 140:
            pending_headers.append(cleaned)
            if len(pending_headers) > 4:
                pending_headers = pending_headers[-4:]

    if current:
        out.append(current)

    # Filter obvious empty entries
    result = []
    for e in out:
        d = e.to_dict()
        if any(d.get(k) for k in ("jobTitle", "employer", "startDate", "endDate", "description")):
            result.append(d)
    return result
