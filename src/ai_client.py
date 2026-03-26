import os
import json
import time
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Singleton client - initialized once, reused across all calls
_client = None
BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "15"))

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL: GEMINI_API_KEY not found in .env")
        _client = genai.Client(api_key=api_key)
    return _client


def _detect_region(name):
    """Detect region from channel name prefix."""
    if " US|" in name or "|US|" in name or name.startswith("US|"):
        return "USA"
    elif " CA|" in name or "|CA|" in name or name.startswith("CA|"):
        return "CANADA"
    elif " UK|" in name or "|UK|" in name or name.startswith("UK|"):
        return "UK"
    return "GLOBAL"


def match_channel(target_name, candidates):
    """
    Single-channel match (legacy wrapper).
    Calls batch internally with a single item.
    """
    results = match_batch([(target_name, candidates)])
    return results.get(target_name)


def match_batch(channel_candidate_pairs):
    """
    BATCH FUNCTION: Match multiple channels in a single AI call.

    Args:
        channel_candidate_pairs: list of (channel_name, candidate_dict) tuples

    Returns:
        dict of {channel_name: selected_id or None}
    """
    if not channel_candidate_pairs:
        return {}

    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # Build the batch prompt
    channels_block = []
    all_candidates = {}  # track valid IDs per channel for validation

    for idx, (name, candidates) in enumerate(channel_candidate_pairs):
        region = _detect_region(name)
        all_candidates[name] = set(candidates.values())

        # Build compact candidate list (name: id)
        opts = {k: v for k, v in candidates.items()}

        channels_block.append({
            "index": idx,
            "source": name,
            "region": region,
            "options": opts
        })

    prompt = f"""Act as a Broadcast Engineer. Map each SOURCE channel to the correct EPG ID from its OPTIONS.

CRITICAL RULES:
1. **REGION LOCK**:
   - USA region → MUST prefer IDs ending in '.us', '.us2', or '.com'
   - CANADA region → MUST prefer IDs ending in '.ca'
   - UK region → MUST prefer IDs ending in '.uk'

2. **SUBCHANNEL AWARENESS**:
   - "WCIV.2" or "(D2)" in source → Prefer subchannel IDs (e.g., WCIV2.us)
   - Primary channel callsigns map to primary IDs (e.g., WCIV.us)

3. **NETWORK MATCHING**:
   - "FOX" source → FOX affiliate ID, NOT CBS/NBC/ABC
   - "ABC" source → ABC affiliate ID, NOT FOX/CBS/NBC
   - CBC/CTV/Global/Sportsnet → prefer matching Canadian network IDs

4. **AVOID GENERIC IDs**:
   - Prefer named IDs: "AMC.us" over "5e7cf123..."
   - Prefer network-specific: "DiscoveryChannel.us" over "Discovery.us"

5. **EXACT CONTENT MATCH**:
   - "Discovery" ≠ "Discovery Science"
   - "AMC" ≠ "AMC Plus"
   - "Sportsnet Ontario" ≠ "Sportsnet West"
   - "West"/"Pacific" feeds are equivalent for US channels

6. **WEST/PACIFIC FEEDS**:
   - In US broadcasting, "West" = "Pacific" time zone feed
   - "TNT WEST" should match "TNT HD (Pacific)"

CHANNELS TO MATCH:
{json.dumps(channels_block, indent=1)}

RESPOND WITH A JSON ARRAY, one result per channel in order:
[
  {{"index": 0, "match_found": true, "selected_id": "ExactID.domain"}},
  {{"index": 1, "match_found": false, "selected_id": null}}
]

Return ONLY the JSON array."""

    # Retry with exponential backoff
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

            results_list = json.loads(response.text)

            # Handle if Gemini wraps it in an object
            if isinstance(results_list, dict) and "results" in results_list:
                results_list = results_list["results"]
            if not isinstance(results_list, list):
                results_list = [results_list]

            # Process results
            output = {}
            for result in results_list:
                idx = result.get("index", -1)
                if idx < 0 or idx >= len(channel_candidate_pairs):
                    continue

                name = channel_candidate_pairs[idx][0]

                if result.get("match_found") and result.get("selected_id"):
                    selected = result["selected_id"]
                    valid_ids = all_candidates.get(name, set())

                    if selected in valid_ids:
                        print(f"  [OK] {name[:40]:<40} → {selected}")
                        output[name] = selected
                    else:
                        print(f"  [FAIL] {name[:40]:<40} → Invalid ID: {selected}")
                        output[name] = None
                else:
                    print(f"  [SKIP] {name[:40]:<40} → no match")
                    output[name] = None

            # Fill in any channels the AI missed in its response
            for name, _ in channel_candidate_pairs:
                if name not in output:
                    print(f"  [MISS] {name[:40]:<40} → AI did not return a result")
                    output[name] = None

            return output

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [FAIL] AI bad response: {e}")
            # Return all None
            return {name: None for name, _ in channel_candidate_pairs}
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [RETRY] Batch retry {attempt + 1}/{max_retries} in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  [FAIL] AI Error (after {max_retries} attempts): {e}")
                return {name: None for name, _ in channel_candidate_pairs}

    return {name: None for name, _ in channel_candidate_pairs}


def brainstorm_ids(channel_name):
    """
    Asks AI to guess likely EPG IDs when no candidates exist.
    Used for discovery/debugging.
    """
    try:
        client = get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

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
    return match_channel(target_name, candidates)
