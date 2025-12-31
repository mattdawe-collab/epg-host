import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GEMINI_API_KEY not found in .env")
    return genai.Client(api_key=api_key)

def get_best_match(target_name, candidates):
    """
    Selects the best match from a provided list of options.
    Enforces Strict Region Matching (US -> US, CA -> CA).
    """
    try:
        client = get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        
        # We detect the region of the input channel to guide the AI
        target_region = "GLOBAL"
        if "US|" in target_name: target_region = "USA"
        elif "CA|" in target_name: target_region = "CANADA"
        elif "UK|" in target_name: target_region = "UK"

        prompt = f"""
        Act as a Broadcast Engineer. Map the SOURCE channel to the correct EPG ID.

        SOURCE: "{target_name}"
        TARGET REGION: {target_region}

        RULES:
        1. REGION LOCK: If Source is USA, you MUST prefer IDs ending in '.us', '.us_locals', or '.com'. Avoid '.ca' or '.uk' unless it is the ONLY option.
        2. IF Source is CANADA, prefer '.ca'.
        3. AVOID GENERIC IDs: Avoid numeric IDs (like '5e7cf...') if a named ID (like 'AMC.us') is available.
        4. EXACT CONTENT: 'Discovery' is NOT 'Discovery Science'. 'AMC' is NOT 'AMC Plus'.

        OPTIONS: 
        {json.dumps(candidates, indent=2)}

        RETURN JSON: {{ "match_found": true/false, "selected_id": "string_id" }}
        """
        
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        result = json.loads(response.text)
        
        if result.get("match_found") and result.get("selected_id") in candidates.values():
            return result["selected_id"]
    except Exception as e:
        print(f"AI Error: {e}")
        return None
    return None

def brainstorm_ids(channel_name):
    """
    Asks AI to guess the ID when no options are known.
    """
    try:
        client = get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        prompt = f"""
        Act as a Broadcast Engineer. I have a channel named "{channel_name}" missing from my EPG.
        Return a JSON list of likely EPG IDs or Call Signs.
        Focus on standard US/Canada format (e.g. "CNN.us", "CBC.ca").
        RETURN ONLY A JSON LIST OF STRINGS.
        """
        
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception:
        return []