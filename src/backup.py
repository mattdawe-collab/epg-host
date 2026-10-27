"""Backup guide sources for when a main source stops updating.

epgshare01 froze on 2026-10-21 and most channels ran out of listings within three days. The backups use their own
channel IDs, so each matched guide channel is paired with its twin in a backup by strict rules: the same name once
quality words and filler words go (numbers, feeds and '+' must agree), or the same local-station callsign and
sub-channel. A name shared by two different backup channels is never guessed. guide.write_guide only uses a twin's
programmes for a channel whose own listings end within the next 24 hours, and only after its own listings end.
Match decisions are untouched: TiviMate keeps seeing the same channels.

Plex channels (guide IDs ending in '.plex', about 700 of the user's channels) take their twin from Matt Huisman's
US Plex guide (i.mjh.nz), which names each channel plainly ("Euronews"). Its kind is "plex" instead of a country.
"""
import os
import re
from collections import defaultdict

import epg_cache
from matching import (FEED_WORDS, GENERIC_CORES, NETWORKS, NUMBER_WORDS, QUALITY_WORDS, country_of, fold_accents, normalize_feed,
                      strip_decorations)

# (url, cache file, country or "plex"), first backup wins. i.mjh.nz Plex: free, updated several times a day.
# iptv-epg.org: free, updated daily, names in the form "US - CNN".
PLEX = "plex"
SOURCES = [
    ("https://i.mjh.nz/Plex/us.xml.gz", "backup_plex_us.xml.gz", PLEX),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "backup_us.xml.gz", "us"),
    ("https://iptv-epg.org/files/epg-gb.xml.gz", "backup_uk.xml.gz", "uk"),
    ("https://iptv-epg.org/files/epg-ca.xml.gz", "backup_ca.xml.gz", "ca"),
]
COUNTRY_TAGS = {"us": "US", "uk": "UK", "ca": "CA"}
BACKUP_TAG = re.compile(r"^([A-Z0-9+]{2,8}) - (.+)$")
FILLER_WORDS = {"THE", "CHANNEL", "NETWORK", "TV", "TELEVISION"}
PLEX_MARK = re.compile(r"\[\s*PLEX\s*\]", re.IGNORECASE)
LOCAL_ID = re.compile(r"^([KWC][A-Z]{2,3})(?:-(DT|TV|LD|CD|LP|HD)(\d*))?\.us_locals\d*$")
BACKUP_STATION = re.compile(r"\b([KWC][A-Z]{2,3})(?:-(?:DT|D)(\d+)|-(?:TV|LD|CD|LP))?\b")
ID_QUALITY = re.compile(r"(UHD|FHD|HD|SD|4K)", re.IGNORECASE)


def name_key(text):
    """'ESPN HD' -> 'ESPN', 'A&E Network' -> 'AANDE', 'HBO (Pacific)' -> 'HBOWEST', 'AMC+' -> 'AMCPLUS'.
    None when nothing distinctive is left."""
    text = normalize_feed(fold_accents(strip_decorations(text)))
    text = QUALITY_WORDS.sub(" ", text).replace("&", " AND ").replace("+", " PLUS ")
    words = [NUMBER_WORDS.get(w, w) for w in re.sub(r"[^0-9A-Za-z]+", " ", text).upper().split()]
    kept = [w for w in words if w not in FILLER_WORDS] or words
    if all(w in GENERIC_CORES or w in FEED_WORDS or w in FILLER_WORDS for w in kept):
        return None  # "West TV", "Movies!": nothing that identifies one channel
    key = "".join(kept)
    return key if len(key) >= 2 and not key.isdigit() else None


def primary_country(xml_id):
    if xml_id.endswith(".plex"):
        return "us"
    country = country_of(xml_id)
    return "uk" if country == "gb" else country


def _pick(ids):
    """One backup channel for a name, or None when the name belongs to different channels.
    Copies that differ only by HD/SD in the ID ('ESPN.us', 'ESPNHD.us') are the same channel."""
    ids = list(dict.fromkeys(ids))
    if len({re.sub(r"[^a-z0-9]", "", ID_QUALITY.sub("", i).lower()) for i in ids}) == 1:
        return min(ids, key=len)
    return None


