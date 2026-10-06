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
    assert summary == {"channels": 2, "priority": 2, "with_guide_id": 1, "file_has_login": False}
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


def test_channel_list_link_uses_the_app_login_api_tivimate_uses():
    link = ip.channels_link({"XC_URL": "http://host.example/", "XC_USERNAME": "user1", "XC_PASSWORD": "p@ss w"})
    assert link == "http://host.example/player_api.php?username=user1&password=p%40ss+w&action=get_live_streams"


API_JSON = json.dumps([
    {"num": 1, "name": "##### CBS #####", "stream_type": "live", "stream_id": 1, "epg_channel_id": None,
     "category_id": "7", "direct_source": ""},
    {"num": 2, "name": "US: CBS (KPHO)", "stream_type": "live", "stream_id": 2, "epg_channel_id": "KPHO.us",
     "stream_icon": "http://logo.example/x.png", "category_id": "7", "direct_source": "http://upstream.example/a"},
    {"num": 3, "name": " TV: ST. LOUIS, MO KTVI FOX 2 ", "stream_type": "live", "stream_id": 3, "epg_channel_id": "",
     "category_id": 12},
    {"num": 4, "name": "FR: TF1", "stream_type": "live", "stream_id": 4, "epg_channel_id": "TF1.fr", "category_id": "30"},
    "not a channel",
])


def test_a_saved_app_login_channel_list_is_read():
    assert ip.parse_m3u(API_JSON) == [
        {"name": "##### CBS #####", "epg_id": None, "group": "7"},
        {"name": "US: CBS (KPHO)", "epg_id": "KPHO.us", "group": "7"},
        {"name": "TV: ST. LOUIS, MO KTVI FOX 2", "epg_id": None, "group": "12"},
    ]


def test_a_saved_login_rejection_says_to_update_the_login():
    with pytest.raises(ValueError, match="set_login"):
        ip.parse_m3u('{"user_info": {"auth": 0}}')
    with pytest.raises(ValueError, match="no channels"):
        ip.parse_m3u('{"user_info": {"auth": 1, "status": "Active"}}')
    with pytest.raises(ValueError, match="no channels"):
        ip.parse_m3u("[]")


def test_an_empty_saved_page_says_the_link_returned_nothing():
    with pytest.raises(ValueError, match="empty"):
        ip.parse_m3u("  \r\n")


def test_a_chrome_saved_channel_list_is_found_in_downloads(tmp_path):
    saved = tmp_path / "player_api.php.json"
    saved.write_text(API_JSON, encoding="utf-8")
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")
    assert ip.find_playlist(str(tmp_path)) == str(saved)


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


def test_chrome_and_edge_save_folders_are_watched_as_well_as_downloads(tmp_path):
    downloads, work, other = tmp_path / "Downloads", tmp_path / "Work Folder", tmp_path / "Other"
    for d in (downloads, work, other):
        d.mkdir()
    chrome = tmp_path / "Chrome User Data"
    (chrome / "Profile 2").mkdir(parents=True)
    (chrome / "Local State").write_text(json.dumps({"profile": {"last_used": "Profile 2"}}), encoding="utf-8")
    (chrome / "Profile 2" / "Preferences").write_text(json.dumps({
        "savefile": {"default_directory": str(work)}, "download": {"default_directory": str(other)}}), encoding="utf-8")
    edge = tmp_path / "Edge User Data"
    (edge / "Default").mkdir(parents=True)
    (edge / "Default" / "Preferences").write_text("{broken", encoding="utf-8")
    gone = tmp_path / "Gone User Data"
    (gone / "Default").mkdir(parents=True)
    (gone / "Default" / "Preferences").write_text(json.dumps({"savefile": {"default_directory": str(tmp_path / "x")}}),
                                                  encoding="utf-8")
    folders = ip.save_folders(str(downloads), [str(chrome), str(edge), str(gone), str(tmp_path / "missing")])
    assert folders == [str(downloads), str(work), str(other)]


def test_the_newest_saved_list_across_folders_is_found(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "player_api.php.json").write_text(API_JSON, encoding="utf-8")
    os.utime(a / "player_api.php.json", (1, 1))
    (b / "player_api.json").write_text(API_JSON, encoding="utf-8")
    assert ip.find_playlist([str(a), str(b)]) == str(b / "player_api.json")


def test_waiting_picks_up_a_saved_list_by_its_content_whatever_its_name(tmp_path):
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "big.json.crdownload").write_text(API_JSON, encoding="utf-8")
    (tmp_path / "cf.example_channels.json").write_text(API_JSON, encoding="utf-8")
    found = ip.wait_for_download([str(tmp_path)], since=0, timeout=2, poll=0.01)
    assert found == str(tmp_path / "cf.example_channels.json")


def test_waiting_picks_up_an_empty_saved_page_so_the_user_hears_why(tmp_path):
    (tmp_path / "player_api.php").write_text("", encoding="utf-8")
    assert ip.wait_for_download([str(tmp_path)], since=0, timeout=2, poll=0.01) == str(tmp_path / "player_api.php")


