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
NETWORKS = ("ABC", "CBS", "NBC", "FOX", "CW", "PBS")
HOME_COUNTRIES = {"US": {"us"}, "CA": {"ca"}, "UK": {"uk", "gb"}}
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
    rest = QUALITY_WORDS.sub(" ", strip_decorations(rest).replace("+", " PLUS "))
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


def flag_reasons(name, xml_id):
    """Free checks for a probably-wrong match: wrong country, wrong callsign, wrong network."""
    reasons = []
    region = region_of(name)
    country = COUNTRY_SUFFIX.match(xml_id.rsplit(".", 1)[-1].lower()) if "." in xml_id else None
    if region in HOME_COUNTRIES and country and country.group(1) not in HOME_COUNTRIES[region]:
        reasons.append("region")
    if any(c not in FEED_WORDS and c not in xml_id.upper() for c in CALLSIGN_IN_NAME.findall(name)):
        reasons.append("callsign")
    in_name = {n for n in NETWORKS if re.search(rf"\b{n}\b", name.upper())}
    in_id = {n for n in NETWORKS if n in xml_id.upper()}
    if in_name and in_id and not (in_name & in_id):
        reasons.append("network")
    return reasons


class Pools:
    """Display-name pools per region, prepared once for fast searching."""

    def __init__(self, by_name):
        regional = {r: {n: i for n, i in by_name.items() if is_region(i, r.lower())} for r in ("US", "CA", "UK")}
        self.maps = {r: (m or by_name) for r, m in regional.items()}
        self.maps["ALL"] = by_name
        self._names = {r: list(m) for r, m in self.maps.items()}
        self._lower = {r: [n.lower() for n in names] for r, names in self._names.items()}
        self._processed = {r: [utils.default_process(n) for n in names] for r, names in self._names.items()}

    def close(self, region, text, cutoff, limit=5):
        """Display names nearly identical to text (plain ratio, no partial matching), best first."""
        hits = process.extract(utils.default_process(text), self._processed[region],
                               scorer=fuzz.ratio, processor=None, score_cutoff=cutoff, limit=limit)
        return [(self._names[region][i], self.maps[region][self._names[region][i]]) for _, _, i in hits]

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


def quick_match(channel_name, by_name, pools):
    """A strict automatic match: same country, nearly identical name, never a +1 feed, never a generic word."""
    if NO_GUIDE_PATTERN.search(channel_name):
        return None
    core = extract_core_name(channel_name)
    if len(core) < 3 or core.upper() in GENERIC_CORES:
        return None
    region = region_of(channel_name)
    wants_timeshift = bool(TIMESHIFT.search(channel_name))

    def acceptable(display, xml_id):
        return bool(TIMESHIFT.search(display)) == wants_timeshift and not flag_reasons(channel_name, xml_id)

    pool = pools.maps[region]
    if core in pool and acceptable(core, pool[core]):
        return pool[core]
    for display, xml_id in pools.close(region, core, AUTO_MATCH_SCORE):
        if acceptable(display, xml_id):
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
            max_candidates=10):
    provider_ids = provider_ids or {}
    rejected = rejected or {}
    legacy = legacy or {}
    pools = Pools(by_name)
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
            return (xml_id in valid_ids and xml_id not in refused
                    and (trusted or not flag_reasons(name, xml_id)))

        old = legacy.get(name)
        rename = renames_known.get(name) or renames_legacy.get(name)
        rename_trusted = name in renames_known
        if saved in valid_ids:
            accept(name, saved, "saved", "known")
        elif name in no_guide:
            result.counts["no_guide"] += 1
        elif NO_GUIDE_PATTERN.search(name):
            result.counts["no_guide_auto"] += 1
        elif old and usable(old, trusted=False):
            accept(name, old, "legacy", "legacy")
        elif rename and usable(rename["id"], trusted=rename_trusted):
            accept(name, rename["id"], "renamed", "carried")
            result.carried[name] = rename
        elif (auto := quick_match(name, by_name, pools)) and auto not in refused:
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
