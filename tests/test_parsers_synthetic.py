import pytest

from app.parsing.sectioner import split_sections
from app.parsing.experience import parse_experience
from app.parsing.education import parse_education
from app.parsing.normalize import normalize_text
from app.parsing.personal import extract_personal


def test_section_headers_variants():
    text = normalize_text(
        """
        JOHN DOE
        PROFESSIONAL SUMMARY:
        Strong engineer...

        WORK & EXPERIENCE
        Acme Corp - Platform Team
        Remote, US
        Senior Software Engineer | Backend | Jan 2022 - Present
        • Built APIs

        EDUCATIONAL BACKGROUND
        State University
        City, Country
        Bachelor of Science in Computer Science
        2018
        """
    )
    sections = split_sections(text)
    assert "summary" in sections
    assert "experience" in sections
    assert "education" in sections


def test_experience_parses_company_dash_location_and_pipe_title():
    text = normalize_text(
        """
        EXPERIENCE
        Acme Corporation - Payments
        San Francisco, CA
        Staff Engineer | Platform | Jan 2020 - Mar 2022
        • Led migration
        """
    )
    sections = split_sections(text)
    exp = parse_experience(sections["experience"])
    assert len(exp) >= 1
    e0 = exp[0]
    assert e0["jobTitle"] in {"Staff Engineer", "Engineer", "Staff Engineer | Platform |"}
    assert e0["employer"] == "Acme Corporation"
    assert e0["city"] == "San Francisco, CA"
    assert e0["startDate"] is not None


def test_experience_handles_title_and_dates_same_line():
    text = normalize_text(
        """
        EXPERIENCE
        Example Inc
        London, UK
        Data Analyst | Jan 2019 - Feb 2020
        - Built dashboards
        """
    )
    sections = split_sections(text)
    exp = parse_experience(sections["experience"])
    assert len(exp) >= 1
    assert exp[0]["startDate"] is not None
    assert exp[0]["endDate"] is not None


def test_education_groups_school_location_degree_and_date():
    text = normalize_text(
        """
        EDUCATION
        Example University
        New York, NY
        Master of Science in Data Science
        May 2021
        • GPA 3.9
        """
    )
    sections = split_sections(text)
    edu = parse_education(sections["education"])
    assert len(edu) == 1
    assert edu[0]["schoolName"] == "Example University"
    assert edu[0]["city"] == "New York, NY"
    assert "Master" in (edu[0]["degree"] or "")
    assert edu[0]["endDate"] is not None


def test_education_degree_then_school_format():
    text = normalize_text(
        """
        EDUCATION
        Bachelor of Arts in Economics
        Some College
        Boston, MA
        2016
        """
    )
    sections = split_sections(text)
    edu = parse_education(sections["education"])
    assert len(edu) == 1
    assert edu[0]["schoolName"] == "Some College"
    assert "Bachelor" in (edu[0]["degree"] or "")


def test_education_date_range_sets_start_and_end():
    text = normalize_text(
        """
        EDUCATION
        Example University
        City, Country
        Bachelor of Technology in Computer Science
        Jan 2019 - May 2023
        """
    )
    sections = split_sections(text)
    edu = parse_education(sections["education"])
    assert len(edu) == 1
    assert edu[0]["startDate"] is not None
    assert edu[0]["endDate"] is not None


def test_education_present_sets_start_only():
    text = normalize_text(
        """
        EDUCATION
        Example University
        City, Country
        Bachelor of Technology in Computer Science
        June 2025 - Present
        """
    )
    sections = split_sections(text)
    edu = parse_education(sections["education"])
    assert len(edu) == 1
    assert edu[0]["startDate"] is not None
    assert edu[0]["endDate"] is None


def test_personal_location_only_from_header_lines():
    text = normalize_text(
        """
        Jane Doe
        jane@example.com | (555) 111-2222
        Seattle, WA
        
        EXPERIENCE
        Example Corp
        Chicago, IL
        Engineer | Jan 2020 - Jan 2021
        """
    )
    p = extract_personal(text)
    assert p["city"] == "Seattle"
    assert p["country"] == "WA"