def test_a_channel_list_saved_as_a_complete_web_page_is_still_read():
    import html
    page = ('<html><head><meta name="color-scheme" content="light dark"></head><body>'
            '<pre style="word-wrap: break-word; white-space: pre-wrap;">' + html.escape(API_JSON, quote=False)
            + '</pre></body></html>')
    assert ip.parse_m3u(page) == ip.parse_m3u(API_JSON)
    with pytest.raises(ValueError, match="web page"):
        ip.parse_m3u("<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>Checking</body></html>")


def test_a_login_with_quotes_or_backslashes_is_still_caught(tmp_path):
    src = tmp_path / "list.m3u"
    src.write_text(M3U.replace("US: CBS (KPHO)", r'US: CBS ab"c\d9'), encoding="utf-8")
    with pytest.raises(ValueError, match="login"):
        ip.import_playlist(str(src), str(tmp_path / "out.json"), today="2026-10-05",
                           login={"XC_URL": "http://host.example", "XC_USERNAME": "user1", "XC_PASSWORD": r'ab"c\d9'})


def test_a_fresh_saved_file_that_fails_is_skipped_and_the_browser_opens(tmp_path, monkeypatch, capsys):
    (tmp_path / "player_api.php.json").write_text('{"user_info": {"auth": 0}}', encoding="utf-8")
    opened = []
    monkeypatch.setattr(ip, "save_folders", lambda *a, **k: [str(tmp_path)])
    monkeypatch.setattr(ip, "load_login", lambda: {"XC_URL": "http://h.example", "XC_USERNAME": "u", "XC_PASSWORD": "p"})
    monkeypatch.setattr(ip.webbrowser, "open", opened.append)
    monkeypatch.setattr(ip, "wait_for_download", lambda *a, **k: None)
    monkeypatch.setattr(ip, "OUT", str(tmp_path / "out.json"))
    assert ip.main(["--no-push"]) == 1
    printed = capsys.readouterr().out
    assert len(opened) == 1 and "set_login" in printed and "Work" not in printed


class FakeGit:
    def __init__(self, ahead):
        self.ahead, self.calls = ahead, []

    def __call__(self, *cmd):
        self.calls.append(cmd)
        out = {"rev-parse": "code\n", "rev-list": f"{self.ahead}\n"}.get(cmd[1], "")
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()


def test_an_unchanged_import_still_pushes_a_commit_that_never_reached_github(monkeypatch, tmp_path):
    fake = FakeGit(ahead=1)
    monkeypatch.setattr(ip, "run", fake)
    monkeypatch.setattr(ip, "PENDING", str(tmp_path / "pending"))
    assert ip.push_and_rebuild("2026-10-05") == 0
    names = [c[:2] for c in fake.calls]
    assert ("git", "commit") not in names and ("git", "push") in names and ("gh", "workflow") in names


def test_an_unchanged_import_with_nothing_unpushed_does_nothing(monkeypatch, capsys, tmp_path):
    fake = FakeGit(ahead=0)
    monkeypatch.setattr(ip, "run", fake)
    monkeypatch.setattr(ip, "PENDING", str(tmp_path / "pending"))
    assert ip.push_and_rebuild("2026-10-05") == 0
    assert ("git", "push") not in [c[:2] for c in fake.calls] and "nothing to push" in capsys.readouterr().out


def test_a_rebuild_that_failed_to_start_is_retried_on_the_next_run(monkeypatch, tmp_path):
    pending = tmp_path / "pending"
    monkeypatch.setattr(ip, "PENDING", str(pending))
    failing = FakeGit(ahead=1)
    failing_run = failing.__call__

    def gh_fails(*cmd):
        result = failing_run(*cmd)
        if cmd[0] == "gh":
            result.returncode, result.stderr = 1, "HTTP 502"
        return result

    monkeypatch.setattr(ip, "run", gh_fails)
    assert ip.push_and_rebuild("2026-10-05") == 1 and pending.exists()
    retry = FakeGit(ahead=0)
    monkeypatch.setattr(ip, "run", retry)
    assert ip.push_and_rebuild("2026-10-05") == 0
    assert ("gh", "workflow") in [c[:2] for c in retry.calls] and not pending.exists()


def test_the_user_is_told_when_the_saved_file_holds_their_login(tmp_path):
    src = tmp_path / "player_api.php.html"
    src.write_text("<!-- saved from url=(0080)http://host.example/player_api.php?username=user1&amp;password=secretpw -->"
                   "<html><body><pre>" + API_JSON + "</pre></body></html>", encoding="utf-8")
    login = {"XC_URL": "http://host.example", "XC_USERNAME": "user1", "XC_PASSWORD": "secretpw"}
    summary = ip.import_playlist(str(src), str(tmp_path / "out.json"), today="2026-10-05", login=login)
    assert summary["file_has_login"] is True
    assert "secretpw" not in (tmp_path / "out.json").read_text(encoding="utf-8")
