import os
import sys
import json
import requests
import gzip
import re
from lxml import etree
from fuzzywuzzy import process
from tqdm import tqdm
from dotenv import load_dotenv
import ai_client
import epg_cache

load_dotenv()

# --- DYNAMIC PATH CONFIG ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

XC_URL = os.getenv("XC_URL")
XC_USER = os.getenv("XC_USERNAME")
XC_PASS = os.getenv("XC_PASSWORD")

OUTPUT_BASE = os.getenv("OUTPUT_PATH", os.path.join(PROJECT_ROOT, "data", "epg_repair.xml"))
KNOWN_MATCHES_FILE = os.path.join(PROJECT_ROOT, "data", "known_matches.json")
SUGGESTED_MATCHES_FILE = os.path.join(PROJECT_ROOT, "suggested_matches.json")
MISSING_LOG = os.path.join(PROJECT_ROOT, "logs", "missing_channels.txt")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "cache")

PRIORITY_PREFIXES = ["US| ", "CA| ", "UK| "]
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "true").lower() in ("true", "1", "yes")

# --- CONFIG ---
SKIP_KNOWN_MISSING = False  # TEMPORARILY DISABLED to give AI a chance
MAX_AI_CALLS = None  # UNLIMITED - Process all channels with AI

# --- SOURCES ---
REFERENCE_SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", "all_sources.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz", "us_locals.xml.gz"),
    ("https://epghub.xyz/epg/EPG-CA.xml.gz", "epg_canada.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz", "us_sports.xml.gz")  # Sports networks
]

def fetch_playlist():
    """Fetch live streams from Xtream Codes API with retry."""
    url = f"{XC_URL}/player_api.php?username={XC_USER}&password={XC_PASS}&action=get_live_streams"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=60)
            return response.json()
        except Exception as e:
            if attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"[WARNING] Playlist fetch failed (attempt {attempt + 1}/3): {e}")
                print(f"          Retrying in {wait}s...")
                import time
                time.sleep(wait)
            else:
                print(f"[ERROR] Playlist fetch failed after 3 attempts: {e}")
                return []

def extract_core_name(channel_name):
    """
    Extract the core channel identifier from decorated IPTV names.
    Returns a cleaned version for matching.
    """
    original = channel_name
    
    # Step 1: Extract callsign from parentheses (highest priority)
    callsign_match = re.search(r'\(([A-Z]{4,5})\)', channel_name)
    if callsign_match:
        return callsign_match.group(1)
    
    # Step 2: Remove quality markers
    clean = re.sub(r'[ᴴᴰᵁᴴᴰ⁴ᴷˢᵈ¹⁰⁸⁰ᵖᶜᴿᵃᴰ]+', '', channel_name)
    clean = re.sub(r'\b(HD|SD|UHD|4K|FHD|1080p|720p|HEVC|H264|H265)\b', '', clean, flags=re.IGNORECASE)
    
    # Step 3: Remove leading/trailing decorators
    clean = re.sub(r'^[#\|]+\s*', '', clean)
    clean = re.sub(r'\s*[#\|]+$', '', clean)
    
    # Step 4: Split by pipe and extract meaningful parts
    parts = [p.strip() for p in clean.split('|') if p.strip()]
    
    # Step 5: Filter out common metadata
    filtered_parts = []
    for p in parts:
        p_upper = p.upper()
        # Skip if it's just metadata
        if any(skip in p_upper for skip in [
            'PRIME', 'SPORTS', 'NETWORK', 'LOCALS', 'CHANNELS'
        ]):
            continue
        # Skip if it's just a region code
        if p_upper in ['US', 'CA', 'UK', 'EU']:
            continue
        filtered_parts.append(p)
    
    # Step 6: Return the first substantial part
    if filtered_parts:
        result = filtered_parts[0].strip()
        # Remove any remaining pipes or hashes
        result = re.sub(r'[|#]+', ' ', result).strip()
        return result
    
    # Fallback
    return channel_name.strip()

def build_regional_maps(reference_map):
    """Pre-compute regional subsets once instead of filtering per channel."""
    us_map = {name: xml_id for name, xml_id in reference_map.items() if xml_id.endswith('.us')}
    ca_map = {name: xml_id for name, xml_id in reference_map.items() if xml_id.endswith('.ca')}
    uk_map = {name: xml_id for name, xml_id in reference_map.items() if xml_id.endswith('.uk')}
    return {"US": us_map, "CA": ca_map, "UK": uk_map}

