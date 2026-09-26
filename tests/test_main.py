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
