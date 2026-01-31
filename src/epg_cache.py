"""
EPG Cache Module - Smart caching for EPG data sources
Handles downloading, caching, and parsing EPG XML files
"""
import os
import gzip
import requests
import time
from datetime import datetime, timedelta
from lxml import etree
from typing import Dict, Set, Tuple, List, Callable, Optional


def get_cache_age_hours(cache_path: str) -> float:
    """Get the age of a cached file in hours"""
    if not os.path.exists(cache_path):
        return float('inf')
    
    mtime = os.path.getmtime(cache_path)
    age_seconds = time.time() - mtime
    return age_seconds / 3600


def download_file(url: str, dest_path: str, timeout: int = 60) -> bool:
    """Download a file with progress indication"""
    try:
        print(f"    Downloading: {url[:60]}...")
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"    ✓ Downloaded: {size_mb:.1f} MB")
        return True
        
    except Exception as e:
        print(f"    ✗ Download failed: {e}")
        return False


def parse_epg_channels(file_path: str, is_dummy_callback: Optional[Callable] = None) -> Tuple[Dict[str, str], Set[str]]:
    """
    Parse an EPG XML file and extract channel information.
    
    Returns:
        Tuple of (reference_data dict, valid_ids set)
        - reference_data: {display_name: xmlid}
        - valid_ids: set of all valid channel IDs
    """
    reference_data = {}
    valid_ids = set()
    
    try:
        opener = gzip.open if file_path.endswith('.gz') else open
        
        with opener(file_path, 'rb') as f:
            context = etree.iterparse(f, events=('end',), tag='channel')
            
            for event, elem in context:
                channel_id = elem.get('id', '')
                
                # Skip bad/dummy IDs
                if is_dummy_callback and is_dummy_callback(channel_id):
                    elem.clear()
                    continue
                
                if channel_id:
                    valid_ids.add(channel_id)
                    
                    # Get all display names for this channel
                    for display_name_elem in elem.findall('display-name'):
                        if display_name_elem.text:
                            display_name = display_name_elem.text.strip()
                            # Only add if not already present (first occurrence wins)
                            if display_name not in reference_data:
                                reference_data[display_name] = channel_id
                
                # Memory cleanup
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
                    
    except Exception as e:
        print(f"    ✗ Error parsing {file_path}: {e}")
    
    return reference_data, valid_ids


def fetch_reference_data_smart(
    reference_sources: List[Tuple[str, str]],
    cache_dir: str,
    valid_ids_callback: Optional[Callable] = None,
    force_refresh: bool = False,
    cache_max_age_hours: float = 24.0
) -> Tuple[Dict[str, str], Set[str]]:
    """
    Fetch and parse EPG reference data with smart caching.
    
    Args:
        reference_sources: List of (url, filename) tuples
        cache_dir: Directory to store cached files
        valid_ids_callback: Function to check if ID is invalid/dummy
        force_refresh: If True, re-download all files regardless of cache
        cache_max_age_hours: Maximum age of cache before refresh (default 24 hours)
    
    Returns:
        Tuple of (reference_data dict, valid_ids set)
    """
    os.makedirs(cache_dir, exist_ok=True)
    
    combined_reference_data = {}
    combined_valid_ids = set()
    
    for url, filename in reference_sources:
        cache_path = os.path.join(cache_dir, filename)
        cache_age = get_cache_age_hours(cache_path)
        
        # Determine if we need to download
        needs_download = force_refresh or cache_age > cache_max_age_hours or not os.path.exists(cache_path)
        
        if needs_download:
            if cache_age != float('inf'):
                print(f"  [{filename}] Cache age: {cache_age:.1f}h (max: {cache_max_age_hours}h) - refreshing")
            else:
                print(f"  [{filename}] No cache found - downloading")
            
            success = download_file(url, cache_path)
            if not success and os.path.exists(cache_path):
                print(f"    Using stale cache for {filename}")
            elif not success:
                print(f"    Skipping {filename} - no data available")
                continue
        else:
            print(f"  [{filename}] Using cache (age: {cache_age:.1f}h)")
        
        # Parse the file
        print(f"    Parsing {filename}...")
        ref_data, valid_ids = parse_epg_channels(cache_path, valid_ids_callback)
        
        # Merge results (first source wins for duplicate display names)
        for display_name, xmlid in ref_data.items():
            if display_name not in combined_reference_data:
                combined_reference_data[display_name] = xmlid
        
        combined_valid_ids.update(valid_ids)
        
        print(f"    ✓ Found {len(ref_data):,} display names, {len(valid_ids):,} channel IDs")
    
    print(f"\n  Total: {len(combined_reference_data):,} display names, {len(combined_valid_ids):,} unique channel IDs")
    
    return combined_reference_data, combined_valid_ids


