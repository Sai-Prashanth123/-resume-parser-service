
import re

def extract_personal(text):
    lines = [l for l in text.splitlines() if l.strip()]
    name = lines[0].split() if lines else []
    email = re.search(r"[\w.-]+@[\w.-]+", text)
    phone = re.search(r"(\+?\d[\d\s()-]{7,})", text)

    return {
        "firstName": name[0] if len(name) > 1 else None,
        "lastName": name[-1] if len(name) > 1 else None,
        "email": email.group(0) if email else None,
        "phone": phone.group(0) if phone else None
    }
