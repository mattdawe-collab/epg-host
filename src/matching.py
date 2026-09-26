"""Match provider channel names to guide channel IDs without AI:
saved decisions, simple renames, and exact or fuzzy display-name matches."""
import re
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
REGION_PREFIXES = {
    "CA": ("CA| ", "CA: ", "CA EN: ", "CA FR: "),
    "US": ("US| ", "SLING| ", "US: ", "AT&T: ", "TV: "),
    "UK": ("UK| ", "UK-BBCI| ", "UK-NOWTV| ", "UK: ", "NOW: "),
}
_PREFIXES_LONGEST_FIRST = sorted(PRIORITY_PREFIXES, key=len, reverse=True)
PREFIX_WORDS = {p[:-2].strip().upper() for p in PRIORITY_PREFIXES} | {"EU", "LOCALS", "CHANNELS"}
AUTO_MATCH_SCORE = 93
SUPERSCRIPT_TAGS = re.compile(r"[ᴴᴰᵁᴴᴰ⁴ᴷˢᵈ¹⁰⁸⁰ᵖᶜᴿᵃᴰ]+")
QUALITY_WORDS = re.compile(r"\b(HD|SD|UHD|FHD|4K|HEVC|H264|H265|1080P|720P|60FPS)\b", re.IGNORECASE)


def is_priority_channel(name):
    return name.startswith(PRIORITY_PREFIXES)


def split_tag(name):
    """('US', 'CNN HD') for 'US: CNN HD' or 'US| CNN HD'; ('', name) when there is no known group tag."""
    for prefix in _PREFIXES_LONGEST_FIRST:
        if name.startswith(prefix):
            return prefix[:-2].strip(), name[len(prefix):]
    return "", name


def extract_core_name(channel_name):
    """The part of a decorated IPTV name that identifies the channel: a callsign if present."""
    callsign = re.search(r"\(([A-Z]{4,5})\)", channel_name)
    if callsign:
        return callsign.group(1)
    clean = SUPERSCRIPT_TAGS.sub("", split_tag(channel_name)[1])
    clean = QUALITY_WORDS.sub("", clean)
    clean = re.sub(r"^[#|]+\s*", "", clean)
    clean = re.sub(r"\s*[#|]+$", "", clean)
    parts = [p.strip() for p in clean.split("|") if p.strip() and p.strip().upper() not in PREFIX_WORDS]
    if parts:
        return re.sub(r"[|#]+", " ", parts[0]).strip()
    return channel_name.strip()


def normalize_name(name):
    """Prefix plus name with quality tags and punctuation removed: 'US| CNN HD' -> 'US|CNN'."""
    prefix, rest = split_tag(name)
    if not prefix:
        prefix, sep, rest = name.partition("| ")
        if not sep:
            prefix, rest = "", name
    rest = QUALITY_WORDS.sub(" ", SUPERSCRIPT_TAGS.sub(" ", rest))
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


class Pools:
    """Display-name pools per region, prepared once for fast searching."""

    def __init__(self, by_name):
        regional = {r: {n: i for n, i in by_name.items() if is_region(i, r.lower())} for r in ("US", "CA", "UK")}
        self.maps = {r: (m or by_name) for r, m in regional.items()}
        self.maps["ALL"] = by_name
        self._names = {r: list(m) for r, m in self.maps.items()}
        self._lower = {r: [n.lower() for n in names] for r, names in self._names.items()}
        self._processed = {r: [utils.default_process(n) for n in names] for r, names in self._names.items()}

    def best(self, region, text, cutoff):
        hit = process.extractOne(utils.default_process(text), self._processed[region],
                                 scorer=fuzz.WRatio, processor=None, score_cutoff=cutoff)
        if not hit:
            return None
        name = self._names[region][hit[2]]
        return name, self.maps[region][name]

    def candidates(self, region, channel_name, limit=10):
        names, lower, pool = self._names[region], self._lower[region], self.maps[region]
        core = extract_core_name(channel_name)
        tag, rest = split_tag(channel_name)
        raw = rest.strip() if tag else re.sub(r"^[^|]*\|\s*", "", channel_name).strip()
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
    """New names that differ from vanished saved names only by quality tags, punctuation or a regrouping
    (see TAG_ALIASES). Every quality copy of a channel inherits the match, as long as the vanished
    names agree on a single guide ID."""
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
    core = extract_core_name(channel_name)
    if core in by_name:
        return by_name[core]
    hit = pools.best(region_of(channel_name), core, AUTO_MATCH_SCORE)
    return hit[1] if hit else None


@dataclass
class Resolution:
    matches: dict = field(default_factory=dict)
    how: dict = field(default_factory=dict)
    carried: dict = field(default_factory=dict)
    queue: list = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)


def resolve(names, known, no_guide, by_name, valid_ids, provider_ids=None, rejected=None, max_candidates=10):
    provider_ids = provider_ids or {}
    rejected = rejected or {}
    pools = Pools(by_name)
    renames = carry_over_renames(names, known)
    result = Resolution()

    def accept(name, xml_id, how, count):
        result.matches[name] = xml_id
        result.how[name] = how
        result.counts[count] += 1

    for name in dict.fromkeys(names):
        saved = known.get(name)
        refused = set(rejected.get(name, ()))
        rename = renames.get(name)
        if saved in valid_ids:
            accept(name, saved, "saved", "known")
        elif name in no_guide:
            result.counts["no_guide"] += 1
        elif rename and rename["id"] in valid_ids and rename["id"] not in refused:
            accept(name, rename["id"], "renamed", "carried")
            result.carried[name] = rename
        elif (auto := quick_match(name, by_name, pools)) and auto not in refused:
            accept(name, auto, "auto", "auto")
        else:
            entry = {"name": name, "reason": "vanished_id" if saved else "new",
                     "candidates": [{"id": i, "name": n}
                                    for n, i in pools.candidates(region_of(name), name, max_candidates).items()]}
            if saved:
                entry["previous_id"] = saved
            if provider_ids.get(name) in valid_ids:
                entry["provider_id"] = provider_ids[name]
            result.queue.append(entry)
            result.counts["queued"] += 1
    return result