def build_reverse_lookup(reference_data: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Build a reverse lookup: {xmlid: [display_names]}
    Useful for finding all names associated with a channel ID
    """
    reverse = {}
    for display_name, xmlid in reference_data.items():
        if xmlid not in reverse:
            reverse[xmlid] = []
        reverse[xmlid].append(display_name)
    return reverse


def extract_callsign_from_epg_id(xmlid: str) -> Optional[str]:
    """
    Extract FCC/CRTC callsign from an EPG XMLID.
    
    Examples:
        "WABC.us" -> "WABC"
        "ABC.(WABC).New.York,.NY.us" -> "WABC"
        "CBLT.ca" -> "CBLT"
    """
    import re
    
    if not xmlid:
        return None
    
    # Pattern 1: Callsign in parentheses
    match = re.search(r'\(([A-Z]{3,5}(?:-?[A-Z0-9]*)?)\)', xmlid)
    if match:
        return match.group(1).replace('-', '')
    
    # Pattern 2: Simple format like "WABC.us" or "CBLT.ca"
    match = re.match(r'^([A-Z]{3,5})\.', xmlid)
    if match:
        return match.group(1)
    
    # Pattern 3: Format like "ABC.East.us"
    match = re.match(r'^([A-Z]{2,4})\.', xmlid)
    if match:
        potential = match.group(1)
        # Only return if it looks like a network code, not a callsign
        if potential in ['ABC', 'NBC', 'CBS', 'FOX', 'PBS', 'CW', 'CTV', 'CBC', 'TSN', 'RDS']:
            return None
        return potential
    
    return None


def get_xmlids_by_callsign(valid_ids: Set[str], callsign: str) -> List[str]:
    """
    Find all XMLIDs that contain a specific callsign.
    """
    import re
    
    callsign_upper = callsign.upper()
    matches = []
    
    for xmlid in valid_ids:
        # Check if callsign appears in the XMLID
        if callsign_upper in xmlid.upper():
            matches.append(xmlid)
        # Also check for patterns like "(WABC)" in the ID
        if f"({callsign_upper})" in xmlid.upper():
            matches.append(xmlid)
    
    return list(set(matches))


def validate_epg_coverage(valid_ids: Set[str]) -> Dict[str, int]:
    """
    Analyze EPG coverage by region/network.
    Returns counts of channels by category.
    """
    stats = {
        'us_total': 0,
        'ca_total': 0,
        'uk_total': 0,
        'us_locals': 0,
        'us_cable': 0,
        'ca_broadcast': 0,
        'ca_specialty': 0,
    }
    
    for xmlid in valid_ids:
        if xmlid.endswith('.us'):
            stats['us_total'] += 1
            # Check if it looks like a local station (has parentheses with callsign)
            if '(' in xmlid and ')' in xmlid:
                stats['us_locals'] += 1
            else:
                stats['us_cable'] += 1
        elif xmlid.endswith('.ca'):
            stats['ca_total'] += 1
        elif xmlid.endswith('.uk'):
            stats['uk_total'] += 1
    
    return stats
