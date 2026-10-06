"""Refresh the channel list from your IPTV playlist, downloaded in your own browser.

Since 2026-09-30 the provider's Cloudflare protection turns away scripts, so the nightly build can't fetch
the channel list itself. Run this on the PC whenever channels have changed:

    python tools/import_playlist.py           opens the playlist download in your browser, waits for it, imports it
    python tools/import_playlist.py FILE      imports a playlist you already saved

It keeps only channel names, guide IDs and groups (never the stream links, which contain your login), saves
them to data/channels_import.json, pushes that to GitHub and starts a guide rebuild. --no-push skips that.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from datetime import date, datetime
from urllib.parse import urlencode, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import matching  # noqa: E402

OUT = os.path.join(ROOT, "data", "channels_import.json")
REPO = "mattdawe-collab/epg-host"
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
EXTINF = re.compile(r'^#EXTINF:\s*-?\d+(?:\.\d+)?((?:\s+[\w-]+="[^"]*")*)\s*,(.*)$')
ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')
FRESH_SECONDS = 24 * 3600


def read_entries(text):
    """Every live channel in an M3U playlist as {"name", "epg_id", "group"}, in playlist order. Stream links,
    logos and everything else are dropped; movies and series are skipped."""
    text = text.lstrip("﻿")
    head = text.lstrip()[:1000].lower()
    if head.startswith("<") or "<html" in head:
        raise ValueError("This file is a web page, not a playlist - probably the provider's protection page. "
                         "Open the link again, let the check finish, and save the file that downloads.")
    entries, pending = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            match = EXTINF.match(line)
            attrs = dict(ATTRIBUTE.findall(match.group(1))) if match else {}
            name = (match.group(2) if match else line.split(",", 1)[-1]).strip() or attrs.get("tvg-name", "").strip()
            pending = {"name": name, "epg_id": attrs.get("tvg-id", "").strip() or None,
                       "group": attrs.get("group-title", "").strip()} if name else None
        elif line and not line.startswith("#"):
            if pending and "/movie/" not in line and "/series/" not in line:
                entries.append(pending)
            pending = None
    if not any(not e["name"].startswith("#") for e in entries):
        raise ValueError("The file has no channels in it.")
    return entries


def keep_wanted(entries):
    """The channels the guide covers, each section header kept only when its section still has one."""
    kept, header = [], None
    for entry in entries:
        if entry["name"].startswith("#"):
            header = entry
        elif matching.is_priority_channel(entry["name"]):
            if header:
                kept.append(header)
                header = None
            kept.append(entry)
    if not kept:
        raise ValueError("The playlist has no channels from the groups this guide covers.")
    return kept


def parse_m3u(text):
    return keep_wanted(read_entries(text))


def login_leaks(text, login):
    """Which parts of the login (server, username, password) appear in text. The repo is public."""
    url = (login or {}).get("XC_URL", "")
    parts = {"server": urlparse(url if "//" in url else "//" + url).hostname or "",
             "username": (login or {}).get("XC_USERNAME", ""), "password": (login or {}).get("XC_PASSWORD", "")}
    lowered = text.lower()
    return [k for k, v in parts.items() if len(v.strip()) >= 4 and v.strip().lower() in lowered]


def import_playlist(path, out, today, login=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        entries = read_entries(f.read())
    kept = keep_wanted(entries)
    text = (f'{{"imported_at": "{today}", "channels": [\n'
            + ",\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + "\n]}\n")
    leaks = login_leaks(text, login)
    if leaks:
        raise ValueError(f"The channel list would contain your login ({', '.join(leaks)}) - nothing was saved.")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".part", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(out + ".part", out)
    channels = [e for e in kept if not e["name"].startswith("#")]
    return {"channels": sum(not e["name"].startswith("#") for e in entries), "priority": len(channels),
            "with_guide_id": sum(bool(e["epg_id"]) for e in channels)}


def find_playlist(folder):
    """The most recently saved playlist in folder, or None."""
    if not os.path.isdir(folder):
        return None
    found = []
    for name in os.listdir(folder):
        lowered = name.lower()
        path = os.path.join(folder, name)
        if (lowered.endswith((".m3u", ".m3u8")) or lowered.startswith("get.php")) and os.path.isfile(path) \
                and not lowered.endswith((".crdownload", ".part", ".tmp")):
            found.append((os.path.getmtime(path), path))
    return max(found)[1] if found else None


def playlist_link(login):
    query = urlencode({"username": login["XC_USERNAME"], "password": login["XC_PASSWORD"],
                       "type": "m3u_plus", "output": "ts"})
    return f"{login['XC_URL'].strip().rstrip('/')}/get.php?{query}"


def load_login():
    from dotenv import dotenv_values

    values = dotenv_values(os.path.join(ROOT, ".env"))
    return {k: (values.get(k) or "").strip() for k in ("XC_URL", "XC_USERNAME", "XC_PASSWORD")}


def wait_for_download(folder, since, timeout=600, poll=2.0):
    """A playlist saved in folder after `since` whose size has stopped changing, or None after timeout."""
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        path = find_playlist(folder)
        if path and os.path.getmtime(path) >= since:
            size = os.path.getsize(path)
            if last == (path, size) and size:
                return path
            last = (path, size)
        time.sleep(poll)
    return None


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def push_and_rebuild(today):
    if run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "code":
        print("Not on the 'code' branch, so nothing was pushed. Switch to it and run again.")
        return 1
    rel = os.path.relpath(OUT, ROOT).replace(os.sep, "/")
    run("git", "add", rel)
    if run("git", "diff", "--cached", "--quiet", "--", rel).returncode == 0:
        print("The channel list hasn't changed since the last import - nothing to push.")
        return 0
    steps = [("git", "commit", "-m", f"Import channel list from playlist ({today})", "--", rel),
             ("git", "push", "origin", "code"),
             ("gh", "workflow", "run", "nightly.yml", "--repo", REPO, "--ref", "code", "-f", "publish=true")]
    for cmd in steps:
        result = run(*cmd)
        if result.returncode:
            print(f"'{' '.join(cmd[:2])}' failed:\n{(result.stderr or result.stdout).strip()}")
            return 1
    print("Pushed. The guide is rebuilding now (about 15 minutes); TiviMate picks it up on its next refresh.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Refresh the channel list from a playlist downloaded in your browser.")
    p.add_argument("playlist", nargs="?", help="a playlist file you already saved")
    p.add_argument("--folder", default=DOWNLOADS, help="where your browser saves downloads")
    p.add_argument("--no-push", action="store_true", help="only save data/channels_import.json")
    args = p.parse_args(argv)
    login = load_login() if os.path.exists(os.path.join(ROOT, ".env")) else {}

    path = args.playlist
    if not path:
        newest = find_playlist(args.folder)
        if newest and time.time() - os.path.getmtime(newest) < FRESH_SECONDS:
            path = newest
            print(f"Using the playlist you downloaded at {datetime.fromtimestamp(os.path.getmtime(newest)):%H:%M %d %b}.")
        else:
            if not all(login.values()):
                print("The IPTV login isn't saved yet - run tools/set_login.py first.")
                return 1
            started = time.time() - 5
            webbrowser.open(playlist_link(login))
            print("Your browser is downloading your playlist. If it asks, save it to your Downloads folder.\n"
                  "Waiting for it (up to 10 minutes)...")
            path = wait_for_download(args.folder, started)
            if not path:
                print("No playlist arrived. Save it from the browser, then run this again.")
                return 1

    today = date.today().isoformat()
    try:
        summary = import_playlist(path, OUT, today, login)
    except (OSError, ValueError) as e:
        print(f"Could not import the playlist: {e}")
        return 1
    print(f"Imported {summary['priority']:,} channels ({summary['with_guide_id']:,} with guide IDs) "
          f"from {summary['channels']:,} live channels in the playlist.")
    if not args.playlist or os.path.dirname(os.path.abspath(path)) == os.path.abspath(args.folder):
        print("The downloaded playlist file contains your login - delete it from Downloads when you're done.")
    return 0 if args.no_push else push_and_rebuild(today)


if __name__ == "__main__":
    sys.exit(main())
