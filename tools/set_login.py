"""Update the IPTV login in .env and in the repo's GitHub Actions secrets.

Run it whenever the provider login changes. What you paste is shown on your screen only (a hidden
prompt turns Ctrl+V into an invisible character on Windows) and is never printed back or logged.
The login is checked with the provider first; --no-check skips that and lets the next GitHub build test it.
"""
import datetime
import os
import subprocess
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
REPO = "mattdawe-collab/epg-host"


def find_problems(login):
    problems = []
    for key, value in login.items():
        if not value:
            problems.append(f"{key} is empty")
        elif any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            problems.append(f"{key} contains an invisible control character - paste with right-click, not Ctrl+V")
    return problems


def ask():
    url = input("Server URL: ").strip().rstrip("/")
    user = input("Username: ").strip()
    password = input("Password: ").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    login = {"XC_URL": url, "XC_USERNAME": user, "XC_PASSWORD": password}
    problems = find_problems(login)
    if problems:
        sys.exit("; ".join(problems) + ". Nothing was changed.")
    return login


def check_login(login):
    try:
        r = requests.get(
            login["XC_URL"] + "/player_api.php",
            params={"username": login["XC_USERNAME"], "password": login["XC_PASSWORD"]},
            timeout=30,
        )
    except requests.RequestException as e:
        sys.exit(f"Could not reach the provider ({type(e).__name__}). Nothing was changed.")
    try:
        info = r.json().get("user_info", {})
    except ValueError:
        info = {}
    if r.status_code != 200 or str(info.get("auth")) != "1":
        sys.exit(f"The provider refused this login (HTTP {r.status_code}). Check the username and password; "
                 f"if you're sure they're right, try with the VPN on, or run with --no-check. Nothing was changed.")
    expires = info.get("exp_date")
    expires = datetime.date.fromtimestamp(int(expires)).isoformat() if expires else "no expiry given"
    print(f"Login OK - status: {info.get('status')}, expires: {expires}, "
          f"connections in use: {info.get('active_cons')} of {info.get('max_connections')}")


def update_env(login):
    text = open(ENV_PATH, encoding="utf-8").read() if os.path.exists(ENV_PATH) else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    remaining = dict(login)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines += [f"{k}={v}" for k, v in remaining.items()]
    with open(ENV_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(newline.join(lines) + newline)
    print("Saved to .env")


def update_github(login):
    for key, value in login.items():
        result = subprocess.run(["gh", "secret", "set", key, "--repo", REPO],
                                input=value, text=True, capture_output=True)
        if result.returncode != 0:
            sys.exit(f"Could not save {key} to GitHub: {result.stderr.strip()}")
    print(f"Saved to GitHub secrets for {REPO}")


if __name__ == "__main__":
    login = ask()
    if "--no-check" in sys.argv[1:]:
        print("Skipping the login check - the next GitHub build will show whether the provider accepts it.")
    else:
        check_login(login)
    update_env(login)
    update_github(login)
    print("Done.")