def get_regional_map(channel_name, regional_maps, reference_map):
    """Get the appropriate regional map for a channel name."""
    if channel_name.startswith("CA| "):
        return regional_maps["CA"] or reference_map
    if channel_name.startswith("US| "):
        return regional_maps["US"] or reference_map
    if channel_name.startswith("UK| "):
        return regional_maps["UK"] or reference_map
    return reference_map

def is_priority_channel(name):
    """Check if channel belongs to a priority region (US, CA, UK) without substring false matches."""
    for prefix in PRIORITY_PREFIXES:
        if name.startswith(prefix):
            return True
    return False

def main():
    # 1. Load Databases
    known_matches = {}
    if os.path.exists(KNOWN_MATCHES_FILE):
        with open(KNOWN_MATCHES_FILE, 'r', encoding='utf-8') as f:
            known_matches = json.load(f)
        print(f"[*] Loaded {len(known_matches)} known matches from database")

    # Ingest AI Suggestions
    if os.path.exists(SUGGESTED_MATCHES_FILE):
        try:
            with open(SUGGESTED_MATCHES_FILE, 'r', encoding='utf-8') as f:
                suggestions = json.load(f)
                if suggestions:
                    known_matches.update(suggestions)
                    print(f"[*] Added {len(suggestions)} AI suggestions")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Could not load suggested_matches.json: {e}")

    if OFFLINE_MODE:
        print(f"\n[*] OFFLINE MODE: Using known matches as channel source (no IPTV fetch)")
        # Use known_matches keys as the channel list
        all_channel_names = [name for name in known_matches.keys() if not name.startswith("#")]
    else:
        playlist = fetch_playlist()
        if not playlist:
            print("[ERROR] Failed to fetch playlist!")
            sys.exit(1)
        print(f"[*] Fetched {len(playlist)} total channels from IPTV provider")
        all_channel_names = [ch.get('name', '').strip() for ch in playlist]

    known_missing = set()
    if SKIP_KNOWN_MISSING and os.path.exists(MISSING_LOG):
        with open(MISSING_LOG, 'r', encoding='utf-8') as f:
            known_missing = {line.strip() for line in f if line.strip()}
        print(f"[*] Loaded {len(known_missing)} known missing channels (will skip)")
    else:
        print(f"[*] Processing all channels with AI - no skip list")

    # Smart cache: only re-download if cache is stale
    cache_max_age = float(os.getenv("CACHE_MAX_AGE", "24"))
    print(f"\n[*] Loading reference EPG data (cache max age: {cache_max_age}h)...")
    reference_data, valid_ids = epg_cache.fetch_reference_data_smart(
        REFERENCE_SOURCES, CACHE_DIR, cache_max_age_hours=cache_max_age
    )
    id_to_name = {xml_id: names[0] for xml_id, names in epg_cache.build_reverse_lookup(reference_data).items() if names}
    ref_names = list(reference_data.keys())

    # Count by region
    ca_count = sum(1 for xml_id in valid_ids if xml_id.endswith('.ca'))
    us_count = sum(1 for xml_id in valid_ids if xml_id.endswith('.us'))
    print(f"[*] Breakdown: {us_count} US channels, {ca_count} CA channels")

    # Pre-compute regional maps once (instead of filtering per channel)
    regional_maps = build_regional_maps(reference_data)
    print(f"[*] Regional maps: US={len(regional_maps['US'])}, CA={len(regional_maps['CA'])}, UK={len(regional_maps['UK'])}")

    target_names = [name for name in all_channel_names if is_priority_channel(name)]

    print(f"\n[*] Processing {len(target_names)} priority channels (US|CA|UK)...")

    final_matches = {}
    new_missing = []
    ai_queue = []
    stats = {"known": 0, "exact": 0, "ai": 0, "skipped": 0, "stale": 0}

    print("\n[PHASE 1] Quick wins (known matches + exact matches)...")
    pbar = tqdm(target_names, unit="ch")

    for name in pbar:
        # Check known database
        if name in known_matches:
            target_id = known_matches[name]
            if target_id in valid_ids:
                final_matches[name] = target_id
                stats["known"] += 1
                continue
            else:
                stats["stale"] += 1
                del known_matches[name]

        # Skip known missing (only if enabled)
        if SKIP_KNOWN_MISSING and name in known_missing:
            new_missing.append(name)
            stats["skipped"] += 1
            continue

        # Extract core name for matching
        core_name = extract_core_name(name)

        # Try direct lookup on extracted name
        if core_name in reference_data:
            final_matches[name] = reference_data[core_name]
            known_matches[name] = reference_data[core_name]
            stats["exact"] += 1
            continue

        # Try very high fuzzy threshold (98%+) for obvious matches
        filtered_map = get_regional_map(name, regional_maps, reference_data)
        filtered_names = list(filtered_map.keys())

        search_pool = filtered_names if filtered_names else ref_names
        matches = process.extract(core_name, search_pool, limit=1)

        if matches and matches[0][1] >= 98:
            best_id = (filtered_map if filtered_names else reference_data)[matches[0][0]]
            final_matches[name] = best_id
            known_matches[name] = best_id
            stats["exact"] += 1
            continue

        # Queue for AI (only in online mode - offline mode skips AI)
        if not OFFLINE_MODE:
            ai_queue.append(name)
        else:
            new_missing.append(name)

    if not OFFLINE_MODE:
        print(f"\n[PHASE 2] AI matching for {len(ai_queue)} channels...")
        print(f"[*] Processing ALL channels with Gemini 3 Flash (no limit)...")

        if ai_queue:
            ai_limit = MAX_AI_CALLS if MAX_AI_CALLS else len(ai_queue)
            ai_subset = ai_queue[:ai_limit]

            ai_pbar = tqdm(ai_subset, unit="ch", desc="AI Matching")

            for name in ai_pbar:
                try:
                    core_name = extract_core_name(name)

                    # Get regional candidates (pre-computed, instant lookup)
                    filtered_map = get_regional_map(name, regional_maps, reference_data)
                    filtered_names = list(filtered_map.keys())

                    search_pool = filtered_names if filtered_names else ref_names

                    # Get top 15 fuzzy candidates (AI will pick from these)
                    candidates = process.extract(core_name, search_pool, limit=15)

                    # Build candidate dict
                    candidate_dict = {match: (filtered_map if filtered_names else reference_data)[match]
                                     for match, score in candidates}

                    # Ask AI
                    result = ai_client.match_channel(name, candidate_dict)

                    if result and result in valid_ids:
                        final_matches[name] = result
                        known_matches[name] = result
                        stats["ai"] += 1
                    else:
                        new_missing.append(name)

                except Exception as e:
                    ai_pbar.write(f"[AI ERROR] {name}: {e}")
                    new_missing.append(name)

            # Add remaining to missing if limit was reached
            if MAX_AI_CALLS and len(ai_queue) > MAX_AI_CALLS:
                print(f"\n[INFO] Processed {MAX_AI_CALLS} channels. {len(ai_queue) - MAX_AI_CALLS} remaining added to missing.")
                new_missing.extend(ai_queue[MAX_AI_CALLS:])
    else:
        print(f"\n[PHASE 2] Skipped (offline mode - no AI matching)")

    # Save results
    if not os.path.exists(os.path.dirname(KNOWN_MATCHES_FILE)):
        os.makedirs(os.path.dirname(KNOWN_MATCHES_FILE))

    with open(KNOWN_MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(known_matches, f, indent=4)

    if os.path.exists(SUGGESTED_MATCHES_FILE):
        with open(SUGGESTED_MATCHES_FILE, 'w') as f:
            json.dump({}, f)

    clean_missing = sorted(list(set([
        m for m in new_missing
        if is_priority_channel(m) and not m.startswith("#")
    ])))
    
    log_dir = os.path.dirname(MISSING_LOG)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    with open(MISSING_LOG, 'w', encoding='utf-8') as f:
        f.write("\n".join(clean_missing))

    # Generate EPG
    print(f"\n[*] Generating Super EPG with program data...")
    
    base_name = os.path.splitext(OUTPUT_BASE)[0]
    OUTPUT_GZ = base_name + ".xml.gz"
    
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
    print(f"\n=== FINAL STATS ===")
    print(f"Known from DB: {stats['known']}")
    print(f"Exact matches: {stats['exact']}")
    print(f"AI-matched: {stats['ai']}")
    print(f"Skipped (known missing): {stats['skipped']}")
    print(f"Stale (removed): {stats['stale']}")
    print(f"Total matched: {len(final_matches)}")
    print(f"Missing: {len(clean_missing)} channels")
    print(f"\nSuccess rate: {(len(final_matches) / len(target_playlist) * 100):.1f}%")

if __name__ == "__main__":
    main()