"""Update the IPTV login in .env and in the repo's GitHub Actions secrets.

Run it whenever the provider login changes. Nothing entered here is printed.
The provider refuses requests from some connections (HTTP 513 - the old setup needed a VPN), so the
login check can fail even for a good login. Connect the VPN first, or pass --no-check to save the
login anyway and let the nightly GitHub build test it from GitHub's servers.
"""
import datetime
import getpass
import os
import subprocess
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
REPO = "mattdawe-collab/epg-host"


def ask():
    url = input("Server URL: ").strip().rstrip("/")
    user = input("Username: ").strip()
    password = getpass.getpass("Password (hidden as you paste): ").strip()
    if not (url and user and password):
        sys.exit("All three are required. Nothing was changed.")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return {"XC_URL": url, "XC_USERNAME": user, "XC_PASSWORD": password}


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
        sys.exit(f"The provider refused this request (HTTP {r.status_code}). That happens for a wrong login, "
                 f"but also when the provider blocks this connection - try again with the VPN on, or run "
                 f"with --no-check to save it anyway. Nothing was changed.")
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
