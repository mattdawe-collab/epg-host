"""Match provider channel names to guide channel IDs without AI.

Trust order: decisions made in Claude sessions (known) always win; old Gemini-era matches (legacy) and
automatic matches are only used when they pass the free checks in flag_reasons()."""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process, utils

OLD_PREFIXES = (  # the provider's naming until 2026: "US| CNN HD"
    "US| ", "CA| ", "UK| ",
    "PRIME| ", "SLING| ", "GO| ", "PLAY+| ",
    "UK-BBCI| ", "UK-NOWTV| ",
    "SPORTS| ", "NFL TEAMS| ", "NHL TEAM| ",
    "4K| ", "ENGLISH| ", "EN| ",
)
NEW_TAGS = ("US", "UK", "NOW", "CA", "CA EN", "CA FR", "PRIME", "PLAY+", "AT&T", "TV", "4K", "ENGLISH", "SPORTS")
PRIORITY_PREFIXES = OLD_PREFIXES + tuple(f"{t}: " for t in NEW_TAGS)  # current naming: "US: CNN HD"
# Where each old group went when the provider regrouped its channels (found by name overlap, 2026-09-26).
TAG_ALIASES = {"SLING": ("AT&T",), "GO": ("TV",), "UK-NOWTV": ("NOW",), "UK-BBCI": ("UK",), "NHL TEAM": ("US",),
               "CA": ("CA", "CA EN", "CA FR")}
REGION_PREFIXES = {  # TV: (formerly GO|) mixes US, Spanish, Israeli and FAST channels, so it has no region
    "CA": ("CA| ", "CA: ", "CA EN: ", "CA FR: "),
    "US": ("US| ", "SLING| ", "US: ", "AT&T: "),
    "UK": ("UK| ", "UK-BBCI| ", "UK-NOWTV| ", "UK: ", "NOW: "),
}
_PREFIXES_LONGEST_FIRST = sorted(PRIORITY_PREFIXES, key=len, reverse=True)
PREFIX_WORDS = {p[:-2].strip().upper() for p in PRIORITY_PREFIXES} | {"EU", "LOCALS", "CHANNELS"}
AUTO_MATCH_SCORE = 93
QUALITY_WORDS = re.compile(r"\b(HD|SD|UHD|FHD|4K|HEVC|H264|H265|1080P|720P|60FPS)\b", re.IGNORECASE)
NO_GUIDE_PATTERN = re.compile(r"\b(PPV|EVENTS?|REPLAY|LOOP)\b|\b24/7\b", re.IGNORECASE)
CALLSIGN_IN_NAME = re.compile(r"\(([A-Z]{4,5})\)")
FEED_WORDS = {"WEST", "EAST", "PACIFIC"}
GENERIC_CORES = {"PPV", "WEST", "EAST", "PACIFIC", "LIVE", "TV", "EVENT", "EVENTS", "HD", "SD", "UHD", "4K",
                 "NEWS", "SPORTS", "MOVIES", "KIDS", "MUSIC"}
TIMESHIFT = re.compile(r"\+\s?\d")
STATION_IN_BRACKETS = re.compile(r"\(([KWC][A-Z]{2,3})(?:-(DT\d*|TV|LD|CD))?\)")  # "(WZTV)", "(WWL)", "(WGBC-DT2)"
BARE_STATION = re.compile(r"\b([KW][A-Z]{3})(?:-DT?(\d+))?\b")  # "KTVI", or "KMOV-D2" for sub-channel 2
NETWORK_WORD = re.compile(r"\b(ABC|CBS|NBC|FOX|CW|PBS|ION|MY ?NETWORK|MYTV|TELEMUNDO|UNIVISION|UNIMAS|ME ?TV)\b",
                          re.IGNORECASE)
