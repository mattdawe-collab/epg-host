import os
import json
import requests
import gzip
import email.utils
from lxml import etree
from fuzzywuzzy import process, fuzz
from dotenv import load_dotenv
from tqdm import tqdm
import ai_client

load_dotenv()

# --- CONFIG ---
XC_URL = os.getenv("XC_URL")
XC_USER = os.getenv("XC_USERNAME")
XC_PASS = os.getenv("XC_PASSWORD")
OUTPUT_FILE = os.getenv("OUTPUT_PATH", "./data/epg_repair.xml")
OVERRIDES_FILE = "./custom_overrides.json"
KNOWN_MATCHES_FILE = "./data/known_matches.json"
MISSING_LOG = "./logs/missing_channels.txt"
CACHE_DIR = "./data/cache"

# --- SOURCES ---
REFERENCE_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://iptv-org.github.io/epg/xml/ca.xml",
    "https://iptv-org.github.io/epg/xml/us.xml",
    "https://iptv-org.github.io/epg/xml/uk.xml"
]

# --- 1. THE "KILL" LIST (Higher Priority) ---
# If a category matches ANY of these, it dies immediately.
FOREIGN_BLOCKLIST = [
    "AR|", "ARABIC", "UAE", "KSA",         # Arabic
    "FR|", "FRANCE", "BELGIUM",            # French
    "DE|", "GERMANY", "GERMAN",            # German
    "IT|", "ITALY",                        # Italian
    "RU|", "RUSSIA",                       # Russian
    "TR|", "TURKEY",                       # Turkish
    "ES|", "SPAIN", "SPANISH",             # Spanish (Euro)
    "PT|", "PORTUGAL",                     # Portuguese
    "PL|", "POLAND",                       # Polish
    "LAT|", "LATINO", "MX|", "MEXICO",     # Latin America
    "BR|", "BRAZIL",                       # Brazil
    "IN|", "INDIA", "HINDI", "PAK|",       # India/Pakistan
    "CN|", "CHINA",                        # China
    "VN|", "VIETNAM",                      # Vietnam
    "GR|", "GREECE",                       # Greece
    "AL|", "ALBANIA",                      # Albania
    "EX-YU", "BALKAN"                      # Balkans
]

# --- 2. THE JUNK LIST (Clean up the rest) ---
IGNORE_JUNK = [
    "24/7", "LOOP", "VOD", "RADIO", "ADULT", "XXX", "MUSIC VIDEO", 
    "RAW", "DIRECTORS CUT", "CINEMA", "PPV", "CHRISTMAS", "HALLOWEEN"
]

# --- 3. THE "KEEP" LIST (Lowest Priority) ---
TARGET_REGIONS = [
    "US|", "USA", "AMERICA",               # USA
    "CA|", "CAN", "CDN", "CANADA",         # Canada
    "UK|", "GB|", "BRITAIN", "KINGDOM",    # UK
    "EN|", "ENGLISH",                      # Generic English
    "NHL", "NFL", "NBA", "MLB", "SPORTS"   # Sports
]

