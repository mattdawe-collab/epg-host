"""Send the nightly scorecard to Telegram: published or not, how fresh the guide is, and any guide source that has
stopped updating (epgshare01 froze for three days in October 2026 before anyone noticed).

Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (GitHub secrets, set with tools/set_telegram.py). Without them it
prints the message and skips sending. A Telegram failure never fails the build.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

STALE_HOURS = 36
SOURCE_NAMES = {
    "all_sources.xml.gz": "epgshare01 (main)",
    "us_locals.xml.gz": "epgshare01 US locals",
    "us_sports.xml.gz": "epgshare01 US sports",
    "epg_uk_ripper.xml.gz": "epgshare01 UK",
    "epg_uk_pw.xml.gz": "epg.pw UK",
    "epg_canada_pw.xml.gz": "epg.pw Canada",
    "backup_plex_us.xml.gz": "Plex guide (backup)",
    "backup_us.xml.gz": "iptv-epg.org US (backup)",
    "backup_uk.xml.gz": "iptv-epg.org UK (backup)",
    "backup_ca.xml.gz": "iptv-epg.org Canada (backup)",
}


def _nth_sunday(year, month, n):
    first = datetime(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def mountain(moment):
    """'Sun 25 Oct, 3:02 AM MT'. Daylight time runs from 2 AM on the second Sunday of March to 2 AM on the first
    Sunday of November (the rule in Alberta and the US Mountain zone)."""
    utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
    starts = _nth_sunday(utc.year, 3, 2) + timedelta(hours=2 + 7)   # 2 AM MST in UTC
    ends = _nth_sunday(utc.year, 11, 1) + timedelta(hours=2 + 6)    # 2 AM MDT in UTC
    local = utc - timedelta(hours=6 if starts <= utc < ends else 7)
    hour = local.hour % 12 or 12
    return f"{local:%a} {local.day} {local:%b}, {hour}:{local:%M} {'AM' if local.hour < 12 else 'PM'} MT"


def _parse(value):
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def format_message(report, now, run_url):
    status = report.get("status", {})
    lines = [f"TV guide - {mountain(now)}"]
    trouble = False
    if report.get("published"):
        lines.append("Published")
    else:
        trouble = True
        lines.append(report.get("not_published_reason") or "NOT published - last night's guide stays up")
        lines += [f"- {p}" for p in report.get("problems", [])]
    channels, upcoming = status.get("channels", 0), status.get("channels_with_upcoming", 0)
    fresh = upcoming / channels if channels else 0.0
    line = f"{upcoming:,} of {channels:,} channels have listings for the next 24 hours ({fresh:.1%})"
    last = (report.get("last_night") or {}).get("fresh")
    if last is not None:
        change = (round(fresh, 4) - last) * 100
        if abs(change) >= 0.05:
            line += f", {'up' if change > 0 else 'down'} {abs(change):.1f} points on last night"
        if change <= -5:
            trouble = True
    lines.append(line)
    filled = (status.get("backup") or {}).get("channels_filled", 0)
    if filled:
        lines.append(f"Filled from the backup: {filled:,} channels")
    stale, dated = [], 0
    for filename, value in (status.get("source_updated") or {}).items():
        updated = _parse(value)
        if not updated:
            continue
        dated += 1
        age = now - updated
        if age > timedelta(hours=STALE_HOURS):
            stale.append(f"{SOURCE_NAMES.get(filename, filename)} has not updated since {mountain(updated)} "
                         f"({age.total_seconds() / 86400:.1f} days)")
    if stale:
        trouble = True
        lines += [f"Warning: {s}" for s in stale]
    elif dated:
        lines.append(f"All {dated} guide sources updated in the last {STALE_HOURS} hours")
    if report.get("login_problem"):
        trouble = True
        lines.append(f"Channel list: {report['login_problem']}")
    score = status.get("score") or {}
    queued = (status.get("counts") or {}).get("queued", 0)
    lines.append(f"Score {score.get('headline', 0):.1%} - {queued:,} channels waiting to be matched, "
                 f"guide {status.get('size_mb', 0)} MB")
    if trouble:
        lines.append(run_url)
    return "\n".join(lines)


def message_for(report_path, now, run_url, publish_outcome=None):
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, ValueError):
        return f"TV guide - {mountain(now)}\nThe nightly build did not finish - last night's guide stays up.\n{run_url}"
    if report.get("published") and publish_outcome == "failure":
        report = {**report, "published": False, "not_published_reason": "NOT published - the upload to GitHub failed"}
    return format_message(report, now, run_url)


def send(token, chat_id, text):
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                 json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                                 timeout=30)
        ok = response.status_code == 200 and response.json().get("ok")
    except (requests.RequestException, ValueError) as e:
        print(f"Telegram: could not send ({type(e).__name__})")
        return False
    if not ok:
        print(f"Telegram: refused (HTTP {response.status_code}) - check the bot token and chat ID")
    return bool(ok)


def main(argv=None):
    p = argparse.ArgumentParser(description="Send the nightly scorecard to Telegram.")
    p.add_argument("--report", required=True)
    p.add_argument("--run-url", default="")
    p.add_argument("--publish-outcome", default=None, help="the publish step's outcome (success/failure/skipped)")
    args = p.parse_args(argv)
    text = message_for(args.report, datetime.now(timezone.utc), args.run_url, args.publish_outcome)
    print(text)
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        print("Telegram is not set up (run tools/set_telegram.py on the PC) - nothing sent.")
        return 0
    if send(token, chat_id, text):
        print("Telegram: sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
