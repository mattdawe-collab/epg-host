"""Download, cache and read the channel lists of the XMLTV guide sources."""
import gzip
import os
import time
from dataclasses import dataclass, field

import requests
from lxml import etree

SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", "all_sources.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz", "us_locals.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz", "us_sports.xml.gz"),
    ("https://epg.pw/xmltv/epg_GB.xml.gz", "epg_uk_pw.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz", "epg_uk_ripper.xml.gz"),
    ("https://epg.pw/xmltv/epg_CA.xml.gz", "epg_canada_pw.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada1.xml.gz", "globetv_canada1.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada2.xml.gz", "globetv_canada2.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada3.xml.gz", "globetv_canada3.xml.gz"),
]


@dataclass
class ReferenceData:
    by_name: dict = field(default_factory=dict)        # display name -> channel id (first source wins)
    valid_ids: set = field(default_factory=set)
    index: dict = field(default_factory=dict)          # channel id -> display names
    source_status: dict = field(default_factory=dict)  # filename -> downloaded | cached | stale cache | failed
    paths: list = field(default_factory=list)          # readable source files, in source order


def get_cache_age_hours(path):
    if not os.path.exists(path):
        return float("inf")
    return (time.time() - os.path.getmtime(path)) / 3600


def download_file(url, dest_path, timeout=120):
    """Download to a temp file and only replace dest_path when the result is a gzip file."""
    tmp_path = dest_path + ".part"
    try:
        print(f"    Downloading {url}")
        with requests.get(url, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        with open(tmp_path, "rb") as f:
            if f.read(2) != b"\x1f\x8b":
                raise ValueError("not a gzip file")
        os.replace(tmp_path, dest_path)
        print(f"    [OK] {os.path.getsize(dest_path) / 1048576:.1f} MB")
        return True
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def parse_epg_channels(path):
    """Read the <channel> list. XMLTV lists channels before programmes, so stop at the first programme."""
    by_name, ids, index = {}, set(), {}
    try:
        with gzip.open(path, "rb") as f:
            for _, elem in etree.iterparse(f, events=("end",), tag=("channel", "programme"),
                                           resolve_entities="internal", no_network=True):
                if elem.tag == "programme":
                    break
                channel_id = (elem.get("id") or "").strip()
                if channel_id:
                    ids.add(channel_id)
                    names = index.setdefault(channel_id, [])
                    for display in elem.findall("display-name"):
                        text = (display.text or "").strip()
                        if text:
                            by_name.setdefault(text, channel_id)
                            if text not in names:
                                names.append(text)
                elem.clear()
    except Exception as e:
        print(f"    [FAIL] Could not read {os.path.basename(path)}: {type(e).__name__}: {e}")
    return by_name, ids, index


def fetch_reference_data(sources, cache_dir, cache_max_age_hours=24.0):
    os.makedirs(cache_dir, exist_ok=True)
    ref = ReferenceData()
    for url, filename in sources:
        path = os.path.join(cache_dir, filename)
        age = get_cache_age_hours(path)
        if age <= cache_max_age_hours:
            status = "cached"
            print(f"  [{filename}] using cache ({age:.1f}h old)")
        else:
            print(f"  [{filename}] downloading")
            if download_file(url, path):
                status = "downloaded"
            elif os.path.exists(path):
                status = "stale cache"
            else:
                ref.source_status[filename] = "failed"
                continue
        by_name, ids, index = parse_epg_channels(path)
        if not ids:
            ref.source_status[filename] = "failed"
            continue
        ref.source_status[filename] = status
        ref.paths.append(path)
        for name, channel_id in by_name.items():
            ref.by_name.setdefault(name, channel_id)
        ref.valid_ids |= ids
        for channel_id, names in index.items():
            merged = ref.index.setdefault(channel_id, [])
            merged.extend(n for n in names if n not in merged)
        print(f"    [OK] {len(by_name):,} names, {len(ids):,} channel IDs")
    print(f"  Total: {len(ref.by_name):,} names, {len(ref.valid_ids):,} channel IDs")
    return ref