def test_personal_location_from_pipe_separated_contact_line():
    text = normalize_text(
        """
        Jayaprakash Divvela
        O'Fallon, MO | jayaprakashdivvela@gmail.com | (202) 439-6064 | linkedin.com/in/jaya-prakash-divvela
        """
    )
    p = extract_personal(text)
    assert p["city"] == "O'Fallon"
    assert p["country"] == "MO"


def test_sectioner_does_not_split_on_key_technologies():
    text = normalize_text(
        """
        PROFESSIONAL EXPERIENCE
        Jobspring - On-site
        Full Stack & AI Developer | January 2025 – June 2025
        Key Responsibilities:
        • Built something
        Key Technologies: Python, FastAPI, React, Docker
        Freelance AI/ML Developer (Self-Employed)
        Feb 2025 – Present
        • Built another thing
        """
    )
    sections = split_sections(text)
    assert "experience" in sections
    assert "Freelance AI/ML Developer" in sections["experience"]


def test_experience_tech_list_wrapped_line_not_treated_as_location_header():
    text = normalize_text(
        """
        EXPERIENCE
        ExampleCo - Hybrid
        Full Stack Developer | Jan 2025 - Jun 2025
        Key Technologies: Python, FastAPI, React, Azure
        Blob Storage, Docker
        Freelance Developer
        Feb 2025 - Present
        • Did work
        """
    )
    sections = split_sections(text)
    exp = parse_experience(sections.get("experience", ""))
    assert len(exp) >= 2
    assert exp[1].get("city") != "Blob Storage, Docker"


def test_experience_title_pipe_company_and_remote_on_date_line():
    text = normalize_text(
        "WORK EXPERIENCE\n"
        "Product Designer | JobSpring\n"
        "Dec 2024 - July 2025 ,Remote\n"
        "• Designed complete UI/UX for the platform\n"
        "UX/UI Designer | Kodeskool\n"
        "Aug 2024 - Oct 2024 ,Remote\n"
        "• Designed Kode Skool's website and logo\n"
    )
    sections = split_sections(text)
    exp = parse_experience(sections.get("experience", ""))
    assert len(exp) >= 2
    assert exp[0].get("jobTitle") == "Product Designer"
    assert exp[0].get("employer") == "JobSpring"
    assert (exp[0].get("city") or "").lower() in {"remote", ""}


def test_experience_work_history_format_title_then_dates_then_company():
    text = normalize_text(
        """
        WORK HISTORY
        GEOTECHNICAL ENGINEERING MANAGER
        06/2017 to Current
        ECS Limited, Schererville, IN
        • Plan and conduct exploration effectively.
        • Develop design specifications and drawings.
        GEOTECHNICAL ENGINEER
        10/2010 to 06/2017
        Milhaus Development LLC, Hammond, IN
        • Analyzed over 100 survey reports.
        """
    )
    sections = split_sections(text)
    exp = parse_experience(sections.get("experience", ""))
    assert len(exp) >= 2
    e0 = exp[0]
    assert e0.get("jobTitle") == "GEOTECHNICAL ENGINEERING MANAGER"
    assert e0.get("employer") == "ECS Limited"
    assert e0.get("city") == "Schererville, IN"
    assert e0.get("startDate") is not None
    assert e0.get("isCurrent") is True
    e1 = exp[1]
    assert "GEOTECHNICAL ENGINEER" in (e1.get("jobTitle") or "")
    assert e1.get("employer") == "Milhaus Development LLC"
    assert e1.get("city") == "Hammond, IN"


def test_experience_title_dash_company_with_dates_on_same_line():
    text = normalize_text(
        """
        Experience
        Backend Developer – JobSpring
        January 2025 – March 2025
        • Built RESTful APIs for an AI-powered Interview Coach
        • Deployed services on Azure with Docker
        """
    )
    sections = split_sections(text)
    exp = parse_experience(sections.get("experience", ""))
    assert len(exp) >= 1
    e0 = exp[0]
    assert e0.get("jobTitle") == "Backend Developer"
    assert e0.get("employer") == "JobSpring"
    assert e0.get("startDate") is not None
    assert e0.get("endDate") is not None
    assert "RESTful" in (e0.get("description") or "")
