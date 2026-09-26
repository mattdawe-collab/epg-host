import gzip
from datetime import datetime, timedelta, timezone

from lxml import etree

import guide
from fixtures_xmltv import make_source

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def read_guide(path):
    with gzip.open(path, "rb") as f:
        root = etree.parse(f).getroot()
    return ([c.get("id") for c in root.findall("channel")],
            [(p.get("channel"), p.findtext("title")) for p in root.findall("programme")])


def test_programmes_copied_to_every_channel_name(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    make_source(src, [("CNN.us", NOW, NOW + HOUR, "News"), ("Other.us", NOW, NOW + HOUR, "Ignored")])
    stats = guide.write_guide(str(out), {"US| CNN HD": "CNN.us", "US| CNN FHD": "CNN.us"}, [str(src)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| CNN FHD", "US| CNN HD"]
    assert programmes == [("US| CNN FHD", "News"), ("US| CNN HD", "News")]
    assert (stats.channels, stats.programmes, stats.channels_with_upcoming) == (2, 2, 2)


def test_duplicate_slots_across_sources_are_dropped(tmp_path):
    a, b, out = tmp_path / "a.xml.gz", tmp_path / "b.xml.gz", tmp_path / "guide.xml.gz"
    make_source(a, [("CNN.us", NOW, NOW + HOUR, "From A")])
    make_source(b, [("CNN.us", NOW, NOW + HOUR, "From B"), ("CNN.us", NOW + HOUR, NOW + 2 * HOUR, "Later B")])
    stats = guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(a), str(b)], NOW)
    assert read_guide(out)[1] == [("US| CNN", "From A"), ("US| CNN", "Later B")]
    assert stats.skipped_duplicates == 1


def test_programmes_outside_window_are_dropped(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    old = NOW - timedelta(days=3)
    soon = NOW + timedelta(days=2)
    far = NOW + timedelta(days=9)
    make_source(src, [("CNN.us", old, old + HOUR, "Old"), ("CNN.us", soon, soon + HOUR, "Soon"),
                      ("CNN.us", far, far + HOUR, "Far")])
    stats = guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(src)], NOW, days_ahead=8)
    assert read_guide(out)[1] == [("US| CNN", "Soon")]
    assert stats.skipped_out_of_window == 2
    assert stats.channels_with_upcoming == 0


def test_special_characters_in_names(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    make_source(src, [("AE.us", NOW, NOW + HOUR, "Show")])
    guide.write_guide(str(out), {"US| A&E <HD> \"East\"": "AE.us"}, [str(src)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| A&E <HD> \"East\""]
    assert programmes == [("US| A&E <HD> \"East\"", "Show")]


def test_corrupt_source_is_skipped(tmp_path):
    good, full, bad, out = (tmp_path / n for n in ("good.xml.gz", "full.xml.gz", "bad.xml.gz", "guide.xml.gz"))
    make_source(good, [("CNN.us", NOW, NOW + HOUR, "Good")])
    make_source(full, [("CNN.us", NOW + i * HOUR, NOW + (i + 1) * HOUR, f"P{i}") for i in range(1, 150)])
    data = full.read_bytes()
    bad.write_bytes(data[: len(data) // 2])
    guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(good), str(bad)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| CNN"]
    assert programmes[0] == ("US| CNN", "Good")


def test_parse_xmltv_time():
    assert guide.parse_xmltv_time("20260926120000 +0000") == NOW
    assert guide.parse_xmltv_time("20260926070000 -0500") == NOW
    assert guide.parse_xmltv_time("20260926120000") == NOW
    assert guide.parse_xmltv_time("garbage") is None
    assert guide.parse_xmltv_time(None) is None