STATION_ID = re.compile(r"^([KWC][A-Z]{2,3})(?:-([A-Z]{2}\d*))?\.")  # "WZTV-DT.us_locals1" -> WZTV, DT
STATION_SUFFIX_RANK = {"DT": 0, "": 1, "TV": 2, "HD": 3, "LD": 4, "CD": 5, "LP": 6}  # the main feed first
BARE_STATION_STOP_WORDS = {"KIDS", "WILD"}
NETWORKS = ("ABC", "CBS", "NBC", "FOX", "CW", "PBS")
HOME_COUNTRIES = {"US": {"us"}, "CA": {"ca"}, "UK": {"uk", "gb"}}
ANY_HOME = {"us", "ca", "uk", "gb"}  # mixed groups (PRIME, TV, PLAY+...) accept these when nothing better is known
RESEMBLE_STOP_WORDS = {"THE", "AND", "CHANNEL", "NETWORK", "PLUS", "TV"}
COUNTRY_SUFFIX = re.compile(r"^([a-z]{2})(?:\d+|_.*)?$")  # ".us", ".ca2", ".us_locals1"; ".plex"/".com" are not countries


def is_priority_channel(name):
    return name.startswith(PRIORITY_PREFIXES)


def split_tag(name):
    """('US', 'CNN HD') for 'US: CNN HD' or 'US| CNN HD'; ('', name) when there is no known group tag."""
    for prefix in _PREFIXES_LONGEST_FIRST:
        if name.startswith(prefix):
            return prefix[:-2].strip(), name[len(prefix):]
    return "", name


def strip_decorations(text):
    """Blank out superscript quality marks (ᴴᴰ ᴿᴬᵂ ³⁸⁴⁰ᴾ) and symbols such as ◉."""
    return "".join(" " if unicodedata.category(ch) in ("Lm", "No", "So", "Sk") else ch for ch in text)


