import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from difflib import get_close_matches
import gzip
import io
import gc

# --- CONFIGURATION ---
MISSING_FILE = r'data/logs/priority_missing.txt'
OUTPUT_FILE = r'data/known_matches.json'

# THE WORKING SOURCE LIST
EXTERNAL_SOURCES = {
    # 1. THE MEGA DATABASE (Crucial: This contains US, UK, CA, and Locals all in one)
    "Mega_Database": "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",

    # 2. FAST CHANNELS (These cover the "Raw" and "Backup" channels often missing from the main list)
    "PlutoTV_US": "https://i.mjh.nz/PlutoTV/us.xml.gz",
    "SamsungTV_US": "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
    "Plex_US": "https://i.mjh.nz/Plex/us.xml.gz",
    
    # 3. OPEN-EPG (The replacement for Bevy - good backup for US/CA/UK)
    "OpenEPG_US": "https://www.open-epg.com/files/unitedstates1.xml.gz",
    "OpenEPG_UK": "https://www.open-epg.com/files/uk1.xml.gz",
    "OpenEPG_CA": "https://www.open-epg.com/files/canada1.xml.gz"
}

def clean_channel_name(name):
    """
    Transforms complex playlist names into simple matchable names.
    Example: 'US| VSIN | US| SPORTS NETWORK' -> 'VSIN'
    """
    # 1. Remove standard prefixes first
    remove_list = [
        "US|", "UK|", "CA|", "RO|", "DE|", "FR|", "IT|", "ES|",
        "#####", "FHD", "HD", "HEVC", "1080p", "Backup", "RAW", 
        "50fps", "60fps", "VIX+", "LOCALS", "NETWORK"
    ]
    clean = name.upper()
    for item in remove_list:
        clean = clean.replace(item, "")
    
    # 2. KEY FIX: Split by pipe '|' and take the first part
    # This removes the trailing category info found in your log file
    if "|" in clean:
        clean = clean.split("|")[0]

    # 3. Final cleanup of whitespace and punctuation
    return clean.strip(" -.")

def stream_and_hunt():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    missing_path = os.path.join(base_dir, "logs", "priority_missing.txt")
    output_path = os.path.join(base_dir, "data", "known_matches.json")

    if not os.path.exists(missing_path):
        print("Could not find priority_missing.txt.")
        return

    # --- STEP 1: LOAD TARGETS ---
    missing_map = {} 
    print("--- LOADING MISSING CHANNELS ---")
    with open(missing_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip headers and empty lines
            if line and "#####" not in line and "---" not in line:
                clean = clean_channel_name(line)
                if len(clean) > 1:
                    missing_map[clean] = line

    print(f"Loaded {len(missing_map)} unique missing targets to hunt for.")
    
    # --- STEP 2: STREAM SOURCES ---
    found_matches = {}
    
    for source_name, url in EXTERNAL_SOURCES.items():
        print(f"\nProcessing Source: {source_name}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                # Handle GZIP compression automatically
                with gzip.GzipFile(fileobj=response) as gz:
                    # iterparse streams the file element by element
                    context = ET.iterparse(gz, events=("end",))
                    
                    count = 0
                    local_matches = 0
                    
                    for event, elem in context:
                        if elem.tag == 'channel':
                            count += 1
                            
                            epg_id = elem.get('id')
                            display_name = elem.find('display-name')
                            
                            if display_name is not None and display_name.text and epg_id:
                                # Clean the EPG name to match our target format
                                epg_name_raw = display_name.text.strip().upper()
                                
                                # EXACT MATCH CHECK
                                if epg_name_raw in missing_map:
                                    original_name = missing_map[epg_name_raw]
                                    
                                    # Only add if we haven't found it yet
                                    if original_name not in found_matches:
                                        found_matches[original_name] = epg_id
                                        local_matches += 1
                                        print(f"  [MATCH] {original_name} -> {epg_id}")
                            
                            # FREE MEMORY (Crucial for large files)
                            elem.clear()
                            
                    print(f"  -> Scanned {count} channels. Found {local_matches} matches.")
                    del context # Force cleanup
                    gc.collect()

        except Exception as e:
            print(f"  -> Error reading {source_name}: {e}")

    # --- STEP 3: SAVE RESULTS ---
    print(f"\n==========================================")
    print(f"HUNT COMPLETE.")
    print(f"New Matches Found: {len(found_matches)}")
    
    # Load existing matches to merge
    existing = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    
    existing.update(found_matches)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=4)
        
    print(f"Total Database Size: {len(existing)}")
    print(f"Updated: {output_path}")
    print(f"==========================================")

if __name__ == "__main__":
    stream_and_hunt()