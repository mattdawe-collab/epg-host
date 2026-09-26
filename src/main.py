"""Nightly EPG build: channel list -> matches (no AI) -> guide -> checks -> scorecard -> publish folder.

Exit codes: 0 published; 2 checks failed, nothing published; 3 published, but from a fallback channel
list that needs attention (login rejected or missing, no channels returned, or stale for several nights).
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import checks
import console_ui as ui
import epg_cache
import guide
import matching
import provider
import publish
import score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIM_DAYS = 5.0
STALE_NIGHTS_LIMIT = 3
LOGIN_HELP = "run tools/set_login.py on the PC"
NOT_XML_SAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def parse_args(argv):
    p = argparse.ArgumentParser(description="Build the EPG guide.")
    p.add_argument("--channels-from", choices=["provider", "known"], default="provider")
    p.add_argument("--previous-dir", help="last night's published files (channels.json, status.json, score_history.json)")
    p.add_argument("--publish-dir", default=os.path.join(ROOT, "publish"))
    p.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    p.add_argument("--cache-dir", default=os.path.join(ROOT, "data", "cache"))
    p.add_argument("--cache-max-age", type=float, default=float(os.getenv("CACHE_MAX_AGE", "24")))
    p.add_argument("--days-ahead", type=float, default=8.0)
    return p.parse_args(argv)


def load_json(path, default):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_channel_list(mode, known, previous_channels):
    """Return (names, provider_ids, expected_countries, description, login_problem). `known` holds every saved name."""
    saved = [n for n in known if not n.startswith("#") and matching.is_priority_channel(n)]
    if mode == "known":
        return saved, {}, {}, "saved matches", None
    fallback = previous_channels or saved
    label = "last night's list" if previous_channels else "saved matches"
    url, user, password = (os.getenv(k, "").strip() for k in ("XC_URL", "XC_USERNAME", "XC_PASSWORD"))
    if not (url and user and password):
        return fallback, {}, {}, f"{label} (login not configured)", f"The IPTV login is not configured - {LOGIN_HELP}."
    try:
        channels = provider.fetch_channels(url, user, password)
    except provider.LoginRejected as e:
        return fallback, {}, {}, f"{label} (login rejected)", (
            f"The provider rejected the IPTV login ({e}). If the same login works on the PC, the provider "
            f"is blocking GitHub; otherwise {LOGIN_HELP}.")
    except provider.ProviderUnavailable as e:
        ui.warn(f"Provider unavailable ({e}) - using {label}")
        return fallback, {}, {}, f"{label} (provider unavailable)", None
    names = [c["name"] for c in channels if matching.is_priority_channel(c["name"])]
    if not names:
        return fallback, {}, {}, f"{label} (provider returned no channels)", (
            f"The provider returned no channels - the account may have expired. Check it, then {LOGIN_HELP}.")
    provider_ids = {c["name"]: c["epg_id"] for c in channels if c["epg_id"]}
    return names, provider_ids, matching.expected_countries(channels), "provider", None


def pct(value):
    return "not audited yet" if value is None else f"{value:.1%}"


def write_step_summary(status, problems, login_problem):
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    counts, card = status["counts"], status["score"]
    lines = ["## EPG guide build", ""]
    lines += [f"**Not published:** {p}" for p in problems]
    if login_problem:
        lines.append(f"**Login problem:** {login_problem}")
    lines += [
        f"**Score: {card['headline']:.1%}** ({card['headline_basis']}) - coverage {pct(card['coverage'])}, "
        f"fresh {pct(card['fresh'])}, accuracy {pct(card['accuracy'])}, flagged {card['flagged']:,}",
        "",
        f"- Channel list: {status['channel_list']}",
        f"- Guide: {status['channels']:,} channels, {status['programmes']:,} programmes, {status['size_mb']} MB",
        f"- Matched: {counts.get('known', 0):,} saved, {counts.get('legacy', 0):,} legacy, "
        f"{counts.get('carried', 0):,} renamed, {counts.get('auto', 0):,} automatic",
        f"- Waiting for a Claude matching session: {counts.get('queued', 0):,} (no guide: "
        f"{counts.get('no_guide', 0) + counts.get('no_guide_auto', 0):,})",
        f"- Added / removed since last night: {status['added_count']:,} / {status['removed_count']:,}",
        "- Sources: " + ", ".join(f"{k} {v}" for k, v in status["sources"].items()),
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    args = parse_args(argv)
    started = time.time()
    now = datetime.now(timezone.utc)
    ui.banner("EPG BRIDGE")

    known = load_json(os.path.join(args.data_dir, "known_matches.json"), {})
    legacy = load_json(os.path.join(args.data_dir, "legacy_matches.json"), {})
    no_guide = load_json(os.path.join(args.data_dir, "no_guide.json"), {})
    rejected = load_json(os.path.join(args.data_dir, "rejected_matches.json"), {})
    audit_log = load_json(os.path.join(args.data_dir, "audit_log.json"), [])
    prev = args.previous_dir
    previous_channels = load_json(prev and os.path.join(prev, "channels.json"), None)
    previous_status = load_json(prev and os.path.join(prev, "status.json"), {})
    previous_history = load_json(prev and os.path.join(prev, "score_history.json"), [])

    ui.step(1, 5, "Channel list")
    names, provider_ids, expected, list_source, login_problem = get_channel_list(args.channels_from, {**legacy, **known}, previous_channels)
    unwritable = [n for n in names if NOT_XML_SAFE.search(n)]
    if unwritable:
        ui.warn(f"Skipping {len(unwritable)} channel name(s) with characters XML cannot hold")
    names = [n for n in dict.fromkeys(names) if not NOT_XML_SAFE.search(n)]
    ui.info(f"{len(names):,} channels from {list_source}")
    stale = args.channels_from == "provider" and list_source != "provider"
    stale_nights = previous_status.get("stale_nights", 0) + 1 if stale else 0
    if stale_nights >= STALE_NIGHTS_LIMIT and not login_problem:
        login_problem = (f"The channel list has not been refreshed for {stale_nights} nights ({list_source}). "
                         f"If the same login works on the PC, the provider may be blocking GitHub.")

    ui.step(2, 5, "Guide sources")
    ref = epg_cache.fetch_reference_data(epg_cache.SOURCES, args.cache_dir, args.cache_max_age)

    ui.step(3, 5, "Matching (no AI)")
    result = matching.resolve(names, known, no_guide, ref.by_name, ref.valid_ids, provider_ids, rejected, legacy,
                              index=ref.index, expected=expected, id_countries=ref.id_country)
    ui.info(", ".join(f"{k}: {v:,}" for k, v in sorted(result.counts.items())))

    ui.step(4, 5, "Building guide")
    build_path = os.path.join(args.cache_dir, "guide_build.xml.gz")
    days = args.days_ahead
    stats = guide.write_guide(build_path, result.matches, ref.paths, now, days_ahead=days)
    size = os.path.getsize(build_path)
    if size > checks.MAX_BYTES and days > TRIM_DAYS:
        ui.warn(f"Guide is {size / 1048576:.0f} MB - trimming to {TRIM_DAYS:g} days ahead")
        days = TRIM_DAYS
        stats = guide.write_guide(build_path, result.matches, ref.paths, now, days_ahead=days)
        size = os.path.getsize(build_path)

    settled = result.counts["no_guide"] + result.counts["no_guide_auto"]
    card = score.scorecard(len(names), result.matches, stats, audit_log, settled_no_guide=settled, expected=expected,
                           id_countries=ref.id_country)
    history = score.update_history(previous_history, now.date().isoformat(), card)
    previous_names = set(previous_channels or [])
    added = sorted(set(names) - previous_names) if previous_channels else []
    removed = sorted(previous_names - set(names)) if previous_channels else []
    status = {
        "generated_at": now.isoformat(timespec="seconds"),
        "channel_list": list_source,
        "stale_nights": stale_nights,
        "channels": stats.channels,
        "programmes": stats.programmes,
        "channels_with_upcoming": stats.channels_with_upcoming,
        "size_mb": round(size / 1048576, 1),
        "days_ahead": days,
        "counts": dict(result.counts),
        "score": {**{k: v for k, v in card.items() if k != "flags"},
                  "flag_examples": dict(list(card["flags"].items())[:20])},
        "added_count": len(added), "added": added[:100],
        "removed_count": len(removed), "removed": removed[:100],
        "sources": ref.source_status,
        "skipped_duplicate_programmes": stats.skipped_duplicates,
        "skipped_out_of_window_programmes": stats.skipped_out_of_window,
        "elapsed_minutes": round((time.time() - started) / 60, 1),
    }
    ui.info(f"Score {card['headline']:.1%} ({card['headline_basis']}): coverage {pct(card['coverage'])}, "
            f"fresh {pct(card['fresh'])}, accuracy {pct(card['accuracy'])}, flagged {card['flagged']:,}")

    ui.step(5, 5, "Checks")
    problems = checks.find_problems(stats, size, previous_status)
    write_step_summary(status, problems, login_problem)
    if problems:
        for p in problems:
            ui.error(p)
        ui.error("Not publishing - last night's guide stays up")
        return 2

    matches_doc = {name: {"id": xml_id, "how": result.how[name], "flags": card["flags"].get(name, [])}
                   for name, xml_id in sorted(result.matches.items())}
    queue_doc = {"generated_at": status["generated_at"], "sources": ref.source_status,
                 "queue": result.queue, "carried": result.carried}
    publish.write_publish_dir(args.publish_dir, build_path, {
        "status.json": status,
        "channels.json": names,
        "matches.json": matches_doc,
        "match_queue.json": queue_doc,
        "score_history.json": history,
    }, ref.index)
    ui.success(f"{stats.channels:,} channels, {stats.programmes:,} programmes, {status['size_mb']} MB -> {args.publish_dir}")
    if login_problem:
        ui.error(login_problem)
        return 3
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
    sys.exit(main())
