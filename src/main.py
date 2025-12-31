import os
import json
import requests
import gzip
from lxml import etree
from fuzzywuzzy import process
from tqdm import tqdm
from dotenv import load_dotenv
import ai_client  # Ensure this matches your ai_client.py file

load_dotenv()

# --- CONFIG ---
XC_URL = os.getenv("XC_URL")
XC_USER = os.getenv("XC_USERNAME")
XC_PASS = os.getenv("XC_PASSWORD")
OUTPUT_FILE = os.getenv("OUTPUT_PATH", "./data/epg_repair.xml")
KNOWN_MATCHES_FILE = "./data/known_matches.json"
MISSING_LOG = "./logs/missing_channels.txt"
CACHE_DIR = "./data/cache"
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
    if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
    
    for url, filename in REFERENCE_SOURCES:
        path = os.path.join(CACHE_DIR, filename)
        try:
            print(f"[*] Fetching {filename}...")
            r = requests.get(url, stream=True)
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            with gzip.open(path, 'rb') as f:
                # Using iterative parsing to save memory on large XMLs
                context = etree.iterparse(f, events=('end',), tag='channel')
                for event, elem in context:
                    channel_id = elem.get('id')
                    for display_name in elem.findall('display-name'):
                        if display_name.text:
                            master_map[display_name.text.strip()] = channel_id
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    return master_map

def main():
    playlist = fetch_playlist()
    if not playlist: return

    # Load Databases
    known_matches = {}
    if os.path.exists(KNOWN_MATCHES_FILE):
        with open(KNOWN_MATCHES_FILE, 'r', encoding='utf-8') as f:
            known_matches = json.load(f)

    known_missing = set()
    if os.path.exists(MISSING_LOG):
        with open(MISSING_LOG, 'r', encoding='utf-8') as f:
            known_missing = {line.strip() for line in f if line.strip()}

    reference_data = fetch_reference_data()
    ref_names = list(reference_data.keys())

    # Build filtered target list (NA and UK only)
    target_playlist = [
        ch for ch in playlist 
        if any(cat in ch.get('name', '') for cat in PRIORITY_CATEGORIES)
    ]

    final_matches = {}
    new_missing = []
    stats = {"known": 0, "auto": 0, "ai": 0, "skipped": 0, "stale": 0}

    pbar = tqdm(target_playlist, unit="ch")
    for channel in pbar:
        name = channel.get('name', '').strip()
        
        # 1. VALIDATION: Check Known Matches
        if name in known_matches:
            target_id = known_matches[name]
            # Ensure the ID still exists in the fresh weekly source
            if target_id in reference_data.values():
                final_matches[name] = target_id
                stats["known"] += 1
                continue
            else:
                stats["stale"] += 1
                tqdm.write(f"⚠️  STALE ID: {name} ({target_id} not in source). Rematching...")
                del known_matches[name]

        # 2. ENERGY SAVER: Check Known Missing
        if name in known_missing:
            new_missing.append(name)
            stats["skipped"] += 1
            continue

        # 3. DISCOVERY: Fuzzy Match
        best_id = None
        # Limit fuzzy search to 5 candidates for AI to review
        matches = process.extract(name, ref_names, limit=5)
        top_match, top_score = matches[0]

        if top_score >= 98:
            best_id = reference_data[top_match]
            stats["auto"] += 1
        elif top_score > 35:
            # AI Consultation for edge cases (FanDuel, Locals, etc)
            pbar.set_description(f"AI Thinking: {name[:15]}")
            candidates = {m[0]: reference_data[m[0]] for m in matches}
            best_id = ai_client.get_best_match(name, candidates)
            if best_id:
                tqdm.write(f"✅ AI MATCH: [{name}] -> {best_id}")
                stats["ai"] += 1

        if best_id:
            final_matches[name] = best_id
            known_matches[name] = best_id
        else:
            new_missing.append(name)

    # --- SAVING & CLEANUP ---
    # Save Match Database
    with open(KNOWN_MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(known_matches, f, indent=4)

    # Save CLEAN Missing Log (No headers, sorted)
    clean_missing = sorted(list(set([
        m for m in new_missing 
        if any(reg in m for reg in PRIORITY_CATEGORIES) and not m.startswith("#")
    ])))
    with open(MISSING_LOG, 'w', encoding='utf-8') as f:
        f.write("\n".join(clean_missing))

    # Generate XMLTV
    root = etree.Element("tv")
    for ch_name, xml_id in final_matches.items():
        c_tag = etree.SubElement(root, "channel", id=xml_id)
        dn_tag = etree.SubElement(c_tag, "display-name")
        dn_tag.text = ch_name
    
    tree = etree.ElementTree(root)
    tree.write(OUTPUT_FILE, pretty_print=True, xml_declaration=True, encoding="utf-8")

    print(f"\n[!] Done! Found {len(final_matches)} matches. Logged {len(clean_missing)} misses.")
    print(f"Stats: Known={stats['known']}, Auto={stats['auto']}, AI={stats['ai']}, Stale_Fixed={stats['stale']}, Skipped={stats['skipped']}")

if __name__ == "__main__":
    main()