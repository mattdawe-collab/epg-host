import os
import json
from google import genai
from google.genai import types

def setup_gemini():
    """Checks for API key presence and prints active model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GEMINI_API_KEY not found in environment variables.")
    
    # We use the specific preview model ID you confirmed you have access to
    target_model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    print(f"[*] AI System Online. Target Engine: {target_model}")

def get_best_match(target_name, candidates):
    """
    Uses Gemini to strictly identify which candidate matches the target.
    Returns the exact ID string from the candidates list, or None.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    
    # Instantiate the modern client
    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are a TV Metadata Specialist Agent.
    
    GOAL: Map the 'Source Channel' to the correct 'Reference ID' from the provided options.
    
    SOURCE CHANNEL: "{target_name}"
    
    AVAILABLE OPTIONS (JSON):
    {json.dumps(candidates, indent=2)}
    
    RULES:
    - Exact matches (ignoring case) are best.
    - "US", "East", "West", "HD", "FHD" suffixes can be ignored if the core channel matches.
    - If multiple regional options exist (e.g. NBC East vs NBC West) and the Source doesn't specify, prefer 'East'.
    - If NO reliable match exists, return null.
    
    OUTPUT SCHEMA:
    {{
        "match_found": boolean,
        "selected_id": "string_id_from_options_or_null"
    }}
    """

    try:
        # Gemini 3.0 strict JSON call
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        # Parse the JSON response
        result = json.loads(response.text)
        
        if result.get("match_found") and result.get("selected_id"):
            # Double check the AI didn't hallucinate an ID not in our list
            if result["selected_id"] in candidates.values():
                return result["selected_id"]
                
        return None
        
    except Exception as e:
        # Gracefully handle quotas or server errors without crashing the main loop
        print(f" [!] AI Error on '{target_name}': {e}")
        return None