def _index_backup(country, names_by_id):
    """(name key, is plex) -> backup IDs, and (callsign, sub-channel) -> backup IDs; sub-channel 1 = main feed."""
    by_key, by_station = defaultdict(list), defaultdict(list)
    if country == PLEX:  # every channel in the Plex guide is a Plex channel, named plainly
        for backup_id, names in names_by_id.items():
            for key in {name_key(PLEX_MARK.sub(" ", d or "")) for d in names} - {None}:
                by_key[(key, True)].append(backup_id)
        return by_key, by_station
    tag = COUNTRY_TAGS[country]
    for backup_id, names in names_by_id.items():
        for display in names:
            match = BACKUP_TAG.match((display or "").strip())
            if not match or match.group(1) != tag:
                continue
            rest = match.group(2)
            plex = bool(PLEX_MARK.search(rest))
            key = name_key(PLEX_MARK.sub(" ", rest))
            if key:
                by_key[(key, plex)].append(backup_id)
            if country == "us":
                found = [(call, int(sub) if sub else 1) for call, sub in BACKUP_STATION.findall(rest)]
                with_sub = {call for call, sub in found if sub > 1}
                for call, sub in found:  # "CBS WNKY WNKY-DT2" is the -DT2 sub-channel, not WNKY's main feed
                    if sub > 1 or call not in with_sub:
                        by_station[(call, sub)].append(backup_id)
    return by_key, by_station


def networks_in(texts):
    """Broadcast networks named in some names: {'CBS'} for 'US: CBS (WCBI)'."""
    return {n for t in texts for n in NETWORKS if re.search(r"\b" + n + r"\b", (t or "").upper())}


def _bridge_one(primary_index, country, names_by_id, networks=None):
    by_key, by_station = _index_backup(country, names_by_id)
    networks = networks or {}
    found = {}

    def same_network(xml_id, backup_id):
        """A twin naming another network (an NBC channel given a CBS guide) is refused."""
        wanted, theirs = networks.get(xml_id), networks_in(names_by_id.get(backup_id, []))
        return not (wanted and theirs) or bool(wanted & theirs)

    for xml_id, names in primary_index.items():
        if (not xml_id.endswith(".plex")) if country == PLEX else primary_country(xml_id) != country:
            continue
        station = LOCAL_ID.match(xml_id)
        if station:
            call, kind, number = station.groups()
            sub = int(number) if kind == "DT" and number else 1
            ids = [i for i in dict.fromkeys(by_station.get((call, sub), [])) if same_network(xml_id, i)]
            if ids:
                found[xml_id] = ids[0]  # several backup copies of one station are the same station
            continue
        plex = xml_id.endswith(".plex")
        picks = {_pick(by_key.get((key, plex), [])) for key in map(name_key, names) if key and (key, plex) in by_key}
        picks.discard(None)
        if len(picks) == 1 and same_network(xml_id, next(iter(picks))):
            found[xml_id] = picks.pop()
    return found


def build_bridge(primary_index, backups):
    """{matched guide ID: backup ID}. primary_index: guide ID -> display names; backups: [(country, backup ID ->
    display names)], earlier backups first."""
    found = {}
    for country, names_by_id in backups:
        for xml_id, backup_id in _bridge_one(primary_index, country, names_by_id).items():
            found.setdefault(xml_id, backup_id)
    return found


def fetch(cache_dir, cache_max_age_hours=24.0, sources=None):
    """Download the backups. Returns ([(country, path, backup ID -> names)], {file: status}). Never raises:
    a missing backup only means no fallback tonight."""
    os.makedirs(cache_dir, exist_ok=True)
    loaded, status = [], {}
    for url, filename, country in (SOURCES if sources is None else sources):
        path = os.path.join(cache_dir, filename)
        age = epg_cache.get_cache_age_hours(path)
        if age <= cache_max_age_hours:
            state = "cached"
            print(f"  [{filename}] using cache ({age:.1f}h old)")
        else:
            print(f"  [{filename}] downloading")
            state = "downloaded" if epg_cache.download_file(url, path, timeout=300) else (
                "stale cache" if os.path.exists(path) else "failed")
        if state == "failed":
            status[filename] = state
            continue
        _, ids, index = epg_cache.parse_epg_channels(path, full_scan=country == PLEX)
        if not ids:
            status[filename] = "failed"
            continue
        status[filename] = state
        loaded.append((country, path, index))
        print(f"    [OK] {len(ids):,} backup channel IDs")
    return loaded, status


def plan(matched_ids, primary_index, loaded, networks=None):
    """[(backup path, {backup ID: [matched guide IDs]})] for guide.write_guide, plus the number of guide IDs with a
    twin. Each matched guide ID gets at most one twin, from the first backup that has one. networks: guide ID ->
    networks named by the provider's channels that use it (see networks_in)."""
    wanted = {i: primary_index.get(i, []) for i in matched_ids}
    taken, result = set(), []
    for country, path, index in loaded:
        pairs = _bridge_one({i: n for i, n in wanted.items() if i not in taken}, country, index, networks)
        inverted = defaultdict(list)
        for xml_id, backup_id in pairs.items():
            inverted[backup_id].append(xml_id)
            taken.add(xml_id)
        if inverted:
            result.append((path, dict(inverted)))
    return result, len(taken)