def fold_accents(text):
    """'Évasion' -> 'Evasion'."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if unicodedata.category(ch) != "Mn")


def extract_core_name(channel_name):
    """The part of a decorated IPTV name that identifies the channel: a callsign if present."""
    for callsign in CALLSIGN_IN_NAME.findall(channel_name):
        if callsign not in FEED_WORDS:
            return callsign
    clean = strip_decorations(split_tag(channel_name)[1])
    clean = re.sub(r"\((?:WEST|EAST|PACIFIC)\)", " ", clean, flags=re.IGNORECASE)
    clean = QUALITY_WORDS.sub("", clean)
    clean = re.sub(r"^[#|]+\s*", "", clean)
    clean = re.sub(r"\s*[#|]+$", "", clean)
    parts = [p.strip() for p in clean.split("|") if p.strip() and p.strip().upper() not in PREFIX_WORDS]
    if parts:
        return " ".join(re.sub(r"[|#]+", " ", parts[0]).split())
    return channel_name.strip()


def normalize_name(name):
    """Group tag plus name without decorations, quality tags or punctuation: 'US: CNN HD' -> 'US|CNN'.
    '+' is kept as PLUS so AMC+ is not AMC and Discovery +1 is not Discovery."""
    prefix, rest = split_tag(name)
    if not prefix:
        prefix, sep, rest = name.partition("| ")
        if not sep:
            prefix, rest = "", name
    rest = QUALITY_WORDS.sub(" ", fold_accents(strip_decorations(rest)).replace("+", " PLUS "))
    rest = " ".join(re.sub(r"[^0-9A-Za-z]+", " ", rest).upper().split())
    return f"{prefix.strip().upper()}|{rest}"


def is_region(xml_id, region):
    suffix = xml_id.rsplit(".", 1)[-1] if "." in xml_id else ""
    return suffix.startswith(region)


def region_of(channel_name):
    for region, prefixes in REGION_PREFIXES.items():
        if channel_name.startswith(prefixes):
            return region
    return "ALL"


def country_of(xml_id):
    """Two-letter country code of a guide ID ('CNN.us' -> 'us', 'X.us_locals1' -> 'us'); None for '.plex' etc."""
    match = COUNTRY_SUFFIX.match(xml_id.rsplit(".", 1)[-1].lower()) if xml_id and "." in xml_id else None
    return match.group(1) if match else None


def same_country(a, b):
    return a == b or {a, b} <= {"uk", "gb"}


def flag_reasons(name, xml_id, expected_country=None, id_country=None):
    """Free checks for a probably-wrong match: wrong country, wrong callsign, wrong network, placeholder guide.
    expected_country (from the provider's playlist) overrides the group's home country; id_country gives the
    country of guide IDs that are bare numbers (from their source file)."""
    reasons = []
    region = region_of(name)
    country = country_of(xml_id) or id_country
    if country:
        if expected_country:
            if not same_country(country, expected_country):
                reasons.append("region")
        elif region in HOME_COUNTRIES:
            if country not in HOME_COUNTRIES[region]:
                reasons.append("region")
        elif country not in ANY_HOME:
            reasons.append("foreign")
    if any(c not in FEED_WORDS and c not in xml_id.upper() for c in CALLSIGN_IN_NAME.findall(name)):
        reasons.append("callsign")
    in_name = {n for n in NETWORKS if re.search(rf"\b{n}\b", name.upper())}
    in_id = {n for n in NETWORKS if n in xml_id.upper()}
    if in_name and in_id and not (in_name & in_id):
        reasons.append("network")
    if "dummy" in xml_id.lower() or re.search(r"(?<![a-z])ppv(?![a-z])", xml_id.lower()):
        reasons.append("placeholder")
    return reasons


def expected_countries(channels):
    """name -> expected guide country, from the provider's own guide ID for the channel or, failing that,
    from the other channels in the same playlist section (the '#### ... ####' header block).
    A section needs at least two hints, 60% of them agreeing."""
    block_of, hints = {}, defaultdict(list)
    block = None
    for channel in channels:
        name = channel["name"]
        if name.startswith("#"):
            block = name
            continue
        block_of[name] = block
        code = country_of(channel.get("epg_id") or "")
        if code:
            hints[block].append("uk" if code == "gb" else code)
    block_country = {}
    for key, codes in hints.items():
        top, count = Counter(codes).most_common(1)[0]
        if count >= 2 and count / len(codes) >= 0.6:
            block_country[key] = top
    result = {}
    for channel in channels:
        name = channel["name"]
        if name.startswith("#"):
            continue
        country = country_of(channel.get("epg_id") or "") or block_country.get(block_of[name])
        if country:
            result[name] = "uk" if country == "gb" else country
    return result


def resembles(channel_name, xml_id, index):
    """Does the guide's name share a real word (or the callsign) with the channel? Catches semantic leaps such as
    a 24/7 'GAME OF THRONES' loop given the HBO East schedule."""
    if any(c not in FEED_WORDS and c in xml_id.upper() for c in CALLSIGN_IN_NAME.findall(channel_name)):
        return True
    guide = [normalize_name(n).split("|", 1)[1] for n in index.get(xml_id, [])]
    channel = normalize_name(channel_name).split("|", 1)[1]
    squeezed = channel.replace(" ", "")
    for g in guide:  # same name once spaces go: "RDS 2" ~ "RDS2 HD", "C-SPAN 1" ~ "CSPAN"
        g_squeezed = g.replace(" ", "")
        if squeezed == g_squeezed or (len(squeezed) >= 5 and squeezed in g_squeezed) \
                or (len(g_squeezed) >= 5 and g_squeezed in squeezed):
            return True
    guide_words = {w for g in guide for w in g.split()}
    joined = " ".join(g.replace(" ", "") for g in guide)
    words = [w for w in channel.split() if len(w) >= 3 and w not in RESEMBLE_STOP_WORDS]
    return any(w in guide_words or (len(w) >= 5 and w in joined) for w in words)


class Pools:
    """Display-name pools per region, prepared once for fast searching. `index` (guide ID -> display names)
    lets automatic matching see every guide sharing a display name, not just the first source's."""

    def __init__(self, by_name, index=None):
        self.ids_by_name = defaultdict(list)
        for xml_id, display_names in (index or {}).items():
            for display in display_names:
                self.ids_by_name[display].append(xml_id)
        for display, xml_id in by_name.items():
            if xml_id not in self.ids_by_name[display]:
                self.ids_by_name[display].append(xml_id)
        self._all_names = list(self.ids_by_name)
        # compare on names without quality words or decorations: "CNN HD" in a guide must match a channel "CNN"
        self._all_processed = [utils.default_process(QUALITY_WORDS.sub(" ", strip_decorations(n))) for n in self._all_names]
        regional = {r: {n: i for n, i in by_name.items() if is_region(i, r.lower())} for r in ("US", "CA", "UK")}
        self.maps = {r: (m or by_name) for r, m in regional.items()}
        self.maps["ALL"] = by_name
        self._names = {r: list(m) for r, m in self.maps.items()}
        self._lower = {r: [n.lower() for n in names] for r, names in self._names.items()}
        self._processed = {r: [utils.default_process(n) for n in names] for r, names in self._names.items()}

    def close_names(self, text, cutoff, limit=10):
        """Display names nearly identical to text (plain ratio, no partial matching), best first."""
        hits = process.extract(utils.default_process(text), self._all_processed,
                               scorer=fuzz.ratio, processor=None, score_cutoff=cutoff, limit=limit)
        return [self._all_names[i] for _, _, i in hits]

    def candidates(self, region, channel_name, limit=10):
        names, lower, pool = self._names[region], self._lower[region], self.maps[region]
        core = extract_core_name(channel_name)
        tag, rest = split_tag(channel_name)
        raw = rest.strip() if tag else re.sub(r"^[^|]*\|\s*", "", channel_name).strip()
        raw = " ".join(strip_decorations(raw).split())
        raw_clean = re.sub(r"\s*(HD|SD|WEST|EAST)\s*$", "", raw, flags=re.IGNORECASE).strip()
        terms = [t for t in dict.fromkeys([core, raw, raw_clean]) if len(t) >= 2]
        found = {}

        def add(i):
            found.setdefault(names[i], pool[names[i]])
            return len(found) >= limit

        for term in terms:  # one name contains the other
            t = term.lower()
            for i, n in enumerate(lower):
                if (t in n or (len(n) >= 3 and n in t)) and add(i):
                    return found
        for term in terms:  # every word of the term appears
            words = [w for w in term.lower().split() if len(w) > 1]
            if words:
                for i, n in enumerate(lower):
                    if all(w in n for w in words) and add(i):
                        return found
        for term in terms:  # closest fuzzy matches
            for _, _, i in process.extract(utils.default_process(term), self._processed[region],
                                           scorer=fuzz.WRatio, processor=None, limit=limit):
                if add(i):
                    return found
        return found


def carry_over_renames(current_names, known):
    """New names that differ from vanished saved names only by decorations, quality tags, punctuation or
    a regrouping (see TAG_ALIASES). Every quality copy of a channel inherits the match, as long as the
    vanished names agree on a single guide ID."""
    current = set(current_names)
    vanished = defaultdict(list)
    for old in known:
        if old in current or old.startswith("#") or not is_priority_channel(old):
            continue
        tag = split_tag(old)[0]
        core = normalize_name(old).split("|", 1)[1]
        for new_tag in TAG_ALIASES.get(tag, (tag,)):
            vanished[f"{new_tag.upper()}|{core}"].append(old)
    new = defaultdict(list)
    for name in dict.fromkeys(current_names):
        if name not in known:
            new[normalize_name(name)].append(name)
    renames = {}
    for key, olds in vanished.items():
        if len({known[o] for o in olds}) == 1:
            for name in new.get(key, []):
                renames[name] = {"from": olds[-1], "id": known[olds[0]]}
    return renames


class Stations:
    """Local TV stations in the guide, by callsign: 'WZTV' -> [('DT', 'WZTV-DT.us_locals1'), ('DT2', ...)]."""

    def __init__(self, valid_ids):
        self.by_call = defaultdict(list)
        for xml_id in valid_ids:
            match = STATION_ID.match(xml_id)
            if match and match.group(1) not in FEED_WORDS:
                self.by_call[match.group(1)].append((match.group(2) or "", xml_id))

    def find(self, call, suffix=None):
        """The station's main feed (-DT, preferring the US locals source), or exactly the requested sub-feed."""
        options = self.by_call.get(call, [])
        if suffix:
            exact = sorted(i for s, i in options if s == suffix)
            return exact[0] if exact else None
        ranked = sorted((STATION_SUFFIX_RANK[s], not i.endswith(".us_locals1"), i)
                        for s, i in options if s in STATION_SUFFIX_RANK)
        return ranked[0][2] if ranked else None


def station_match(channel_name, stations):
    """A local affiliate by callsign: '(WZTV)' in the name, or a bare 'KTVI' next to a network word like FOX."""
    for call, suffix in STATION_IN_BRACKETS.findall(channel_name):
        if call not in FEED_WORDS:
            found = stations.find(call, suffix or None)
            if found:
                return found
    if NETWORK_WORD.search(channel_name):
        for call, subchannel in BARE_STATION.findall(strip_decorations(channel_name)):
            if call in FEED_WORDS or call in BARE_STATION_STOP_WORDS:
                continue
            found = stations.find(call, f"DT{subchannel}" if subchannel else None)
            if subchannel:
                return found  # the named sub-channel or nothing - never the main feed's (other network's) guide
            if found and found.endswith(".us_locals1"):
                return found
    return None


def quick_match(channel_name, pools, expected_country=None, id_countries=None):
    """A strict automatic match: nearly identical name, right country, never a +1 feed, never a generic word,
    never a placeholder. Every guide sharing the display name is considered, so the right country can be found."""
    if NO_GUIDE_PATTERN.search(channel_name):
        return None
    core = extract_core_name(channel_name)
    if len(core) < 3 or core.upper() in GENERIC_CORES:
        return None
    wants_timeshift = bool(TIMESHIFT.search(channel_name))
    for display in pools.close_names(core, AUTO_MATCH_SCORE):
        if bool(TIMESHIFT.search(display)) != wants_timeshift:
            continue
        for xml_id in pools.ids_by_name[display]:
            if not flag_reasons(channel_name, xml_id, expected_country, (id_countries or {}).get(xml_id)):
                return xml_id
    return None


@dataclass
class Resolution:
    matches: dict = field(default_factory=dict)
    how: dict = field(default_factory=dict)
    carried: dict = field(default_factory=dict)
    queue: list = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)


