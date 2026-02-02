import os
import sys

# Ensure imports work when run as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.parsing.normalize import normalize_text
from app.parsing.sectioner import split_sections
from app.parsing.experience import parse_experience


def main():
    t = normalize_text(
        """WORK EXPERIENCE
Product Designer | JobSpring
Dec 2024 - July 2025 ,Remote
• Designed complete UI/UX for the platform
UX/UI Designer | Kodeskool
Aug 2024 - Oct 2024 ,Remote
• Designed Kode Skool's website and logo
"""
    )
    lines = t.splitlines()
    print("line3:", repr(lines[3]))
    print("ord3:", ord(lines[3].lstrip()[0]) if lines[3].strip() else None)
    print("line4:", repr(lines[4]))
    print("line4 last char ord:", ord(lines[4][-1]) if lines[4] else None)
    print("line5:", repr(lines[5]))
    sec = split_sections(t)
    exp = parse_experience(sec.get("experience", ""))
    print("count", len(exp))
    for e in exp:
        print(e.get("jobTitle"), e.get("employer"), e.get("startDate"), e.get("endDate"), e.get("city"))


if __name__ == "__main__":
    main()

