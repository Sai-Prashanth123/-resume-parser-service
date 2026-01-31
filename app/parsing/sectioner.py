
HEADERS = ["experience","education","skills","projects"]

def split_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        low = line.lower().strip(": ")
        if low in HEADERS:
            current = low
            sections[current] = ""
        elif current:
            sections[current] += line + "\n"
    return sections
