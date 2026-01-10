import json
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION (DYNAMIC PATHS) ---
load_dotenv()

# 1. Find where this script file is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Go up one level to find the project root
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# 3. Build paths relative to the Project Root
INPUT_FILE = os.path.join(PROJECT_ROOT, "logs", "high_priority_hunt.txt")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "suggested_matches.json")
KNOWN_MATCHES = os.path.join(PROJECT_ROOT, "data", "known_matches.json")

BATCH_SIZE = 20

# Gemini Setup
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    exit(1)

genai.configure(api_key=api_key)

try:
    # UPDATED: Using the Gemini 3 Flash Preview model as requested
    model = genai.GenerativeModel("gemini-3-flash-preview")
except Exception as e:
    print(f"Error initializing model: {e}")
    exit(1)

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def hunt_batch(batch_channels, existing_suggestions):
    # Double check we haven't already suggested these in this session
    to_ask = [c for c in batch_channels if c not in existing_suggestions]
    if not to_ask:
        return {}

    # --- PROMPT: Aggressive on Local/City matches ---
    prompt = f"""
    I have a list of TV channel identifiers from an IPTV playlist. 
    Map each one to the most likely standard XMLTV ID.

    CRITICAL RULES FOR LOCALS:
    1. IF A CITY IS LISTED, FIND THE SPECIFIC STATION CALLSIGN.
       - "CBC Fredericton" -> "CBAT.ca" (NOT CBC.ca)
       - "CTV Calgary" -> "CFCN.ca" (NOT CTV.ca)
       - "ABC New York" -> "WABC.us" (NOT ABC.us)
       - "NBC Los Angeles" -> "KNBC.us"
    2. Only use the generic National feed (e.g., "CBC.ca", "Global.ca") if NO city is mentioned.
    3. Ignore decorations like "#####", "| US |", "FHD", "HEVC".
    4. Return ONLY valid JSON: {{ "Input Name": "xmltv.id" }}

    Channels to map:
    {json.dumps(to_ask)}
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"  [!] Batch failed. Error: {e}")
        return {}

def main():
    print(f"--- PATH DEBUG ---")
    print(f"Script Location: {SCRIPT_DIR}")
    print(f"Project Root:    {PROJECT_ROOT}")
    print(f"Looking for input at: {INPUT_FILE}")
    print("-" * 50)

    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at: {INPUT_FILE}")
        return

    # Load all raw channels
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        all_channels = [line.strip() for line in f if line.strip()]

    # Load history
    suggestions = load_json(OUTPUT_FILE)
    known = load_json(KNOWN_MATCHES)
    
    # --- SMART FILTER LOGIC ---
    count_total = len(all_channels)
    count_known = 0
    count_suggested = 0
    work_list = []

    # Check each channel against BOTH history files
    for c in all_channels:
        if c in known:
            count_known += 1
            continue
        if c in suggestions:
            count_suggested += 1
            continue
        work_list.append(c)
    
    print(f"Total Input Channels:      {count_total}")
    print(f"Skipped (Already Known):   {count_known}")
    print(f"Skipped (Already In File): {count_suggested}")
    print(f"-------------------------------------------")
    print(f"ACTUAL NEW WORK REMAINING: {len(work_list)}")
    print(f"-------------------------------------------")

    if not work_list:
        print("Nothing new to hunt! Great job.")
        return

    # Process in batches
    for i in range(0, len(work_list), BATCH_SIZE):
        batch = work_list[i : i + BATCH_SIZE]
        print(f"\nHunting Batch {i//BATCH_SIZE + 1} ({len(batch)} channels)...")
        
        new_matches = hunt_batch(batch, suggestions)
        
        if new_matches:
            suggestions.update(new_matches)
            save_json(OUTPUT_FILE, suggestions)
            
            print(f"  + Found {len(new_matches)} matches:")
            for channel, xmlid in new_matches.items():
                print(f"    - {channel}  ->  {xmlid}") 

        else:
            print("  - No matches found in this batch.")
        
        # Polite delay
        time.sleep(1)

    print(f"\nDone! Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()