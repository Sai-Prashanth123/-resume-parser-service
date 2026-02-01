
import re

def extract_personal(text):
    """
    Flexible personal details parser.
    Extracts name, email, phone from resume.
    Leaves address/city/country empty (too error-prone).
    """
    if not text:
        return {
            "firstName": None,
            "lastName": None,
            "email": None,
            "phoneNumber": None,
            "address": None,
            "city": None,
            "country": None
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
    
    # Don't extract address/city/country - too error-prone with various resume formats
    # These fields will be left empty for manual entry
    
    return {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phoneNumber": phone_number,
        "address": None,
        "city": None,
        "country": None
    }