def resolve(names, known, no_guide, by_name, valid_ids, provider_ids=None, rejected=None, legacy=None,
            index=None, expected=None, id_countries=None, max_candidates=10):
    provider_ids = provider_ids or {}
    rejected = rejected or {}
    legacy = legacy or {}
    expected = expected or {}
    id_countries = id_countries or {}
    pools = Pools(by_name, index)
    stations = Stations(valid_ids)
    renames_known = carry_over_renames(names, known)
    renames_legacy = carry_over_renames(names, legacy)
    result = Resolution()

    def accept(name, xml_id, how, count):
        result.matches[name] = xml_id
        result.how[name] = how
        result.counts[count] += 1

    for name in dict.fromkeys(names):
        saved = known.get(name)
        refused = set(rejected.get(name, ()))

        def usable(xml_id, trusted):
            if xml_id not in valid_ids or xml_id in refused:
                return False
            return trusted or (not flag_reasons(name, xml_id, expected.get(name), id_countries.get(xml_id))
                               and (index is None or resembles(name, xml_id, index)))

        old = legacy.get(name)
        rename = renames_known.get(name) or renames_legacy.get(name)
        rename_trusted = name in renames_known
        if saved in valid_ids:
            accept(name, saved, "saved", "known")
        elif name in no_guide:
            result.counts["no_guide"] += 1
        elif NO_GUIDE_PATTERN.search(name):
            result.counts["no_guide_auto"] += 1
        elif (station := station_match(name, stations)) and station not in refused \
                and not flag_reasons(name, station, expected.get(name), id_countries.get(station)):
            accept(name, station, "station", "station")
        elif old and usable(old, trusted=False):
            accept(name, old, "legacy", "legacy")
        elif rename and usable(rename["id"], trusted=rename_trusted):
            accept(name, rename["id"], "renamed", "carried")
            result.carried[name] = rename
        elif (auto := quick_match(name, pools, expected.get(name), id_countries)) and auto not in refused:
            accept(name, auto, "auto", "auto")
        else:
            hint = saved or old or (rename or {}).get("id")
            entry = {"name": name,
                     "reason": "vanished_id" if saved else ("unverified_legacy" if hint else "new"),
                     "candidates": [{"id": i, "name": n}
                                    for n, i in pools.candidates(region_of(name), name, max_candidates).items()]}
            if hint:
                entry["previous_id"] = hint
            if provider_ids.get(name) in valid_ids:
                entry["provider_id"] = provider_ids[name]
            result.queue.append(entry)
            result.counts["queued"] += 1
    return result
