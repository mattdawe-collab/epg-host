"""Refresh the channel list from your IPTV provider, opened in your own browser.

Since 2026-09-30 the provider's Cloudflare protection turns away scripts, so the nightly build can't fetch
the channel list itself. Run this on the PC whenever channels have changed:

    python tools/import_playlist.py           opens your channel list in the browser; press Ctrl+S, Save; it imports it
    python tools/import_playlist.py FILE      imports a channel list or M3U playlist you already saved

The browser page is the provider's app-login channel list (player_api.php, the one TiviMate uses; the M3U
download link returns an empty page for this provider). Only channel names, guide IDs and groups are kept - never
stream links, which contain your login. They go to data/channels_import.json, which is pushed to GitHub, and a
guide rebuild starts. --no-push skips that.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import matching  # noqa: E402

OUT = os.path.join(ROOT, "data", "channels_import.json")
REPO = "mattdawe-collab/epg-host"
LOGIN_KEYS = ("XC_URL", "XC_USERNAME", "XC_PASSWORD")
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
BROWSER_DIRS = [os.path.join(LOCAL_APPDATA, "Google", "Chrome", "User Data"),
                os.path.join(LOCAL_APPDATA, "Microsoft", "Edge", "User Data")]
LIST_NAMES = ("get.php", "player_api")
PARTIAL = (".crdownload", ".part", ".partial", ".tmp")
EXTINF = re.compile(r'^#EXTINF:\s*-?\d+(?:\.\d+)?((?:\s+[\w-]+="[^"]*")*)\s*,(.*)$')
ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')
TAG = re.compile(r"<[^>]*>")
FRESH_SECONDS = 24 * 3600
PENDING = os.path.join(ROOT, ".git", "epg_import_rebuild_pending")  # a rebuild is still owed after a failed start


def read_api_json(text):
    """Channels from a saved player_api.php?action=get_live_streams page: a JSON list of streams."""
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("The saved channel list is incomplete or damaged - open it again and save it once the "
                         "page has finished loading.") from None
    if isinstance(data, dict) and isinstance(data.get("user_info"), dict) and str(data["user_info"].get("auth")) == "0":
        raise ValueError("The provider rejected the login saved on this PC - run tools/set_login.py, then try again.")
    entries = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and str(item.get("name") or "").strip():
            entries.append({"name": str(item["name"]).strip(),
                            "epg_id": str(item.get("epg_channel_id") or "").strip() or None,
                            "group": str(item.get("category_id") or "").strip()})
    return entries


def read_entries(text):
    """Every live channel in a saved channel list (provider JSON or M3U playlist) as {"name", "epg_id", "group"},
    in provider order. Stream links, logos and everything else are dropped; movies and series are skipped."""
    text = text.lstrip("﻿")
    if not text.strip():
        raise ValueError("The saved page is empty - the provider sent nothing back. If the browser page was blank, "
                         "the login saved on this PC may be out of date: run tools/set_login.py, then try again.")
    head = text.lstrip()[:1000].lower()
    if head.startswith("<") or "<html" in head:
        inner = html.unescape(TAG.sub("", text)).strip()
        if inner.startswith(("[", "{")):  # saved as "Webpage, Complete": the channel list wrapped in HTML
            return read_entries(inner)
        raise ValueError("This file is a web page, not a channel list - probably the provider's protection page. "
                         "Open the link again, let the check finish, and save the page once it fills with text.")
    if head.startswith(("[", "{")):
        entries = read_api_json(text)
        if not any(not e["name"].startswith("#") for e in entries):
            raise ValueError("The saved channel list has no channels in it.")
        return entries
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
        raw = f.read()
    entries = read_entries(raw)
    kept = keep_wanted(entries)
    text = (f'{{"imported_at": "{today}", "channels": [\n'
            + ",\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + "\n]}\n")
    plain = "\n".join(f"{e['name']}\t{e['epg_id'] or ''}\t{e['group']}" for e in kept)  # before JSON escaping
    leaks = login_leaks(text + "\n" + plain, login)
    if leaks:
        raise ValueError(f"The channel list would contain your login ({', '.join(leaks)}) - nothing was saved.")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".part", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(out + ".part", out)
    channels = [e for e in kept if not e["name"].startswith("#")]
    return {"channels": sum(not e["name"].startswith("#") for e in entries), "priority": len(channels),
            "with_guide_id": sum(bool(e["epg_id"]) for e in channels),
            "file_has_login": bool(login_leaks(raw, login))}


def save_folders(downloads=DOWNLOADS, browser_dirs=BROWSER_DIRS):
    """Downloads plus the folders Chrome and Edge save into. Ctrl+S opens wherever a page was last saved
    (the profile's savefile.default_directory), which often isn't Downloads."""
    folders, seen = [downloads], {os.path.normcase(os.path.abspath(downloads))}
    for user_data in browser_dirs:
        profile = "Default"
        try:
            with open(os.path.join(user_data, "Local State"), encoding="utf-8") as f:
                profile = json.load(f)["profile"]["last_used"] or profile
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            with open(os.path.join(user_data, profile, "Preferences"), encoding="utf-8") as f:
                prefs = json.load(f)
        except (OSError, ValueError):
            continue
        for section in ("savefile", "download"):
            folder = prefs.get(section) if isinstance(prefs, dict) else None
            folder = folder.get("default_directory") if isinstance(folder, dict) else None
            key = os.path.normcase(os.path.abspath(folder)) if isinstance(folder, str) and folder else None
            if key and key not in seen and os.path.isdir(folder):
                seen.add(key)
                folders.append(folder)
    return folders


def files_in(folders):
    for folder in [folders] if isinstance(folders, str) else folders:
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if not name.lower().endswith(PARTIAL) and os.path.isfile(path):
                yield path


def named_like_a_list(path):
    name = os.path.basename(path).lower()
    return name.endswith((".m3u", ".m3u8")) or name.startswith(LIST_NAMES)


def looks_like_a_list(path):
    """True for a saved channel list or playlist whatever it was named, judged by its first few KB."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096).decode("utf-8", "ignore").lstrip("﻿ \r\n\t")
    except OSError:
        return False
    return head.startswith("#EXTM3U") or '"stream_id"' in head or '"user_info"' in head


def find_playlist(folders):
    """The most recently saved channel list or playlist (judged by file name) in the folders, or None."""
    found = [(os.path.getmtime(p), p) for p in files_in(folders) if named_like_a_list(p)]
    return max(found)[1] if found else None


def wait_for_download(folders, since, timeout=600, poll=2.0):
    """A channel list saved in any of the folders after `since` whose size has stopped changing (an empty file
    must stay empty for three checks), or None after timeout."""
    deadline, seen = time.time() + timeout, {}
    while time.time() < deadline:
        ready = []
        for path in files_in(folders):
            try:
                modified, size = os.path.getmtime(path), os.path.getsize(path)
            except OSError:
                continue
            if modified < since or not (named_like_a_list(path) or (size and looks_like_a_list(path))):
                continue
            previous = seen.get(path)
            steady = previous[1] + 1 if previous and previous[0] == size else 0
            seen[path] = (size, steady)
            if steady >= (1 if size else 3):
                ready.append((modified, path))
        if ready:
            return max(ready)[1]
        time.sleep(poll)
    return None


def channels_link(login):
    query = urlencode({"username": login["XC_USERNAME"], "password": login["XC_PASSWORD"],
                       "action": "get_live_streams"})
    return f"{login['XC_URL'].strip().rstrip('/')}/player_api.php?{query}"


def load_login():
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return {k: "" for k in LOGIN_KEYS}
    from dotenv import dotenv_values

    values = dotenv_values(path)
    return {k: (values.get(k) or "").strip() for k in LOGIN_KEYS}


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def push_and_rebuild(today):
    if run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "code":
        print("Not on the 'code' branch, so nothing was pushed. Switch to it and run again.")
        return 1
    rel = os.path.relpath(OUT, ROOT).replace(os.sep, "/")
    run("git", "add", rel)
    if run("git", "diff", "--cached", "--quiet", "--", rel).returncode:
        result = run("git", "commit", "-m", f"Import channel list from playlist ({today})", "--", rel)
        if result.returncode:
            print(f"'git commit' failed:\n{(result.stderr or result.stdout).strip()}")
            return 1
    elif run("git", "rev-list", "--count", "origin/code..HEAD").stdout.strip() in ("", "0") \
            and not os.path.exists(PENDING):
        print("The channel list hasn't changed since the last import - nothing to push.")
        return 0
    try:
        open(PENDING, "w").close()
    except OSError:
        pass
    for cmd in (("git", "push", "origin", "code"),
                ("gh", "workflow", "run", "nightly.yml", "--repo", REPO, "--ref", "code", "-f", "publish=true")):
        result = run(*cmd)
        if result.returncode:
            print(f"'{' '.join(cmd[:2])}' failed:\n{(result.stderr or result.stdout).strip()}\nRun this again to retry.")
            return 1
    try:
        os.remove(PENDING)
    except OSError:
        pass
    print("Pushed. The guide is rebuilding now (about 15 minutes); TiviMate picks it up on its next refresh.")
    return 0


def try_import(path, today, login):
    try:
        return import_playlist(path, OUT, today, login)
    except (OSError, ValueError) as e:
        print(f"Could not import {os.path.basename(path) if named_like_a_list(path) else 'the saved file'}: {e}")
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Refresh the channel list from your provider, opened in your browser.")
    p.add_argument("playlist", nargs="?", help="a channel list or playlist file you already saved")
    p.add_argument("--folder", help="also look for the saved file in this folder")
    p.add_argument("--no-push", action="store_true", help="only save data/channels_import.json")
    args = p.parse_args(argv)
    login = load_login()
    today = datetime.now(timezone.utc).date().isoformat()  # same clock as the nightly build's channel_list_date

    path, summary = args.playlist, None
    if path:
        summary = try_import(path, today, login)
        if not summary:
            return 1
    else:
        folders = save_folders() + ([args.folder] if args.folder else [])
        newest = find_playlist(folders)
        if newest and time.time() - os.path.getmtime(newest) < FRESH_SECONDS:
            print(f"Found the channel list you saved at {datetime.fromtimestamp(os.path.getmtime(newest)):%H:%M %d %b}.")
            path, summary = newest, try_import(newest, today, login)
            if not summary:
                print("Skipping it and opening a fresh copy instead.")
        if not summary:
            if not all(login.values()):
                print("The IPTV login isn't saved yet - run tools/set_login.py first.")
                return 1
            started = time.time() - 5
            webbrowser.open(channels_link(login))
            print("Your browser is opening your channel list.\n"
                  "  1. Wait until the page fills with text (it can take a minute).\n"
                  "  2. Press Ctrl+S, then click Save.\n"
                  f"Waiting for the saved file in {', '.join(os.path.basename(f) or f for f in folders)} "
                  "(up to 10 minutes)...")
            path = wait_for_download(folders, started)
            if not path:
                print("Nothing was saved there. If the browser page stayed blank or showed an error, the login saved "
                      "on this PC may be out of date - run tools/set_login.py, then run this again. If you saved it "
                      "somewhere else, run this again with that file's full path at the end.")
                return 1
            summary = try_import(path, today, login)
            if not summary:
                return 1

    print(f"Imported {summary['priority']:,} channels ({summary['with_guide_id']:,} with guide IDs) "
          f"from {summary['channels']:,} live channels.")
    if summary["file_has_login"] or path.lower().endswith((".m3u", ".m3u8")) \
            or os.path.basename(path).lower().startswith("get.php"):
        print(f"The saved file ({os.path.basename(path)} in {os.path.basename(os.path.dirname(path)) or 'its folder'}) "
              "contains your login - delete it when you're done.")
    return 0 if args.no_push else push_and_rebuild(today)


if __name__ == "__main__":
    sys.exit(main())
