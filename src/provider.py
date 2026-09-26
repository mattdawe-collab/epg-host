"""Fetch the channel list from the IPTV provider's Xtream Codes API."""
import re
import time
from urllib.parse import quote, quote_plus, urlparse

import requests


class LoginRejected(Exception):
    """The provider refused the login. This provider answers HTTP 513 for a bad login."""


class ProviderUnavailable(Exception):
    """The provider could not be reached or sent something unusable."""


def redact(text, secrets):
    """Drop query strings, then every raw and URL-encoded form of each secret. Logs are public."""
    text = re.sub(r"\?[^\s'\"()]*", "?***", text)
    forms = set()
    for secret in secrets:
        if secret:
            forms |= {secret, quote(secret, safe=""), quote_plus(secret)}
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "***")
    return text


def fetch_channels(url, username, password, timeout=60, attempts=3, sleep=time.sleep):
    """Return [{"name": str, "epg_id": str | None}] for every live channel."""
    base = url.strip().rstrip("/")
    secrets = [username, password, base, urlparse(base).hostname or ""]
    params = {"username": username, "password": password, "action": "get_live_streams"}
    problem = "no attempts made"
    for attempt in range(attempts):
        if attempt:
            sleep(10 * attempt)
        try:
            response = requests.get(f"{base}/player_api.php", params=params, timeout=timeout)
        except requests.RequestException as e:
            problem = redact(f"{type(e).__name__}: {e}", secrets)
            continue
        if response.status_code == 513:
            raise LoginRejected("HTTP 513")
        if response.status_code != 200:
            problem = f"HTTP {response.status_code}"
            continue
        try:
            data = response.json()
        except ValueError:
            problem = "the response was not JSON"
            continue
        if isinstance(data, dict):
            info = data.get("user_info")
            if isinstance(info, dict) and str(info.get("auth")) == "0":
                raise LoginRejected("auth=0")
            problem = "unexpected response shape"
            continue
        if not isinstance(data, list):
            problem = "unexpected response shape"
            continue
        channels = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                channels.append({"name": name, "epg_id": str(item.get("epg_channel_id") or "").strip() or None})
        return channels
    raise ProviderUnavailable(problem)
