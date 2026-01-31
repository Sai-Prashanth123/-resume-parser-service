
def parse_education(text):
    blocks = text.split("\n\n")
    return [{"institution": b.split("\n")[0]} for b in blocks if b.strip()]
