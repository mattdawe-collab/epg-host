"""Write the merged XMLTV guide: one channel per provider name, programmes copied from the matched source."""
import gzip
import os
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from lxml import etree


@dataclass
class GuideStats:
    channels: int
    programmes: int
    channels_with_upcoming: int
    skipped_duplicates: int
    skipped_out_of_window: int
    bridged_channels: int = 0  # channel names that got programmes from a backup source (see backup.py)


def parse_xmltv_time(value):
    """'20260926120000 +0000' -> timezone-aware datetime, or None when unreadable."""
    if not value or len(value) < 14:
        return None
    try:
        moment = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    offset = value[14:].strip()
    if len(offset) == 5 and offset[0] in "+-" and offset[1:].isdigit():
        delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        return moment.replace(tzinfo=timezone(delta if offset[0] == "+" else -delta))
    return moment.replace(tzinfo=timezone.utc)


def write_guide(out_path, matches, source_paths, now, days_ahead=8.0, days_behind=1.0, backups=None):
    """backups: [(path, {backup ID: [guide IDs]})], read after the main sources. A guide ID whose own listings end
    within the next 24 hours takes its backup twin's programmes from the moment its own listings end."""
    names_by_id = defaultdict(list)
    for name in sorted(matches):
        names_by_id[matches[name]].append(name)
    earliest = now - timedelta(days=days_behind)
    latest = now + timedelta(days=days_ahead)
    next_day = now + timedelta(hours=24)
    seen, upcoming_ids, bridged_ids = set(), set(), set()
    last_stop = {}
    counts = {"programmes": 0, "duplicates": 0, "out_of_window": 0}

    def copy_programmes(xf, path, target_ids):
        """target_ids(elem, start, stop) -> guide IDs this programme belongs to."""
        try:
            with gzip.open(path, "rb") as src:
                # Sources are third-party files: never let them pull local files in via entities.
                for _, elem in etree.iterparse(src, events=("end",), tag="programme",
                                               resolve_entities="internal", no_network=True):
                    start = parse_xmltv_time(elem.get("start"))
                    stop = parse_xmltv_time(elem.get("stop")) or start
                    for xml_id in target_ids(elem, start, stop):
                        key = (xml_id, start.timestamp() if start else elem.get("start"))
                        if start and (stop < earliest or start > latest):
                            counts["out_of_window"] += 1
                        elif key in seen:
                            counts["duplicates"] += 1
                        else:
                            seen.add(key)
                            if start and start < next_day and stop > now:
                                upcoming_ids.add(xml_id)
                            for name in names_by_id[xml_id]:
                                dup = deepcopy(elem)
                                dup.set("channel", name)
                                xf.write(dup)
                                counts["programmes"] += 1
                            yield xml_id
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
        except Exception as e:
            print(f"    [WARN] Stopped reading {os.path.basename(path)}: {type(e).__name__}: {e}")

    def own_ids(elem, start, stop):
        xml_id = elem.get("channel")
        if xml_id in names_by_id:
            if stop and stop > last_stop.get(xml_id, stop):
                last_stop[xml_id] = stop
            last_stop.setdefault(xml_id, stop)
            return (xml_id,)
        return ()

    with gzip.open(out_path, "wb") as out, etree.xmlfile(out, encoding="utf-8") as xf:
        xf.write_declaration()
        with xf.element("tv", {"generator-info-name": "epg-bridge"}):
            for name in sorted(matches):
                channel = etree.Element("channel", id=name)
                etree.SubElement(channel, "display-name").text = name
                xf.write(channel)
            for path in source_paths:
                for _ in copy_programmes(xf, path, own_ids):
                    pass
            # A channel whose own listings run out in the next 24 hours (or never existed) takes its backup twin's.
            ends = {i: last_stop.get(i) for i in names_by_id if not last_stop.get(i) or last_stop[i] < next_day}
            for path, twins in backups or []:
                twins = {b: [i for i in ids if i in ends] for b, ids in twins.items()}

                def backup_ids(elem, start, stop, twins=twins):
                    if not start:
                        return ()
                    return [i for i in twins.get(elem.get("channel"), ()) if not ends[i] or start >= ends[i]]

                for xml_id in copy_programmes(xf, path, backup_ids):
                    bridged_ids.add(xml_id)
    upcoming = sum(len(names_by_id[i]) for i in upcoming_ids)
    bridged = sum(len(names_by_id[i]) for i in bridged_ids)
    return GuideStats(len(matches), counts["programmes"], upcoming, counts["duplicates"], counts["out_of_window"],
                      bridged)
