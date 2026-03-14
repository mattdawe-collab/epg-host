import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Singleton client - initialized once, reused across all calls
_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL: GEMINI_API_KEY not found in .env")
        _client = genai.Client(api_key=api_key)
    return _client

def match_channel(target_name, candidates):
    """
    MAIN FUNCTION: Selects the best EPG match from provided candidates.
    Enforces strict region matching (US -> .us, CA -> .ca).
    """
    return get_best_match(target_name, candidates)

def get_best_match(target_name, candidates):
    """
    Core matching logic with Gemini AI.
    Enhanced for Canadian channel detection.
    """
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # Detect region from input
    target_region = "GLOBAL"
    if " US|" in target_name or "|US|" in target_name:
        target_region = "USA"
    elif " CA|" in target_name or "|CA|" in target_name:
        target_region = "CANADA"
    elif " UK|" in target_name or "|UK|" in target_name:
        target_region = "UK"

    # Extract network hints for Canadian channels
    network_hints = ""
    if "CBC" in target_name.upper():
        network_hints = "\n- CBC channels should map to CBC*.ca IDs"
    elif "SPORTSNET" in target_name.upper():
        network_hints = "\n- Sportsnet channels should map to Sportsnet*.ca IDs"
    elif "CTV" in target_name.upper():
        network_hints = "\n- CTV channels should map to CTV*.ca IDs"
    elif "GLOBAL" in target_name.upper():
        network_hints = "\n- Global channels should map to Global*.ca IDs"

    prompt = f"""
Act as a Broadcast Engineer. Map the SOURCE channel to the correct EPG ID.

SOURCE: "{target_name}"
TARGET REGION: {target_region}

CRITICAL RULES:
1. **REGION LOCK**:
   - If SOURCE contains "| US|" → MUST prefer IDs ending in '.us' or '.com'
   - If SOURCE contains "| CA|" → MUST prefer IDs ending in '.ca'
   - If SOURCE contains "| UK|" → MUST prefer IDs ending in '.uk'

2. **SUBCHANNEL AWARENESS**:
   - "WCIV.2" or "(D2)" in source → Prefer subchannel IDs (e.g., WCIV2.us)
   - Primary channel callsigns map to primary IDs (e.g., WCIV.us)

3. **NETWORK MATCHING**:
   - "FOX" source → FOX affiliate ID, NOT CBS/NBC/ABC
   - "ABC" source → ABC affiliate ID, NOT FOX/CBS/NBC
   - "CBS" source → CBS affiliate ID, NOT FOX/NBC/ABC{network_hints}

4. **AVOID GENERIC IDs**:
   - Prefer named IDs: "AMC.us" over "5e7cf123..."
   - Prefer network-specific: "DiscoveryChannel.us" over "Discovery.us"

5. **EXACT CONTENT MATCH**:
   - "Discovery" ≠ "Discovery Science"
   - "AMC" ≠ "AMC Plus"
   - "Sportsnet Ontario" ≠ "Sportsnet West"

OPTIONS:
{json.dumps(candidates, indent=2)}

RESPOND ONLY WITH JSON:
{{
  "match_found": true,
  "selected_id": "ExactID.domain",
  "confidence": "high|medium|low",
  "reasoning": "Brief explanation"
}}

If NO valid match exists, return:
{{
  "match_found": false,
  "selected_id": null,
  "reasoning": "Why no match"
}}
"""

    # Retry with exponential backoff for transient failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )

            result = json.loads(response.text)

            # Validate the AI's choice
            if result.get("match_found") and result.get("selected_id"):
                selected = result["selected_id"]

                if selected in candidates.values():
                    confidence = result.get("confidence", "unknown")
                    reasoning = result.get("reasoning", "No reason given")
                    print(f"  ✓ AI Match: {selected} [{confidence}] - {reasoning}")
                    return selected
                else:
                    print(f"  ✗ AI returned invalid ID: {selected}")
                    return None
            else:
                reasoning = result.get("reasoning", "No match found")
                print(f"  ○ AI skipped: {reasoning}")
                return None

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ✗ AI bad response: {e}")
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  ⟳ AI retry {attempt + 1}/{max_retries} in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  ✗ AI Error (after {max_retries} attempts): {e}")
                return None
    return None

def brainstorm_ids(channel_name):
    """
    Asks AI to guess likely EPG IDs when no candidates exist.
    Used for discovery/debugging.
    """
    try:
        client = get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

        # Detect region
        region_hint = ""
        if " CA|" in channel_name or "|CA|" in channel_name:
            region_hint = "Focus on Canadian (.ca) IDs."
        elif " US|" in channel_name or "|US|" in channel_name:
            region_hint = "Focus on US (.us) IDs."

        prompt = f"""
Act as a Broadcast Engineer. Suggest likely EPG IDs for this channel:

CHANNEL: "{channel_name}"
{region_hint}

Return a JSON array of 3-5 most likely EPG ID formats.

EXAMPLES:
- For "CBC Toronto | CA|" → ["CBCToronto.ca", "CBLT.ca", "CBC.ca"]
- For "Sportsnet Ontario | CA|" → ["SportsnetOntario.ca", "SN360.ca"]
- For "CNN HD | US|" → ["CNN.us", "CNNHDEast.us"]

RETURN ONLY JSON ARRAY OF STRINGS.
"""
        
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        suggestions = json.loads(response.text)
        if isinstance(suggestions, list):
            return suggestions
        return []
        
    except Exception as e:
        print(f"Brainstorm error: {e}")
        return []

# Legacy alias for backward compatibility
def get_match(target_name, candidates):
    """Deprecated: Use match_channel() instead."""
    return get_best_match(target_name, candidates)