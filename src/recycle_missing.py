import os
import json
import requests
import gzip
import time
from lxml import etree
from dotenv import load_dotenv
import ai_client
import gc

load_dotenv()

MISSING_LOG = "./logs/missing_channels.txt"
KNOWN_MATCHES_FILE = "./data/known_matches.json"
CACHE_DIR = "./data/cache"

JUNK_KEYWORDS = [
    "backup", "raw", "hevc", "vip", "feed", "event", "ppv", 
    "24/7", "loop", "uncut", "rec", "replay", "vod", 
    "pluto", "samsung", "rakuten", "plex", "section", "---"
]

BROAD_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://i.mjh.nz/PlutoTV/us.xml.gz",
    # ADDED: EPGHub Canada
    "https://epghub.xyz/epg/EPG-CA.xml.gz"
]

def clean_line_data(line):
    if not line or any(k in line.lower() for k in JUNK_KEYWORDS): return None
    if "|" in line:
        parts = line.split("|")
        return parts[1].strip() if len(parts) >= 3 else parts[0].strip()
    return line.strip()

def load_broad_database():
    os.makedirs(CACHE_DIR, exist_ok=True)
    master_index = {} 
    print(f"\n[*] Loading Broader Database...")
    
    for url in BROAD_SOURCES:
        filename = url.split("/")[-1]
        local_path = os.path.join(CACHE_DIR, filename)
        
        if not os.path.exists(local_path):
            try:
                print(f"    - Downloading {filename}...")
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(local_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
            except: continue

        try:
            with gzip.open(local_path, 'rb') as gz:
                context = etree.iterparse(gz, events=("end",), tag="channel")
                for event, elem in context:
                    xml_id = elem.get("id")
                    dn = elem.find("display-name")
                    if xml_id and dn is not None and dn.text:
                        master_index[dn.text.strip().upper()] = xml_id
                    elem.clear()
                    while elem.getprevious() is not None: del elem.getparent()[0]
                del context
                gc.collect()
        except: pass
    return master_index

def main():
    if not os.path.exists(MISSING_LOG): return

    print("[*] Sanitizing Log File...")
    valid_targets = []
    with open(MISSING_LOG, 'r', encoding='utf-8') as f:
        for line in f:
            clean = clean_line_data(line)
            if clean: valid_targets.append(clean)

    known = {}
    if os.path.exists(KNOWN_MATCHES_FILE):
        with open(KNOWN_MATCHES_FILE, 'r') as f: known = json.load(f)

    to_process = list(set([t for t in valid_targets if t not in known]))
    print(f"[*] Recycling {len(to_process)} unique channels.")

    db = load_broad_database()
    new_finds = 0
    
    for i, name in enumerate(to_process):
        print(f"\n[{i+1}/{len(to_process)}] Thinking: {name}")
        
        aliases = ai_client.brainstorm_ids(name)
        found_id = None
        
        if aliases:
            print(f"    -> Suggestions: {aliases}")
            for alias in aliases:
                key = alias.upper()
                if key in db:
                    found_id = db[key]
                    break
                for s in [" DT", " HD", "-EAST", " US", " CA"]:
                    if (key + s) in db:
                        found_id = db[key+s]
                        break
                if found_id: break

        if found_id:
            print(f"    -> MATCH! {found_id}")
            known[name] = found_id 
            new_finds += 1
            with open(KNOWN_MATCHES_FILE, 'w') as f: json.dump(known, f, indent=4)
        else:
            print("    -> No match in database.")
            
        time.sleep(1.0)

    print(f"[*] Recycle Complete. Rescued {new_finds} channels.")

if __name__ == "__main__":
    main()