
import os
import json
from groq import Groq

def parse_with_llm(text: str) -> dict:
    """
    Parse resume text using Groq LLM API for structured data extraction.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    client = Groq(api_key=api_key)
    
    prompt = f"""You are a professional resume parser. Extract ALL information from the resume text below and return ONLY valid JSON.

Resume Text:
{text}

IMPORTANT INSTRUCTIONS:
1. Extract EVERY detail accurately - names, dates, locations, descriptions
2. For dates: Use DD-MM-YYYY format (e.g., "15-06-2020")
3. For current positions: Use null for endDate and set isCurrentlyWorking to true
4. Extract complete job descriptions with bullet points and achievements
5. Identify all skills mentioned throughout the resume
6. Extract address components: street address, city, country separately
7. Find all social links (LinkedIn, GitHub, portfolio, etc.)
8. For skills, try to infer experience level based on context (Beginner/Intermediate/Advanced/Expert)

Return JSON with this EXACT structure:
{{
  "personalDetails": {{
    "firstName": "string (required)",
    "lastName": "string (required)",
    "email": "string (required)",
    "phoneNumber": "string (required)",
    "address": "string (full street address, P.O. Box, etc.)",
    "city": "string (required)",
    "country": "string (required)"
  }},
  "professionalSummary": "string (2-3 sentence summary of professional background and expertise)",
  "workExperience": [
    {{
      "jobTitle": "string (required - e.g., Senior Software Engineer)",
      "employer": "string (required - company name)",
      "startDate": "string (DD-MM-YYYY format, required)",
      "endDate": "string (DD-MM-YYYY format) or null if current",
      "isCurrentlyWorking": boolean,
      "city": "string (work location city)",
      "description": "string (detailed description with responsibilities and achievements, use bullet points with \\n)"
    }}
  ],
  "education": [
    {{
      "schoolName": "string (required - university/institution name)",
      "degree": "string (required - degree title, e.g., Bachelor of Science in Computer Science)",
      "startDate": "string (DD-MM-YYYY format)",
      "endDate": "string (DD-MM-YYYY format)",
      "city": "string (institution location)",
      "description": "string (relevant coursework, honors, GPA, activities)"
    }}
  ],
  "socialLinks": [
    {{
      "label": "string (e.g., LinkedIn, GitHub, Portfolio, Personal Website)",
      "url": "string (full URL starting with https://)"
    }}
  ],
  "skills": [
    {{
      "skillName": "string (required - e.g., Python, React, AWS)",
      "experienceLevel": "string (Beginner/Intermediate/Advanced/Expert based on context)"
    }}
  ]
}}

CRITICAL: 
- Extract at least 5-10 skills if available
- Include ALL work experiences from last 10 years
- Capture complete job descriptions with achievements
- Find and include ALL social media/professional links
- If information is missing, use null (not empty string)

Return ONLY the JSON, no markdown, no explanations."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Groq's fastest and most capable model
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise resume parser that extracts structured data and returns only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Ensure all required keys exist with defaults
        return {
            "personalDetails": result.get("personalDetails", {}),
            "professionalSummary": result.get("professionalSummary", ""),
            "workExperience": result.get("workExperience", []),
            "education": result.get("education", []),
            "socialLinks": result.get("socialLinks", []),
            "skills": result.get("skills", []),
            "meta": {
                "model": "llama-3.3-70b-versatile",
                "provider": "groq",
                "parsed": True
            }
        }
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise ValueError(f"LLM parsing failed: {str(e)}")
