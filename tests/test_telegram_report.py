"""The nightly Telegram scorecard."""
import json
from datetime import datetime, timezone

import pytest

import telegram_report as tr

NOW = datetime(2026, 10, 25, 9, 2, tzinfo=timezone.utc)  # 3:02 AM MDT


def report(published=True, problems=(), fresh=3703, channels=3813, filled=41, updated=None, login_problem=None,
           last_night_fresh=0.8419):
    return {
        "published": published, "problems": list(problems), "login_problem": login_problem,
        "last_night": {"date": "2026-10-24", "fresh": last_night_fresh} if last_night_fresh is not None else None,
        "status": {
            "generated_at": NOW.isoformat(), "channels": channels, "channels_with_upcoming": fresh,
            "size_mb": 22.5, "counts": {"queued": 3774},
            "score": {"headline": 0.4881, "coverage": 0.5026, "fresh": round(fresh / channels, 4)},
            "backup": {"channels_filled": filled},
            "source_updated": updated if updated is not None else {
                "all_sources.xml.gz": "2026-10-24T22:40:35+00:00", "us_locals.xml.gz": "2026-10-24T22:41:07+00:00"},
        },
    }


def test_mountain_time_follows_daylight_saving():
    assert tr.mountain(datetime(2026, 10, 25, 9, 2, tzinfo=timezone.utc)) == ("Sun 25 Oct, 3:02 AM MT")
    assert tr.mountain(datetime(2026, 12, 1, 15, 30, tzinfo=timezone.utc)) == ("Tue 1 Dec, 8:30 AM MT")
    assert tr.mountain(datetime(2026, 3, 8, 8, 59, tzinfo=timezone.utc)) == ("Sun 8 Mar, 1:59 AM MT")   # MST
    assert tr.mountain(datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc)) == ("Sun 8 Mar, 3:00 AM MT")    # MDT
    assert tr.mountain(datetime(2026, 11, 1, 7, 59, tzinfo=timezone.utc)) == ("Sun 1 Nov, 1:59 AM MT")  # MDT
    assert tr.mountain(datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)) == ("Sun 1 Nov, 1:00 AM MT")   # MST


def test_a_good_night_is_short_and_says_published():
    text = tr.format_message(report(), NOW, "https://run")
    assert text.splitlines()[0] == "TV guide - Sun 25 Oct, 3:02 AM MT"
    assert "Published" in text and "NOT" not in text
    assert "3,703 of 3,813 channels have listings for the next 24 hours (97.1%)" in text
    assert "up 12.9 points on last night" in text
    assert "Filled from the backup: 41 channels" in text
    assert "All 2 guide sources updated in the last 36 hours" in text
    assert "https://run" not in text  # the link only matters when something is wrong


def test_a_refused_build_says_why_and_links_the_run():
    text = tr.format_message(report(published=False, fresh=982, last_night_fresh=0.9489,
                                    problems=["only 982 of 3,813 channels have programmes in the next 24 hours"]),
                             NOW, "https://run")
    assert "NOT published - last night's guide stays up" in text
    assert "- only 982 of 3,813 channels have programmes in the next 24 hours" in text
    assert "down 69.1 points on last night" in text
    assert text.rstrip().endswith("https://run")


def test_a_source_that_stopped_updating_is_named_with_its_age():
    text = tr.format_message(report(updated={"all_sources.xml.gz": "2026-10-21T16:39:17+00:00",
                                             "us_locals.xml.gz": "2026-10-24T22:41:07+00:00",
                                             "globetv_canada1.xml.gz": None}), NOW, "https://run")
    assert "epgshare01 (main) has not updated since Wed 21 Oct, 10:39 AM MT (3.7 days)" in text
    assert "us_locals" not in text and "globetv" not in text
    assert text.rstrip().endswith("https://run")


def test_login_problem_is_reported():
    text = tr.format_message(report(login_problem="The IPTV login is not configured - run tools/set_login.py"),
                             NOW, "https://run")
    assert "Channel list: The IPTV login is not configured - run tools/set_login.py" in text


def test_missing_report_means_the_build_crashed(tmp_path):
    text = tr.message_for(str(tmp_path / "missing.json"), NOW, "https://run", publish_outcome="skipped")
    assert "did not finish" in text and "https://run" in text


def test_publish_step_failure_overrides_a_good_build(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report()), encoding="utf-8")
    text = tr.message_for(str(path), NOW, "https://run", publish_outcome="failure")
    assert "NOT published - the upload to GitHub failed" in text


def test_send_posts_plain_text(monkeypatch):
    sent = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True}

    def fake_post(url, json=None, timeout=None):
        sent.update(url=url, payload=json)
        return Response()

    monkeypatch.setattr(tr.requests, "post", fake_post)
    assert tr.send("123:ABC", "42", "hello") is True
    assert sent["url"] == "https://api.telegram.org/bot123:ABC/sendMessage"
    assert sent["payload"] == {"chat_id": "42", "text": "hello", "disable_web_page_preview": True}


def test_cli_skips_quietly_when_telegram_is_not_set_up(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert tr.main(["--report", str(tmp_path / "r.json"), "--run-url", "u"]) == 0
    assert "not set up" in capsys.readouterr().out
