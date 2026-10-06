import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import import_playlist as ip  # noqa: E402

M3U = '''#EXTM3U
#EXTINF:-1 tvg-id="" tvg-name="##### CBS #####" tvg-logo="" group-title="US| CBS HD",##### CBS #####
http://host.example:80/user1/secretpw/1.ts
#EXTINF:-1 tvg-id="KPHO.us" tvg-name="US: CBS (KPHO)" tvg-logo="http://logo.example/x.png" group-title="US| CBS HD",US: CBS (KPHO)
http://host.example:80/user1/secretpw/2.ts
#EXTINF:-1 tvg-id="" tvg-name="TV: ST. LOUIS, MO KTVI FOX 2" group-title="TV",TV: ST. LOUIS, MO KTVI FOX 2
http://host.example:80/user1/secretpw/3.ts
'''


def test_parse_keeps_order_headers_and_commas_and_drops_urls():
    entries = ip.parse_m3u(M3U)
    assert entries == [
        {"name": "##### CBS #####", "epg_id": None, "group": "US| CBS HD"},
        {"name": "US: CBS (KPHO)", "epg_id": "KPHO.us", "group": "US| CBS HD"},
        {"name": "TV: ST. LOUIS, MO KTVI FOX 2", "epg_id": None, "group": "TV"},
    ]
    dumped = json.dumps(entries)
    assert "secretpw" not in dumped and "host.example" not in dumped and "user1" not in dumped


def test_a_saved_web_page_is_refused():
    with pytest.raises(ValueError, match="web page"):
        ip.parse_m3u("<!DOCTYPE html><html><body>Just a moment...</body></html>")


def test_a_playlist_without_channels_is_refused():
    with pytest.raises(ValueError, match="no channels"):
        ip.parse_m3u("#EXTM3U\n")


def test_import_writes_only_names_ids_and_groups(tmp_path):
    src = tmp_path / "tv_channels.m3u"
    src.write_text(M3U, encoding="utf-8")
    out = tmp_path / "data" / "channels_import.json"
    summary = ip.import_playlist(str(src), str(out), today="2026-10-05")
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert doc["imported_at"] == "2026-10-05" and len(doc["channels"]) == 3
    assert summary == {"channels": 2, "priority": 2, "with_guide_id": 1}
    assert "secretpw" not in text and "host.example" not in text


def test_the_newest_playlist_in_a_folder_is_found(tmp_path):
    old = tmp_path / "old.m3u"
    old.write_text(M3U, encoding="utf-8")
    new = tmp_path / "get.php"
    new.write_text(M3U, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a playlist", encoding="utf-8")
    os.utime(old, (1, 1))
    assert ip.find_playlist(str(tmp_path)) == str(new)
    assert ip.find_playlist(str(tmp_path / "missing")) is None


def test_download_link_is_built_from_the_saved_login_without_printing_it():
    link = ip.playlist_link({"XC_URL": "http://host.example/", "XC_USERNAME": "user1", "XC_PASSWORD": "p@ss w"})
    assert link == "http://host.example/get.php?username=user1&password=p%40ss+w&type=m3u_plus&output=ts"


def test_main_imports_a_given_file_without_pushing(tmp_path, monkeypatch, capsys):
    src = tmp_path / "list.m3u"
    src.write_text(M3U, encoding="utf-8")
    out = tmp_path / "channels_import.json"
    monkeypatch.setattr(ip, "OUT", str(out))
    assert ip.main([str(src), "--no-push"]) == 0
    assert out.exists()
    printed = capsys.readouterr().out
    assert "2 channels" in printed and "secretpw" not in printed


def test_movies_and_series_in_the_playlist_are_skipped():
    text = M3U + ('#EXTINF:-1 tvg-name="US: Some Movie (2020)" group-title="VOD",US: Some Movie (2020)\n'
                  'http://host.example:80/movie/user1/secretpw/9.mp4\n'
                  '#EXTINF:-1 tvg-name="US: A Show S01 E01" group-title="Series",US: A Show S01 E01\n'
                  'http://host.example:80/series/user1/secretpw/10.mkv\n')
    assert [e["name"] for e in ip.parse_m3u(text)][-1] == "TV: ST. LOUIS, MO KTVI FOX 2"


def test_sections_without_wanted_channels_are_dropped():
    text = M3U + ('#EXTINF:-1 tvg-name="##### FRANCE #####" group-title="FR",##### FRANCE #####\nhttp://h/u/p/7.ts\n'
                  '#EXTINF:-1 tvg-name="FR: TF1" group-title="FR",FR: TF1\nhttp://h/u/p/8.ts\n')
    assert [e["name"] for e in ip.parse_m3u(text)] == [
        "##### CBS #####", "US: CBS (KPHO)", "TV: ST. LOUIS, MO KTVI FOX 2"]


def test_import_refuses_to_write_anything_containing_the_login(tmp_path):
    src = tmp_path / "list.m3u"
    src.write_text(M3U.replace("US: CBS (KPHO)", "US: CBS user1"), encoding="utf-8")
    out = tmp_path / "channels_import.json"
    with pytest.raises(ValueError, match="login"):
        ip.import_playlist(str(src), str(out), today="2026-10-05",
                           login={"XC_URL": "http://host.example", "XC_USERNAME": "user1", "XC_PASSWORD": "secretpw"})
    assert not out.exists()
