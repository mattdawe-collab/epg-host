import json
from datetime import datetime, timedelta, timezone

import pytest

import epg_cache
import main
import provider
from fixtures_xmltv import make_source


@pytest.fixture
def env(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    cache = tmp_path / "cache"
    cache.mkdir()
    make_source(cache / "a.xml.gz",
                [(i, now - timedelta(minutes=30), now + timedelta(minutes=30), "Show")
                 for i in ("CNN.us", "ESPN.us", "BBCOne.uk")],
                names={"CNN.us": ["CNN"], "ESPN.us": ["ESPN"], "BBCOne.uk": ["BBC One"]})
    monkeypatch.setattr(epg_cache, "SOURCES", [("https://example.invalid/a.xml.gz", "a.xml.gz")])
    for key in ("XC_URL", "XC_USERNAME", "XC_PASSWORD"):
        monkeypatch.setenv(key, "x")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    (tmp_path / "data").mkdir()
    return tmp_path


def write_data(root, known, no_guide=None):
    (root / "data" / "known_matches.json").write_text(json.dumps(known), encoding="utf-8")
    (root / "data" / "no_guide.json").write_text(json.dumps(no_guide or {}), encoding="utf-8")


def run(root, *extra):
    return main.main(["--data-dir", str(root / "data"), "--cache-dir", str(root / "cache"),
                      "--publish-dir", str(root / "publish"), "--cache-max-age", "9999", *extra])


def published(root, name):
    return json.loads((root / "publish" / name).read_text(encoding="utf-8"))


def test_known_mode_builds_and_publishes(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us", "US| ESPN": "ESPN.us", "##### NEWS #####": "x"})
    assert run(env, "--channels-from", "known") == 0
    status = published(env, "status.json")
    assert status["channels"] == 2 and status["channel_list"] == "saved matches"
    assert status["score"]["coverage"] == 1.0 and status["score"]["headline_basis"] == "unaudited"
    assert published(env, "matches.json")["US| CNN HD"] == {"id": "CNN.us", "how": "saved", "flags": []}
    assert published(env, "score_history.json")[-1]["headline"] == 1.0
    assert (env / "publish" / "epg.xml.gz").read_bytes() == (env / "publish" / "data" / "epg_repair.xml.gz").read_bytes()


def test_provider_mode_carries_renames_and_queues_new_channels(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us"})
    monkeypatch.setattr(main.provider, "fetch_channels", lambda *a, **k: [
        {"name": "US| CNN FHD", "epg_id": None}, {"name": "US| MYSTERY", "epg_id": None}, {"name": "FR| TF1", "epg_id": None}])
    assert run(env) == 0
    queue = published(env, "match_queue.json")
    assert [e["name"] for e in queue["queue"]] == ["US| MYSTERY"]
    assert queue["carried"]["US| CNN FHD"]["id"] == "CNN.us"
    assert published(env, "channels.json") == ["US| CNN FHD", "US| MYSTERY"]
    assert published(env, "status.json")["score"]["coverage"] == 0.5
    assert published(env, "status.json")["stale_nights"] == 0


def test_provider_returning_no_channels_uses_fallback_and_returns_3(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us"})
    monkeypatch.setattr(main.provider, "fetch_channels", lambda *a, **k: [])
    assert run(env) == 3
    assert published(env, "status.json")["channel_list"] == "saved matches (provider returned no channels)"


def test_stale_channel_list_escalates_after_three_nights(env, monkeypatch):
    write_data(env, {"US| CNN HD": "CNN.us"})

    def down(*a, **k):
        raise provider.ProviderUnavailable("HTTP 403")

    monkeypatch.setattr(main.provider, "fetch_channels", down)
    previous = env / "previous"
    previous.mkdir()
    (previous / "channels.json").write_text(json.dumps(["US| CNN HD"]), encoding="utf-8")
    (previous / "status.json").write_text(json.dumps({"channels": 1, "stale_nights": 1, "failing_nights": 1}),
                                          encoding="utf-8")
    assert run(env, "--previous-dir", str(previous)) == 0
    assert published(env, "status.json")["failing_nights"] == 2
    (previous / "status.json").write_text(json.dumps({"channels": 1, "stale_nights": 2, "failing_nights": 2}),
                                          encoding="utf-8")
    assert run(env, "--previous-dir", str(previous)) == 3
    assert published(env, "status.json")["stale_nights"] == 3


def test_one_bad_night_after_many_blocked_nights_is_not_an_alarm(env, monkeypatch):
    write_data(env, {"US| CNN HD": "CNN.us"})

    def down(*a, **k):
        raise provider.ProviderUnavailable("ReadTimeout")

    monkeypatch.setattr(main.provider, "fetch_channels", down)
    previous = env / "previous"
    previous.mkdir()
    (previous / "channels.json").write_text(json.dumps(["US| CNN HD"]), encoding="utf-8")
    (previous / "status.json").write_text(json.dumps({"channels": 1, "stale_nights": 9}), encoding="utf-8")
    assert run(env, "--previous-dir", str(previous)) == 0
    status = published(env, "status.json")
    assert status["stale_nights"] == 10 and status["failing_nights"] == 1


def test_names_that_cannot_be_written_to_xml_are_dropped(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us", "US| BAD\x01NAME": "ESPN.us"})
    monkeypatch.setattr(main.provider, "fetch_channels", lambda *a, **k: [
        {"name": "US| CNN HD", "epg_id": None}, {"name": "US| BAD\x01NAME", "epg_id": None}])
    assert run(env) == 0
    assert published(env, "channels.json") == ["US| CNN HD"]


def test_rejected_login_publishes_last_nights_list_and_returns_3(env, monkeypatch):
    write_data(env, {"US| CNN HD": "CNN.us"})

    def reject(*a, **k):
        raise provider.LoginRejected("HTTP 513")

    monkeypatch.setattr(main.provider, "fetch_channels", reject)
    previous = env / "previous"
    previous.mkdir()
    (previous / "channels.json").write_text(json.dumps(["US| CNN HD"]), encoding="utf-8")
    (previous / "status.json").write_text(json.dumps({"channels": 1}), encoding="utf-8")
    (previous / "score_history.json").write_text(json.dumps([{"date": "2026-01-01", "headline": 0.1}]), encoding="utf-8")
    assert run(env, "--previous-dir", str(previous)) == 3
    assert published(env, "status.json")["channel_list"] == "last night's list (login rejected)"
    assert [h["date"] for h in published(env, "score_history.json")][0] == "2026-01-01"


def test_missing_login_returns_3(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    monkeypatch.delenv("XC_PASSWORD")
    write_data(env, {"US| CNN HD": "CNN.us"})
    assert run(env) == 3
    assert published(env, "status.json")["channel_list"] == "saved matches (login not configured)"


def test_failed_checks_return_2_and_publish_nothing(env):
    write_data(env, {"US| CNN HD": "CNN.us"})
    assert run(env, "--channels-from", "known") == 2
    assert not (env / "publish").exists()


def test_expected_country_from_the_playlist_steers_matching(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us"})
    monkeypatch.setattr(main.provider, "fetch_channels", lambda *a, **k: [
        {"name": "#### SPAIN ####", "epg_id": None},
        {"name": "TV: BBC ONE", "epg_id": "bbcone.es"},
        {"name": "TV: OTHER", "epg_id": "other.es"},
        {"name": "US: CNN HD", "epg_id": None}])
    assert run(env) == 0
    matches = published(env, "matches.json")
    assert "TV: BBC ONE" not in matches  # only a .uk guide exists, but the playlist says this channel is Spanish
    assert matches["US: CNN HD"]["id"] == "CNN.us"


def test_provider_blocking_scripts_is_not_an_alarm(env, monkeypatch):
    write_data(env, {"US| CNN HD": "CNN.us"})

    def blocked(*a, **k):
        raise provider.ProviderBlocked("HTTP 403")

    monkeypatch.setattr(main.provider, "fetch_channels", blocked)
    previous = env / "previous"
    previous.mkdir()
    (previous / "channels.json").write_text(json.dumps(["US| CNN HD"]), encoding="utf-8")
    (previous / "status.json").write_text(json.dumps({"channels": 1, "stale_nights": 7}), encoding="utf-8")
    assert run(env, "--previous-dir", str(previous)) == 0
    status = published(env, "status.json")
    assert status["channel_list"] == "last night's list (provider blocks automated access)"
    assert status["stale_nights"] == 8 and status["failing_nights"] == 0


def test_imported_playlist_is_used_when_the_provider_blocks_scripts(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {"US| CNN HD": "CNN.us"})
    (env / "data" / "channels_import.json").write_text(json.dumps({"imported_at": "2026-10-05", "channels": [
        {"name": "##### NEWS #####", "epg_id": None, "group": "US"},
        {"name": "US: CNN HD", "epg_id": "CNN.us", "group": "US"}]}), encoding="utf-8")

    def blocked(*a, **k):
        raise provider.ProviderBlocked("HTTP 403")

    monkeypatch.setattr(main.provider, "fetch_channels", blocked)
    assert run(env) == 0
    status = published(env, "status.json")
    assert status["channel_list"] == "imported playlist from 2026-10-05 (provider blocks automated access)"
    assert published(env, "channels.json") == ["US: CNN HD"]
    assert published(env, "matches.json")["US: CNN HD"]["id"] == "CNN.us"


def test_fallback_prefers_whichever_list_is_newer():
    imported = {"imported_at": "2026-10-05", "channels": [
        {"name": "##### NEWS #####", "epg_id": None, "group": "US"},
        {"name": "US: CNN HD", "epg_id": "CNN.us", "group": "US"}, {"name": "US: FOX NEWS", "epg_id": None, "group": "US"},
        {"name": "US: KTVI", "epg_id": "KTVI.us", "group": "US"}]}
    names, ids, expected, label, date = main.fallback_list([], ["US: OLD"], imported, "2026-09-29")
    assert names == ["US: CNN HD", "US: FOX NEWS", "US: KTVI"] and label == "imported playlist from 2026-10-05"
    assert ids == {"US: CNN HD": "CNN.us", "US: KTVI": "KTVI.us"} and expected["US: FOX NEWS"] == "us" and date == "2026-10-05"
    assert main.fallback_list([], ["US: OLD"], imported, "2026-10-05")[3] == "imported playlist from 2026-10-05"
    assert main.fallback_list([], ["US: OLD"], imported, "2026-10-06")[:5:4] == (["US: OLD"], "2026-10-06")
    assert main.fallback_list(["US| A"], None, None, None)[3] == "saved matches"


def test_a_working_provider_dates_the_list_and_outranks_older_imports(env, monkeypatch):
    monkeypatch.setattr(main.checks, "FIRST_RUN_MIN_CHANNELS", 1)
    write_data(env, {})
    (env / "data" / "channels_import.json").write_text(json.dumps({"imported_at": "2000-01-01", "channels": [
        {"name": "US: OLD", "epg_id": None, "group": "US"}]}), encoding="utf-8")
    monkeypatch.setattr(main.provider, "fetch_channels", lambda *a, **k: [{"name": "US: CNN HD", "epg_id": "CNN.us"}])
    assert run(env) == 0
    status = published(env, "status.json")
    assert status["channel_list"] == "provider" and status["channel_list_date"] == datetime.now(timezone.utc).date().isoformat()