def load_json_file(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_json_file(filepath, data):
    try:
        existing = load_json_file(filepath)
        existing.update(data)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        print(f"[!] Error saving {filepath}: {e}")

def get_xc_data():
    base_url = XC_URL.strip()
    if not base_url.startswith("http"):
        base_url = f"http://{base_url}"
    
    print(f"[*] Connecting to {base_url}...")
    try:
        c_resp = requests.get(f"{base_url}/player_api.php?username={XC_USER}&password={XC_PASS}&action=get_live_categories", timeout=15)
        c_map = {c['category_id']: c['category_name'] for c in c_resp.json()}
        
        s_resp = requests.get(f"{base_url}/player_api.php?username={XC_USER}&password={XC_PASS}&action=get_live_streams", timeout=45)
        
        filtered = []
        stats = {"active": 0, "junk": 0, "foreign": 0, "other": 0}
        
        print("[-] Applying Strict Region Filters...")
        for ch in tqdm(s_resp.json(), unit="ch"):
            cat_name = c_map.get(ch.get('category_id'), "Uncategorized").upper()
            
            # 1. Check Foreign Blocklist (KILL)
            if any(bad in cat_name for bad in FOREIGN_BLOCKLIST):
                stats["foreign"] += 1
                continue

            # 2. Check Junk Blocklist (KILL)
            if any(bad in cat_name for bad in IGNORE_JUNK):
                stats["junk"] += 1
                continue
                
            # 3. Check Target Whitelist (KEEP)
            if not any(good in cat_name for good in TARGET_REGIONS):
                stats["other"] += 1
                continue

            ch['category_name'] = cat_name
            filtered.append(ch)
            stats["active"] += 1
                
        print(f"[*] Filtering complete.")
        print(f"    - Active Channels: {stats['active']}")
        print(f"    - Blocked Foreign: {stats['foreign']} (Strict Mode)")
        print(f"    - Blocked Junk:    {stats['junk']}")
        return filtered
    except Exception as e:
        print(f"[!] Error fetching XC data: {e}")
        return []

def download_and_parse(url):
    filename = url.split('/')[-1]
    local_path = os.path.join(CACHE_DIR, filename)
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    headers = {}
    if os.path.exists(local_path):
        mtime = os.path.getmtime(local_path)
        headers['If-Modified-Since'] = email.utils.formatdate(mtime, usegmt=True)

    try:
        resp = requests.get(url, headers=headers, timeout=180, stream=True)
        content = None
        
        if resp.status_code == 304:
            with open(local_path, 'rb') as f:
                content = f.read()
        elif resp.status_code == 200:
            total_size = int(resp.headers.get('content-length', 0))
            with open(local_path, 'wb') as f, tqdm(desc=filename, total=total_size, unit='iB', unit_scale=True, unit_divisor=1024) as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    bar.update(size)
            with open(local_path, 'rb') as f:
                content = f.read()
        else:
            return {}

        if filename.endswith('.gz') or (content and content[:2] == b'\x1f\x8b'):
            try:
                content = gzip.decompress(content)
            except:
                pass 

        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(content, parser=parser)
        
        local_map = {}
        for channel in root.findall('channel'):
            dn = channel.find('display-name')
            if dn is not None and dn.text:
                local_map[dn.text] = channel.get('id')
        return local_map

    except Exception:
        return {}

def get_reference_data():
    master_map = {}
    print(f"[*] Building Database...")
    for url in REFERENCE_SOURCES:
        data = download_and_parse(url)
        master_map.update(data)
    print(f"[*] Database Ready. {len(master_map)} unique IDs.")
    return master_map

def main():
    ai_client.setup_gemini()
    my_channels = get_xc_data()
    ref_data = get_reference_data()
    manual_overrides = load_json_file(OVERRIDES_FILE)
    known_matches = load_json_file(KNOWN_MATCHES_FILE)
    
    if not my_channels or not ref_data:
        return

    ref_names = list(ref_data.keys())
    matches = {} 
    missing_list = []
    stats = {"known": 0, "auto": 0, "ai": 0, "manual": 0}

    print(f"[*] Starting Analysis on {len(my_channels)} channels...")
    pbar = tqdm(my_channels, unit="ch", desc="Matching", dynamic_ncols=True)
    
    for ch in pbar:
        name = ch.get('name', 'Unknown')
        cat = ch.get('category_name', 'Unknown')
        
        if name in known_matches:
            matches[name] = known_matches[name]
            stats["known"] += 1
            continue
            
        if name in manual_overrides:
            matches[name] = manual_overrides[name]
            stats["manual"] += 1
            continue

        best_candidates = process.extract(name, ref_names, limit=5, scorer=fuzz.token_sort_ratio)
        valid_candidates = [match[0] for match in best_candidates if match[1] > 60]

        if not valid_candidates:
            missing_list.append(f"{name} | {cat}")
            continue

        # Auto-Match 95%
        if best_candidates[0][1] >= 95:
            matches[name] = ref_data[best_candidates[0][0]]
            stats["auto"] += 1
            continue

        candidate_objs = { cn: ref_data[cn] for cn in valid_candidates }
        if name in matches:
            continue

        best_id = ai_client.get_best_match(name, candidate_objs)
        if best_id:
            tqdm.write(f"    [AI MATCH] {name} -> {best_id}")
            matches[name] = best_id
            stats["ai"] += 1
        else:
            missing_list.append(f"{name} | {cat}")

    if matches:
        root = etree.Element("tv")
        for name, xml_id in matches.items():
            c_tag = etree.SubElement(root, "channel", id=xml_id)
            dn_tag = etree.SubElement(c_tag, "display-name")
            dn_tag.text = name 
        tree = etree.ElementTree(root)
        try:
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
            tree.write(OUTPUT_FILE, encoding='utf-8', xml_declaration=True, pretty_print=True)
            save_json_file(KNOWN_MATCHES_FILE, matches)
            print(f"\n[*] SUCCESS: {len(matches)} channels processed.")
            print(f"    - From Memory: {stats['known']}")
            print(f"    - Auto Matched: {stats['auto']}")
            print(f"    - AI Matched: {stats['ai']}")
        except Exception as e:
            print(f"[!] Save Error: {e}")
            
    if missing_list:
        os.makedirs(os.path.dirname(MISSING_LOG), exist_ok=True)
        with open(MISSING_LOG, 'w', encoding='utf-8') as f:
            for item in missing_list: f.write(f"{item}\n")

if __name__ == "__main__":
    main()