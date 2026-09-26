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


def write_guide(out_path, matches, source_paths, now, days_ahead=8.0, days_behind=1.0):
    names_by_id = defaultdict(list)
    for name in sorted(matches):
        names_by_id[matches[name]].append(name)
    earliest = now - timedelta(days=days_behind)
    latest = now + timedelta(days=days_ahead)
    next_day = now + timedelta(hours=24)
    seen, upcoming_ids = set(), set()
    programmes = duplicates = out_of_window = 0

    with gzip.open(out_path, "wb") as out, etree.xmlfile(out, encoding="utf-8") as xf:
        xf.write_declaration()
        with xf.element("tv", {"generator-info-name": "epg-bridge"}):
            for name in sorted(matches):
                channel = etree.Element("channel", id=name)
                etree.SubElement(channel, "display-name").text = name
                xf.write(channel)
            for path in source_paths:
                try:
                    with gzip.open(path, "rb") as src:
                        for _, elem in etree.iterparse(src, events=("end",), tag="programme"):
                            xml_id = elem.get("channel")
                            if xml_id in names_by_id:
                                start = parse_xmltv_time(elem.get("start"))
                                stop = parse_xmltv_time(elem.get("stop")) or start
                                key = (xml_id, start.timestamp() if start else elem.get("start"))
                                if start and (stop < earliest or start > latest):
                                    out_of_window += 1
                                elif key in seen:
                                    duplicates += 1
                                else:
                                    seen.add(key)
                                    if start and start < next_day and stop > now:
                                        upcoming_ids.add(xml_id)
                                    for name in names_by_id[xml_id]:
                                        dup = deepcopy(elem)
                                        dup.set("channel", name)
                                        xf.write(dup)
                                        programmes += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                except Exception as e:
                    print(f"    [WARN] Stopped reading {os.path.basename(path)}: {type(e).__name__}: {e}")
    upcoming = sum(len(names_by_id[i]) for i in upcoming_ids)
    return GuideStats(len(matches), programmes, upcoming, duplicates, out_of_window)
