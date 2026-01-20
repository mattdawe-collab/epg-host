import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION (DYNAMIC PATHS) ---
load_dotenv()

# 1. Find where this script file is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Go up one level to find the project root
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# 3. Build paths relative to the Project Root
SUGGESTIONS_FILE = os.path.join(PROJECT_ROOT, "suggested_matches.json")
REPORT_FILE = os.path.join(PROJECT_ROOT, "audit_report.md")

# Gemini Setup
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: API Key not found.")
    exit(1)

genai.configure(api_key=api_key)

try:
    # UPDATED: Using Gemini 3 Flash Preview
    model = genai.GenerativeModel("gemini-3-flash-preview")
except Exception as e:
    print(f"Error initializing model: {e}")
    exit(1)

def audit_batch(batch_items):
    # We send the Input->Output pairs and ask the model to CRITIQUE them
    prompt = f"""
    You are a strict TV Database QA Auditor. 
    Review the following "Input Channel Name" to "Mapped XMLID" pairs.

    YOUR GOAL: Flag matches that seem incorrect, lazy, or generic.

    CRITERIA TO FLAG:
    1. NETWORK MISMATCH: (e.g., "ABC East" mapped to "NBC.us")
    2. MISSED LOCALIZATION: (e.g., "CTV Calgary" mapped to "CTV.ca" generic, instead of specific "CFCN" or similar callsign).
    3. BAD FORMAT: XMLID looks like junk or completely unrelated text.

    If a match looks 99% correct, IGNORE IT. Only output the suspicious ones.

    INPUT DATA:
    {json.dumps(batch_items, indent=2)}

    OUTPUT FORMAT (Markdown Table rows only):
    | Input Name | Current Match | Reason for Flag |
    """

    try:
        response = model.generate_content(prompt)
        # Clean up response to just get the table rows
        lines = response.text.strip().split('\n')
        # Filter for lines that look like pipe tables
        table_rows = [line for line in lines if "|" in line and "---" not in line and "Input Name" not in line]
        return table_rows
    except Exception as e:
        print(f"Error auditing batch: {e}")
        return []

def main():
    print(f"--- PATH DEBUG ---")
    print(f"Script Location: {SCRIPT_DIR}")
    print(f"Reading suggestions from: {SUGGESTIONS_FILE}")
    print("-" * 50)

    if not os.path.exists(SUGGESTIONS_FILE):
        print(f"No suggestions found at {SUGGESTIONS_FILE}")
        return

    with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        print("Suggestions file is empty.")
        return

    print(f"Auditing {len(data)} matches...")
    
    # Header for the report
    report_lines = [
        "# Match Audit Report",
        f"**Total Reviewed:** {len(data)}",
        "",
        "| Input Name | Current Match | Reason for Flag |",
        "|---|---|---|"
    ]

    # Process in batches of 30
    items = list(data.items())
    batch_size = 30
    flag_count = 0

    for i in range(0, len(items), batch_size):
        batch = dict(items[i : i + batch_size])
        print(f"  - Auditing batch {i//batch_size + 1}...")
        
        flags = audit_batch(batch)
        if flags:
            report_lines.extend(flags)
            flag_count += len(flags)

    # Save Report
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    print("-" * 50)
    print(f"Audit Complete.")
    print(f"Flagged {flag_count} suspicious matches.")
    print(f"Report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()