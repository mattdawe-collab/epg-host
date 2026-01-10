import os
import json
import requests
import gzip
from lxml import etree
from fuzzywuzzy import process
from tqdm import tqdm
from dotenv import load_dotenv
import ai_client 

load_dotenv()

# --- DYNAMIC PATH CONFIG ---
# Get the directory where this script lives (e.g., Z:\AI_EPG_Bridge\src)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to get the project root (e.g., Z:\AI_EPG_Bridge)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

XC_URL = os.getenv("XC_URL")
XC_USER = os.getenv("XC_USERNAME")
XC_PASS = os.getenv("XC_PASSWORD")

# Use os.path.join with PROJECT_ROOT to ensure we hit the correct folders
OUTPUT_BASE = os.getenv("OUTPUT_PATH", os.path.join(PROJECT_ROOT, "data", "epg_repair.xml"))
KNOWN_MATCHES_FILE = os.path.join(PROJECT_ROOT, "data", "known_matches.json")
SUGGESTED_MATCHES_FILE = os.path.join(PROJECT_ROOT, "suggested_matches.json")
MISSING_LOG = os.path.join(PROJECT_ROOT, "logs", "missing_channels.txt")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "cache")

PRIORITY_CATEGORIES = ["US|", "CA|", "UK|"]

# --- SOURCES ---
REFERENCE_SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", "all_sources.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz", "us_locals.xml.gz"),
    ("https://epghub.xyz/epg/EPG-CA.xml.gz", "epg_canada.xml.gz")
]

def fetch_playlist():
    url = f"{XC_URL}/player_api.php?username={XC_USER}&password={XC_PASS}&action=get_live_streams"
    try:
        response = requests.get(url, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Error fetching playlist: {e}")
        return []

def fetch_reference_data():
    """Downloads and parses EPG sources into a name:id map."""
    master_map = {}
    valid_ids = set()
    
    # Ensure cache directory exists
    if not os.path.exists(CACHE_DIR): 
        os.makedirs(CACHE_DIR)
    
    for url, filename in REFERENCE_SOURCES:
        path = os.path.join(CACHE_DIR, filename)
        try:
            print(f"[*] Fetching fresh data for {filename}...")
            r = requests.get(url, stream=True)
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            with gzip.open(path, 'rb') as f:
                context = etree.iterparse(f, events=('end',), tag='channel')
                for event, elem in context:
                    channel_id = elem.get('id')
                    valid_ids.add(channel_id)
                    
                    for display_name in elem.findall('display-name'):
                        if display_name.text:
                            master_map[display_name.text.strip()] = channel_id
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    
    return master_map, valid_ids

def main():
    playlist = fetch_playlist()
    if not playlist: return

    # 1. Load Databases
    known_matches = {}
    if os.path.exists(KNOWN_MATCHES_FILE):
        with open(KNOWN_MATCHES_FILE, 'r', encoding='utf-8') as f:
            known_matches = json.load(f)

    # --- Ingest AI Suggestions ---
    if os.path.exists(SUGGESTED_MATCHES_FILE):
        print(f"[*] merging AI suggestions from {SUGGESTED_MATCHES_FILE}...")
        try:
            with open(SUGGESTED_MATCHES_FILE, 'r', encoding='utf-8') as f:
                suggestions = json.load(f)
                known_matches.update(suggestions)
        except:
            pass 

    known_missing = set()
    if os.path.exists(MISSING_LOG):
        with open(MISSING_LOG, 'r', encoding='utf-8') as f:
            known_missing = {line.strip() for line in f if line.strip()}

    reference_data, valid_ids = fetch_reference_data()
    ref_names = list(reference_data.keys())

    target_playlist = [
        ch for ch in playlist 
        if any(cat in ch.get('name', '') for cat in PRIORITY_CATEGORIES)
    ]

    final_matches = {}
    new_missing = []
    stats = {"known": 0, "auto": 0, "ai": 0, "skipped": 0, "stale": 0, "fixed": 0}

    print(f"Processing {len(target_playlist)} channels...")
    pbar = tqdm(target_playlist, unit="ch")
    
    for channel in pbar:
        name = channel.get('name', '').strip()
        
        # 2. VALIDATION
        if name in known_matches:
            target_id = known_matches[name]
            if target_id in valid_ids:
                final_matches[name] = target_id
                stats["known"] += 1
                continue
            else:
                stats["stale"] += 1
                del known_matches[name]

        # 3. ENERGY SAVER
        if name in known_missing:
            new_missing.append(name)
            stats["skipped"] += 1
            continue

        # 4. DISCOVERY
        best_id = None
        matches = process.extract(name, ref_names, limit=5)
        top_match, top_score = matches[0]

        if top_score >= 95:
            best_id = reference_data[top_match]
            stats["auto"] += 1
        
        if best_id:
            final_matches[name] = best_id
            known_matches[name] = best_id
            stats["fixed"] += 1
        else:
            new_missing.append(name)

    # --- SAVING & CLEANUP ---
    # Ensure data directory exists for known_matches
    if not os.path.exists(os.path.dirname(KNOWN_MATCHES_FILE)):
        os.makedirs(os.path.dirname(KNOWN_MATCHES_FILE))

    with open(KNOWN_MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(known_matches, f, indent=4)

    if os.path.exists(SUGGESTED_MATCHES_FILE):
        with open(SUGGESTED_MATCHES_FILE, 'w') as f:
            json.dump({}, f)

    clean_missing = sorted(list(set([
        m for m in new_missing 
        if any(reg in m for reg in PRIORITY_CATEGORIES) and not m.startswith("#")
    ])))
    
    # --- CRITICAL FIX: Ensure logs directory exists ---
    log_dir = os.path.dirname(MISSING_LOG)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    with open(MISSING_LOG, 'w', encoding='utf-8') as f:
        f.write("\n".join(clean_missing))

    # --- SUPER EPG GENERATION (Compressed) ---
    print(f"\n[*] Generating Super EPG with program data...")
    
    base_name = os.path.splitext(OUTPUT_BASE)[0]
    OUTPUT_GZ = base_name + ".xml.gz"
    
    # Ensure output directory exists
    if not os.path.exists(os.path.dirname(OUTPUT_GZ)):
        os.makedirs(os.path.dirname(OUTPUT_GZ))
    
    valid_xml_ids = set(final_matches.values())

    with gzip.open(OUTPUT_GZ, 'wb') as f:
        with etree.xmlfile(f, encoding='utf-8') as xf:
            with xf.element('tv'):
                for ch_name, xml_id in final_matches.items():
                    ch_elem = etree.Element('channel', id=xml_id)
                    dn = etree.SubElement(ch_elem, 'display-name')
                    dn.text = ch_name
                    xf.write(ch_elem)
                
                for url, filename in REFERENCE_SOURCES:
                    path = os.path.join(CACHE_DIR, filename)
                    try:
                        print(f"    - Merging schedule from {filename}...")
                        with gzip.open(path, 'rb') as source_f:
                            context = etree.iterparse(source_f, events=('end',), tag='programme')
                            for event, elem in context:
                                if elem.get('channel') in valid_xml_ids:
                                    xf.write(elem)
                                elem.clear()
                                while elem.getprevious() is not None:
                                    del elem.getparent()[0]
                    except Exception as e:
                        print(f"Error merging {filename}: {e}")

    print(f"\n[!] Done! Super EPG saved to {OUTPUT_GZ}")
    print(f"Stats: Known={stats['known']}, Auto={stats['auto']}, Stale_Dropped={stats['stale']}")

if __name__ == "__main__":
    main()