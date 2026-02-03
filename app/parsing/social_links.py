
import re

def extract_social_links(text):
    links = []
    
    linkedin_pattern = r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+"
    linkedin_matches = re.findall(linkedin_pattern, text, re.I)
    for match in linkedin_matches:
        if not match.startswith('http'):
            match = 'https://' + match
        links.append({
            "label": "LinkedIn",
            "url": match
        })
    
    github_pattern = r"(?:https?://)?(?:www\.)?github\.com/[\w-]+"
    github_matches = re.findall(github_pattern, text, re.I)
    for match in github_matches:
        if not match.startswith('http'):
            match = 'https://' + match
        links.append({
            "label": "GitHub",
            "url": match
        })
    
    website_pattern = r"(?:https?://)?(?:www\.)?[\w-]+\.(?:com|net|org|io|dev|me|co)(?:/[\w-]*)*"
    website_matches = re.findall(website_pattern, text, re.I)
    for match in website_matches:
        if 'linkedin.com' in match.lower() or 'github.com' in match.lower():
            continue
        if any(domain in match.lower() for domain in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']):
            continue
        if not match.startswith('http'):
            match = 'https://' + match
        links.append({
            "label": "Portfolio",
            "url": match
        })
    
    twitter_pattern = r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[\w-]+"
    twitter_matches = re.findall(twitter_pattern, text, re.I)
    for match in twitter_matches:
        if not match.startswith('http'):
            match = 'https://' + match
        links.append({
            "label": "Twitter",
            "url": match
        })
    
    seen = set()
    unique_links = []
    for link in links:
        url_lower = link['url'].lower()
        if url_lower not in seen:
            seen.add(url_lower)
            unique_links.append(link)
    
    return unique_links
