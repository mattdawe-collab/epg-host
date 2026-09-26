import gzip
import os
import time
from datetime import datetime, timedelta, timezone

from lxml import etree

import epg_cache
from fixtures_xmltv import make_source, xmltv_time

NOW = datetime.now(timezone.utc)


def prog(channel_id):
    return (channel_id, NOW, NOW + timedelta(hours=1), "Show")


class FakeDownload:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body


def test_parse_reads_names_ids_and_index(tmp_path):
    src = tmp_path / "a.xml.gz"
    make_source(src, [prog("CNN.us")], names={"CNN.us": ["CNN", "CNN HD"], "BBCOne.uk": ["BBC One"]})
    by_name, ids, index = epg_cache.parse_epg_channels(str(src))
    assert by_name == {"CNN": "CNN.us", "CNN HD": "CNN.us", "BBC One": "BBCOne.uk"}
    assert ids == {"CNN.us", "BBCOne.uk"}
    assert index == {"CNN.us": ["CNN", "CNN HD"], "BBCOne.uk": ["BBC One"]}


def test_parse_stops_at_first_programme(tmp_path):
    root = etree.Element("tv")
    etree.SubElement(etree.SubElement(root, "channel", id="A.us"), "display-name").text = "A"
    etree.SubElement(root, "programme", start=xmltv_time(NOW), stop=xmltv_time(NOW), channel="A.us")
    etree.SubElement(etree.SubElement(root, "channel", id="B.us"), "display-name").text = "B"
    src = tmp_path / "odd.xml.gz"
    with gzip.open(src, "wb") as f:
        f.write(etree.tostring(root))
    _, ids, _ = epg_cache.parse_epg_channels(str(src))
    assert ids == {"A.us"}


def test_fetch_reports_status_and_first_source_wins(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    make_source(cache / "fresh.xml.gz", [prog("CNN.us")], names={"CNN.us": ["CNN"]})
    make_source(cache / "old.xml.gz", [prog("CNN2.us")], names={"CNN2.us": ["CNN", "CNN Two"]})
    old = time.time() - 48 * 3600
    os.utime(cache / "old.xml.gz", (old, old))
    monkeypatch.setattr(epg_cache, "download_file", lambda url, dest, timeout=120: False)
    sources = [("https://example.invalid/1", "fresh.xml.gz"), ("https://example.invalid/2", "old.xml.gz"),
               ("https://example.invalid/3", "none.xml.gz")]
    ref = epg_cache.fetch_reference_data(sources, str(cache), cache_max_age_hours=24)
    assert ref.source_status == {"fresh.xml.gz": "cached", "old.xml.gz": "stale cache", "none.xml.gz": "failed"}
    assert ref.by_name == {"CNN": "CNN.us", "CNN Two": "CNN2.us"}
    assert ref.valid_ids == {"CNN.us", "CNN2.us"}
    assert ref.index == {"CNN.us": ["CNN"], "CNN2.us": ["CNN", "CNN Two"]}
    assert ref.paths == [os.path.join(str(cache), "fresh.xml.gz"), os.path.join(str(cache), "old.xml.gz")]


def test_fetch_downloads_when_cache_missing(tmp_path, monkeypatch):
    def fake_download(url, dest, timeout=120):
        make_source(dest, [prog("ESPN.us")], names={"ESPN.us": ["ESPN"]})
        return True

    monkeypatch.setattr(epg_cache, "download_file", fake_download)
    ref = epg_cache.fetch_reference_data([("https://example.invalid/a", "a.xml.gz")], str(tmp_path), 24)
    assert ref.source_status == {"a.xml.gz": "downloaded"}
    assert ref.valid_ids == {"ESPN.us"}


def test_download_rejects_non_gzip_and_keeps_old_file(tmp_path, monkeypatch):
    dest = tmp_path / "a.xml.gz"
    dest.write_bytes(b"\x1f\x8bOLD")
    monkeypatch.setattr(epg_cache.requests, "get", lambda *a, **k: FakeDownload(b"<html>blocked</html>"))
    assert epg_cache.download_file("https://example.invalid/a", str(dest)) is False
    assert dest.read_bytes() == b"\x1f\x8bOLD"
    assert not (tmp_path / "a.xml.gz.part").exists()


def test_download_saves_gzip(tmp_path, monkeypatch):
    dest = tmp_path / "a.xml.gz"
    monkeypatch.setattr(epg_cache.requests, "get", lambda *a, **k: FakeDownload(b"\x1f\x8bNEW"))
    assert epg_cache.download_file("https://example.invalid/a", str(dest)) is True
    assert dest.read_bytes() == b"\x1f\x8bNEW"


def test_sources_drop_dead_epghub():
    assert len(epg_cache.SOURCES) == 9
    assert not any("epghub.xyz" in url for url, _ in epg_cache.SOURCES)
