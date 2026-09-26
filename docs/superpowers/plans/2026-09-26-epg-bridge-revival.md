# EPG Bridge Revival Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish the TiviMate guide every night on GitHub Actions with zero AI API calls, keep the TinyURLs working, and score coverage, freshness and accuracy.

**Architecture:**
- `src/main.py` orchestrates small single-purpose modules:
  - `provider.py`: the channel list
  - `epg_cache.py`: the guide sources
  - `matching.py`: no-AI matching
  - `guide.py`: the XMLTV writer
  - `checks.py`: the publish gate
  - `score.py`: the scorecard
  - `publish.py`: the output folder
- The workflow runs `main.py` on the `code` branch and force-pushes the output folder to a publish-only `main` branch.
- `src/match_session.py` gives Claude Code sessions the tools to match and audit channels by hand.

**Tech Stack:**
- Python 3.13, with `requests`, `python-dotenv`, `lxml` and `rapidfuzz>=3`
- `pytest` for tests
- GitHub Actions: `actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`

**Spec:** `docs/superpowers/specs/2026-09-26-epg-bridge-revival-design.md`

All commands run from the PC copy's root: `C:\Users\Admin\Documents\AI_EPG_Bridge`. `py` below means `venv\Scripts\python`.

## Global Constraints

- **No AI:** no AI/LLM API calls anywhere. Remove every Gemini import and the `google-genai` dependency.
- **Public repo:** never commit `.env`, the provider's address, credentials or raw playlist data. Never print the provider URL, username or password.
- **Branches:** `main` is publish-only and rebuilt nightly. Code lives on `code`.
- **Published paths:** `main:epg.xml.gz` and `main:data/epg_repair.xml.gz` must both exist after every publish, byte-identical.
- **Guide format:** each `<channel id>` and its `<display-name>` are the exact provider channel name.
- **Matching order:**
  1. a saved match whose ID is valid tonight
  2. `no_guide`
  3. rename carry-over (unique normalized pair, not rejected)
  4. exact or fuzzy (≥ 93) match, not rejected
  5. the queue
- **Programme window:** from 1 day behind to 8 days ahead. If the file is over 95 MB, retry once at 5 days ahead.
- **Publish gate:**
  - at least 80% of last night's channels (on a first run, at least 1,000)
  - at least 50% of guide channels have a programme in the next 24 hours
  - the compressed file is at most 95 MB
- **Exit codes of `main.py`:**
  - 0: published
  - 2: checks failed, so nothing is published
  - 3: published from a fallback list because the login was rejected or missing
- **Scorecard:**
  - coverage = matched ÷ channels
  - fresh = channels with a programme in the next 24 hours ÷ guide channels
  - accuracy = correct ÷ random audits, over the last 200
  - headline = coverage × fresh × accuracy, using 1.0 for accuracy until the first audit
  - history keeps 365 days
- **Schedule:** `0 9 * * *` UTC. Job timeout: 90 minutes.
- **Windows console:** anything that prints channel names must survive non-ASCII characters (`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`).
- **Commits:** every commit message ends with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A guide source that downloads as an HTML error page (HTTP 200, not gzip) must never replace a good cached copy. Tested in Task 2 (`test_download_rejects_non_gzip_and_keeps_old_file`).
2. Channel names with XML-special characters, such as `US| A&E <HD>`, must still produce a guide that parses. Tested in Task 4 (`test_special_characters_in_names`).
3. A source file corrupt partway through must be skipped without aborting the build or corrupting the output. Tested in Task 4 (`test_corrupt_source_is_skipped`).
4. The provider listing the same channel name twice must not duplicate guide channels or block rename carry-over. Tested in Task 3 (`test_carry_over_handles_duplicate_names_in_list`, `test_resolve_lists_each_channel_once`).
5. A `requests` error message that contains the full API URL, credentials included, must be redacted before it can reach a log. Tested in Task 1 (`test_network_errors_retry_then_raise_unavailable_without_secrets`).

---

### Task 1: `code` branch, test harness and provider client

**Files:**
- Create: `requirements-dev.txt`, `tests/conftest.py`, `tests/fixtures_xmltv.py`, `src/provider.py`, `tests/test_provider.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces:
  - `provider.fetch_channels(url, username, password, timeout=60, attempts=3, sleep=time.sleep) -> list[dict]`, returning items of the form `{"name": str, "epg_id": str | None}`
  - `provider.LoginRejected` and `provider.ProviderUnavailable` (both subclasses of `Exception`)
  - `provider.redact(text, secrets) -> str`
  - `fixtures_xmltv.make_source(path, programmes, names=None)`, where each programme is `(channel_id, start_dt, stop_dt, title)` and `names` is `{channel_id: [display names]}`
  - `fixtures_xmltv.xmltv_time(dt) -> str`

- [ ] **Step 1: Create the branch and the commit identity**

```powershell
git switch -c code
$id = gh api user --jq .id
git config user.name "Matt Dawe"
git config user.email "$id+mattdawe-collab@users.noreply.github.com"
```

- [ ] **Step 2: Dependencies and the test harness**

`requirements.txt`:
```
requests
python-dotenv
lxml
rapidfuzz>=3
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
```

`tests/conftest.py`:
```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
```

`tests/fixtures_xmltv.py`:
```python
import gzip

from lxml import etree


def xmltv_time(moment):
    return moment.strftime("%Y%m%d%H%M%S +0000")


def make_source(path, programmes, names=None):
    """programmes: [(channel_id, start, stop, title)]; names: {channel_id: [display names]}."""
    names = dict(names or {})
    for channel_id, *_ in programmes:
        names.setdefault(channel_id, [channel_id])
    root = etree.Element("tv")
    for channel_id, display_names in names.items():
        channel = etree.SubElement(root, "channel", id=channel_id)
        for display in display_names:
            etree.SubElement(channel, "display-name").text = display
    for channel_id, start, stop, title in programmes:
        programme = etree.SubElement(root, "programme", start=xmltv_time(start), stop=xmltv_time(stop), channel=channel_id)
        etree.SubElement(programme, "title").text = title
    with gzip.open(path, "wb") as f:
        f.write(etree.tostring(root, xml_declaration=True, encoding="utf-8"))
```

Run: `py -m pip install -r requirements-dev.txt`

- [ ] **Step 3: Write the failing tests** in `tests/test_provider.py`

```python
import pytest
import requests

import provider


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def fake_get(responses):
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append((url, params))
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return _get, calls


def no_sleep(_seconds):
    pass


def test_fetch_channels_returns_names_and_epg_ids(monkeypatch):
    get, calls = fake_get([FakeResponse(200, [
        {"name": " US| CNN HD ", "epg_channel_id": "CNN.us"},
        {"name": "UK| BBC ONE", "epg_channel_id": ""},
        {"name": "", "epg_channel_id": "x"},
        "not a dict",
    ])])
    monkeypatch.setattr(provider.requests, "get", get)
    channels = provider.fetch_channels("http://host.example/", "user1", "pass1", sleep=no_sleep)
    assert channels == [{"name": "US| CNN HD", "epg_id": "CNN.us"}, {"name": "UK| BBC ONE", "epg_id": None}]
    assert calls[0][0] == "http://host.example/player_api.php"
    assert calls[0][1] == {"username": "user1", "password": "pass1", "action": "get_live_streams"}


def test_http_513_means_login_rejected(monkeypatch):
    get, _ = fake_get([FakeResponse(513)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.LoginRejected, match="513"):
        provider.fetch_channels("http://host.example", "u", "p", sleep=no_sleep)


def test_auth_zero_means_login_rejected(monkeypatch):
    get, _ = fake_get([FakeResponse(200, {"user_info": {"auth": 0}})])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.LoginRejected):
        provider.fetch_channels("http://host.example", "u", "p", sleep=no_sleep)


def test_network_errors_retry_then_raise_unavailable_without_secrets(monkeypatch):
    message = ("HTTPConnectionPool(host='host.example', port=80): Max retries exceeded with url: "
               "/player_api.php?username=user1&password=secretpw&action=get_live_streams")
    get, calls = fake_get([requests.ConnectionError(message) for _ in range(3)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.ProviderUnavailable) as caught:
        provider.fetch_channels("http://host.example", "user1", "secretpw", sleep=no_sleep)
    text = str(caught.value)
    assert "secretpw" not in text and "user1" not in text and "host.example" not in text
    assert len(calls) == 3


def test_retry_recovers_after_a_failure(monkeypatch):
    get, calls = fake_get([FakeResponse(502), FakeResponse(200, [{"name": "US| CNN", "epg_channel_id": None}])])
    monkeypatch.setattr(provider.requests, "get", get)
    assert provider.fetch_channels("http://h", "u", "p", sleep=no_sleep) == [{"name": "US| CNN", "epg_id": None}]
    assert len(calls) == 2


def test_server_errors_become_unavailable(monkeypatch):
    get, _ = fake_get([FakeResponse(502), FakeResponse(502), FakeResponse(502)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.ProviderUnavailable, match="HTTP 502"):
        provider.fetch_channels("http://h", "u", "p", sleep=no_sleep)


def test_redact_replaces_longest_secrets_first():
    assert provider.redact("http://host.example host.example u1 pw", ["u1", "pw", "http://host.example", "host.example", ""]) == "*** *** *** ***"
```

- [ ] **Step 4: Run them and see them fail**

Run: `py -m pytest tests/test_provider.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'provider'`.

- [ ] **Step 5: Implement** `src/provider.py`

```python
"""Fetch the channel list from the IPTV provider's Xtream Codes API."""
import time
from urllib.parse import urlparse

import requests


class LoginRejected(Exception):
    """The provider refused the login. This provider answers HTTP 513 for a bad login."""


class ProviderUnavailable(Exception):
    """The provider could not be reached or sent something unusable."""


def redact(text, secrets):
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, "***")
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
        channels = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                channels.append({"name": name, "epg_id": str(item.get("epg_channel_id") or "").strip() or None})
        return channels
    raise ProviderUnavailable(problem)
```

- [ ] **Step 6: Run the tests and see them pass**

Run: `py -m pytest tests/test_provider.py -q`
Expected: `7 passed`.

- [ ] **Step 7: Commit**

```powershell
git add requirements.txt requirements-dev.txt tests/conftest.py tests/fixtures_xmltv.py src/provider.py tests/test_provider.py
git commit -m "Add provider client with login-rejection handling and secret redaction" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Guide sources — safe downloads, status, guide index

**Files:**
- Modify (full rewrite): `src/epg_cache.py`
- Test: `tests/test_epg_cache.py`

**Interfaces:**
- Consumes: `fixtures_xmltv.make_source`
- Produces:
  - `epg_cache.SOURCES: list[tuple[url, filename]]`, the nine sources without `epghub.xyz`
  - `epg_cache.ReferenceData`, with fields:
    - `by_name: dict[str, str]`
    - `valid_ids: set[str]`
    - `index: dict[str, list[str]]`
    - `source_status: dict[str, str]`, each value being "downloaded", "cached", "stale cache" or "failed"
    - `paths: list[str]`
  - `epg_cache.fetch_reference_data(sources, cache_dir, cache_max_age_hours=24.0) -> ReferenceData`
  - `epg_cache.parse_epg_channels(path) -> (by_name, ids, index)`
  - `epg_cache.download_file(url, dest_path, timeout=120) -> bool`

- [ ] **Step 1: Write the failing tests** in `tests/test_epg_cache.py`

```python
import os
import time
from datetime import datetime, timedelta, timezone

from lxml import etree
import gzip

import epg_cache
from fixtures_xmltv import make_source, xmltv_time

NOW = datetime.now(timezone.utc)


def prog(channel_id):
    return (channel_id, NOW, NOW + timedelta(hours=1), "Show")


class FakeDownload:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body


def test_parse_reads_names_ids_and_index(tmp_path):
    src = tmp_path / "a.xml.gz"
    make_source(src, [prog("CNN.us")], names={"CNN.us": ["CNN", "CNN HD"], "BBCOne.uk": ["BBC One"]})
    by_name, ids, index = epg_cache.parse_epg_channels(str(src))
    assert by_name == {"CNN": "CNN.us", "CNN HD": "CNN.us", "BBC One": "BBCOne.uk"}
    assert ids == {"CNN.us", "BBCOne.uk"}
    assert index == {"CNN.us": ["CNN", "CNN HD"], "BBCOne.uk": ["BBC One"]}


def test_parse_stops_at_first_programme(tmp_path):
    root = etree.Element("tv")
    etree.SubElement(etree.SubElement(root, "channel", id="A.us"), "display-name").text = "A"
    etree.SubElement(root, "programme", start=xmltv_time(NOW), stop=xmltv_time(NOW), channel="A.us")
    etree.SubElement(etree.SubElement(root, "channel", id="B.us"), "display-name").text = "B"
    src = tmp_path / "odd.xml.gz"
    with gzip.open(src, "wb") as f:
        f.write(etree.tostring(root))
    _, ids, _ = epg_cache.parse_epg_channels(str(src))
    assert ids == {"A.us"}


def test_fetch_reports_status_and_first_source_wins(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    make_source(cache / "fresh.xml.gz", [prog("CNN.us")], names={"CNN.us": ["CNN"]})
    make_source(cache / "old.xml.gz", [prog("CNN2.us")], names={"CNN2.us": ["CNN", "CNN Two"]})
    old = time.time() - 48 * 3600
    os.utime(cache / "old.xml.gz", (old, old))
    monkeypatch.setattr(epg_cache, "download_file", lambda url, dest, timeout=120: False)
    sources = [("https://example.invalid/1", "fresh.xml.gz"), ("https://example.invalid/2", "old.xml.gz"),
               ("https://example.invalid/3", "none.xml.gz")]
    ref = epg_cache.fetch_reference_data(sources, str(cache), cache_max_age_hours=24)
    assert ref.source_status == {"fresh.xml.gz": "cached", "old.xml.gz": "stale cache", "none.xml.gz": "failed"}
    assert ref.by_name == {"CNN": "CNN.us", "CNN Two": "CNN2.us"}
    assert ref.valid_ids == {"CNN.us", "CNN2.us"}
    assert ref.index == {"CNN.us": ["CNN"], "CNN2.us": ["CNN", "CNN Two"]}
    assert ref.paths == [os.path.join(str(cache), "fresh.xml.gz"), os.path.join(str(cache), "old.xml.gz")]


def test_fetch_downloads_when_cache_missing(tmp_path, monkeypatch):
    def fake_download(url, dest, timeout=120):
        make_source(dest, [prog("ESPN.us")], names={"ESPN.us": ["ESPN"]})
        return True

    monkeypatch.setattr(epg_cache, "download_file", fake_download)
    ref = epg_cache.fetch_reference_data([("https://example.invalid/a", "a.xml.gz")], str(tmp_path), 24)
    assert ref.source_status == {"a.xml.gz": "downloaded"}
    assert ref.valid_ids == {"ESPN.us"}


def test_download_rejects_non_gzip_and_keeps_old_file(tmp_path, monkeypatch):
    dest = tmp_path / "a.xml.gz"
    dest.write_bytes(b"\x1f\x8bOLD")
    monkeypatch.setattr(epg_cache.requests, "get", lambda *a, **k: FakeDownload(b"<html>blocked</html>"))
    assert epg_cache.download_file("https://example.invalid/a", str(dest)) is False
    assert dest.read_bytes() == b"\x1f\x8bOLD"
    assert not (tmp_path / "a.xml.gz.part").exists()


def test_download_saves_gzip(tmp_path, monkeypatch):
    dest = tmp_path / "a.xml.gz"
    monkeypatch.setattr(epg_cache.requests, "get", lambda *a, **k: FakeDownload(b"\x1f\x8bNEW"))
    assert epg_cache.download_file("https://example.invalid/a", str(dest)) is True
    assert dest.read_bytes() == b"\x1f\x8bNEW"


def test_sources_drop_dead_epghub():
    assert len(epg_cache.SOURCES) == 9
    assert not any("epghub.xyz" in url for url, _ in epg_cache.SOURCES)
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_epg_cache.py -q`
Expected: failures such as `AttributeError: module 'epg_cache' has no attribute 'SOURCES'`.

- [ ] **Step 3: Implement.** Replace all of `src/epg_cache.py` with:

```python
"""Download, cache and read the channel lists of the XMLTV guide sources."""
import gzip
import os
import time
from dataclasses import dataclass, field

import requests
from lxml import etree

SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", "all_sources.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz", "us_locals.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz", "us_sports.xml.gz"),
    ("https://epg.pw/xmltv/epg_GB.xml.gz", "epg_uk_pw.xml.gz"),
    ("https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz", "epg_uk_ripper.xml.gz"),
    ("https://epg.pw/xmltv/epg_CA.xml.gz", "epg_canada_pw.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada1.xml.gz", "globetv_canada1.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada2.xml.gz", "globetv_canada2.xml.gz"),
    ("https://raw.githubusercontent.com/globetvapp/epg/main/Canada/canada3.xml.gz", "globetv_canada3.xml.gz"),
]


@dataclass
class ReferenceData:
    by_name: dict = field(default_factory=dict)        # display name -> channel id (first source wins)
    valid_ids: set = field(default_factory=set)
    index: dict = field(default_factory=dict)          # channel id -> display names
    source_status: dict = field(default_factory=dict)  # filename -> downloaded | cached | stale cache | failed
    paths: list = field(default_factory=list)          # readable source files, in source order


def get_cache_age_hours(path):
    if not os.path.exists(path):
        return float("inf")
    return (time.time() - os.path.getmtime(path)) / 3600


def download_file(url, dest_path, timeout=120):
    """Download to a temp file and only replace dest_path when the result is a gzip file."""
    tmp_path = dest_path + ".part"
    try:
        print(f"    Downloading {url}")
        with requests.get(url, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        with open(tmp_path, "rb") as f:
            if f.read(2) != b"\x1f\x8b":
                raise ValueError("not a gzip file")
        os.replace(tmp_path, dest_path)
        print(f"    [OK] {os.path.getsize(dest_path) / 1048576:.1f} MB")
        return True
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def parse_epg_channels(path):
    """Read the <channel> list. XMLTV lists channels before programmes, so stop at the first programme."""
    by_name, ids, index = {}, set(), {}
    try:
        with gzip.open(path, "rb") as f:
            for _, elem in etree.iterparse(f, events=("end",), tag=("channel", "programme")):
                if elem.tag == "programme":
                    break
                channel_id = (elem.get("id") or "").strip()
                if channel_id:
                    ids.add(channel_id)
                    names = index.setdefault(channel_id, [])
                    for display in elem.findall("display-name"):
                        text = (display.text or "").strip()
                        if text:
                            by_name.setdefault(text, channel_id)
                            if text not in names:
                                names.append(text)
                elem.clear()
    except Exception as e:
        print(f"    [FAIL] Could not read {os.path.basename(path)}: {type(e).__name__}: {e}")
    return by_name, ids, index


def fetch_reference_data(sources, cache_dir, cache_max_age_hours=24.0):
    os.makedirs(cache_dir, exist_ok=True)
    ref = ReferenceData()
    for url, filename in sources:
        path = os.path.join(cache_dir, filename)
        age = get_cache_age_hours(path)
        if age <= cache_max_age_hours:
            status = "cached"
            print(f"  [{filename}] using cache ({age:.1f}h old)")
        else:
            print(f"  [{filename}] downloading")
            if download_file(url, path):
                status = "downloaded"
            elif os.path.exists(path):
                status = "stale cache"
            else:
                ref.source_status[filename] = "failed"
                continue
        by_name, ids, index = parse_epg_channels(path)
        if not ids:
            ref.source_status[filename] = "failed"
            continue
        ref.source_status[filename] = status
        ref.paths.append(path)
        for name, channel_id in by_name.items():
            ref.by_name.setdefault(name, channel_id)
        ref.valid_ids |= ids
        for channel_id, names in index.items():
            merged = ref.index.setdefault(channel_id, [])
            merged.extend(n for n in names if n not in merged)
        print(f"    [OK] {len(by_name):,} names, {len(ids):,} channel IDs")
    print(f"  Total: {len(ref.by_name):,} names, {len(ref.valid_ids):,} channel IDs")
    return ref
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_epg_cache.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/epg_cache.py tests/test_epg_cache.py
git commit -m "Rework guide sources: drop dead epghub, safe downloads, per-source status, guide index" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: No-AI matching

**Files:**
- Create: `src/matching.py`, `tests/test_matching.py`

**Interfaces:**
- Produces:
  - `matching.PRIORITY_PREFIXES`
  - `matching.is_priority_channel(name) -> bool`
  - `matching.extract_core_name(name) -> str`
  - `matching.normalize_name(name) -> str`
  - `matching.is_region(xml_id, region) -> bool`
  - `matching.region_of(name) -> "US" | "CA" | "UK" | "ALL"`
  - `matching.Pools(by_name)`, with methods:
    - `.best(region, text, cutoff) -> (display, id) | None`
    - `.candidates(region, channel_name, limit=10) -> dict[display, id]`
  - `matching.carry_over_renames(current_names, known) -> {new_name: {"from": old_name, "id": xml_id}}`
  - `matching.quick_match(name, by_name, pools) -> str | None`
  - `matching.Resolution`, with fields:
    - `matches: dict[name, id]`
    - `how: dict[name, "saved" | "renamed" | "auto"]`
    - `carried: dict`
    - `queue: list[dict]`, each entry holding keys `name`, `reason` ("new" or "vanished_id"), `candidates` (a list of `{"id", "name"}`), and optionally `previous_id` and `provider_id`
    - `counts: Counter`
  - `matching.resolve(names, known, no_guide, by_name, valid_ids, provider_ids=None, rejected=None, max_candidates=10) -> Resolution`

- [ ] **Step 1: Write the failing tests** in `tests/test_matching.py`

```python
import matching

REFERENCE = {
    "CNN": "CNN.us",
    "CNN International": "CNNInternational.uk",
    "BBC One": "BBCOne.uk",
    "CBC Toronto": "CBLT.ca",
    "ESPN": "ESPN.us",
    "ESPN 2": "ESPN2.us",
}
VALID = set(REFERENCE.values())


def test_priority_prefixes():
    assert matching.is_priority_channel("US| CNN HD")
    assert matching.is_priority_channel("SLING| AMC")
    assert not matching.is_priority_channel("FR| TF1")
    assert not matching.is_priority_channel("USA NETWORK")


def test_core_name_skips_every_prefix_and_quality_tag():
    assert matching.extract_core_name("SLING| AMC") == "AMC"
    assert matching.extract_core_name("PLAY+| DISCOVERY") == "DISCOVERY"
    assert matching.extract_core_name("US| CNN HD") == "CNN"
    assert matching.extract_core_name("US| ABC 7 (WABC) NEW YORK") == "WABC"


def test_normalize_ignores_quality_tags_and_punctuation():
    assert matching.normalize_name("US| CNN HD") == matching.normalize_name("US| CNN FHD")
    assert matching.normalize_name("US| CNN ᴴᴰ") == matching.normalize_name("US| CNN")
    assert matching.normalize_name("US| A&E HD") == matching.normalize_name("US| A E")


def test_normalize_keeps_prefix_and_numbers():
    assert matching.normalize_name("UK| BBC ONE HD") != matching.normalize_name("US| BBC ONE HD")
    assert matching.normalize_name("US| ESPN 2 HD") != matching.normalize_name("US| ESPN HD")


def test_carry_over_simple_rename():
    known = {"US| CNN HD": "CNN.us", "US| FOX NEWS": "FoxNews.us"}
    assert matching.carry_over_renames(["US| CNN FHD", "US| FOX NEWS"], known) == {
        "US| CNN FHD": {"from": "US| CNN HD", "id": "CNN.us"}}


def test_carry_over_skips_ambiguous_pairs():
    assert matching.carry_over_renames(["US| CNN FHD", "US| CNN 4K"], {"US| CNN HD": "CNN.us"}) == {}
    assert matching.carry_over_renames(["US| CNN FHD"], {"US| CNN HD": "CNN.us", "US| CNN SD": "CNNsd.us"}) == {}


def test_carry_over_ignores_section_headers_and_other_prefixes():
    assert matching.carry_over_renames(["FR| TF1 FHD"], {"##### NEWS #####": "x", "FR| TF1 HD": "TF1.fr"}) == {}


def test_carry_over_handles_duplicate_names_in_list():
    assert matching.carry_over_renames(["US| CNN FHD", "US| CNN FHD"], {"US| CNN HD": "CNN.us"}) == {
        "US| CNN FHD": {"from": "US| CNN HD", "id": "CNN.us"}}


def test_resolve_order():
    known = {"US| CNN HD": "CNN.us", "US| OLD NAME HD": "ESPN.us", "US| GONE": "Missing.us"}
    no_guide = {"US| PPV EVENT 1": "2026-09-26"}
    names = ["US| CNN HD", "US| PPV EVENT 1", "US| OLD NAME FHD", "UK| BBC ONE", "US| TOTALLY UNKNOWN XYZ", "US| GONE"]
    res = matching.resolve(names, known, no_guide, REFERENCE, VALID)
    assert res.matches == {"US| CNN HD": "CNN.us", "US| OLD NAME FHD": "ESPN.us", "UK| BBC ONE": "BBCOne.uk"}
    assert res.how == {"US| CNN HD": "saved", "US| OLD NAME FHD": "renamed", "UK| BBC ONE": "auto"}
    assert res.carried == {"US| OLD NAME FHD": {"from": "US| OLD NAME HD", "id": "ESPN.us"}}
    queued = {e["name"]: e for e in res.queue}
    assert set(queued) == {"US| TOTALLY UNKNOWN XYZ", "US| GONE"}
    assert queued["US| GONE"]["reason"] == "vanished_id" and queued["US| GONE"]["previous_id"] == "Missing.us"
    assert queued["US| TOTALLY UNKNOWN XYZ"]["reason"] == "new"
    assert dict(res.counts) == {"known": 1, "no_guide": 1, "carried": 1, "auto": 1, "queued": 2}


def test_resolve_lists_each_channel_once():
    res = matching.resolve(["US| CNN HD", "US| CNN HD"], {"US| CNN HD": "CNN.us"}, {}, REFERENCE, VALID)
    assert res.matches == {"US| CNN HD": "CNN.us"}
    assert res.counts["known"] == 1


def test_rejected_pairs_are_never_auto_matched():
    res = matching.resolve(["UK| BBC ONE"], {}, {}, REFERENCE, VALID, rejected={"UK| BBC ONE": ["BBCOne.uk"]})
    assert res.matches == {}
    assert [e["name"] for e in res.queue] == ["UK| BBC ONE"]


def test_rejected_pairs_are_never_carried_over():
    res = matching.resolve(["US| CNN FHD"], {"US| CNN HD": "CNN.us"}, {}, {"Other": "Other.us"}, VALID | {"Other.us"},
                           rejected={"US| CNN FHD": ["CNN.us"]})
    assert "US| CNN FHD" not in res.matches


def test_queue_entry_has_candidates_and_only_valid_provider_hints():
    name = "US| TOTALLY UNKNOWN XYZ"
    entry = matching.resolve([name], {}, {}, REFERENCE, VALID, provider_ids={name: "ESPN2.us"}).queue[0]
    assert entry["provider_id"] == "ESPN2.us"
    assert 0 < len(entry["candidates"]) <= 10
    assert all(c["id"] in VALID for c in entry["candidates"])
    entry = matching.resolve([name], {}, {}, REFERENCE, VALID, provider_ids={name: "Nope.us"}).queue[0]
    assert "provider_id" not in entry


def test_candidates_are_capped():
    pools = matching.Pools({f"CNN {i}": f"CNN{i}.us" for i in range(30)})
    assert len(pools.candidates("US", "US| CNN", limit=10)) == 10
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_matching.py -q`
Expected: `ModuleNotFoundError: No module named 'matching'`.

- [ ] **Step 3: Implement** `src/matching.py`

```python
"""Match provider channel names to guide channel IDs without AI:
saved decisions, simple renames, and exact or fuzzy display-name matches."""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process, utils

PRIORITY_PREFIXES = (
    "US| ", "CA| ", "UK| ",
    "PRIME| ", "SLING| ", "GO| ", "PLAY+| ",
    "UK-BBCI| ", "UK-NOWTV| ",
    "SPORTS| ", "NFL TEAMS| ", "NHL TEAM| ",
    "4K| ", "ENGLISH| ", "EN| ",
)
PREFIX_WORDS = {p.strip("| ").upper() for p in PRIORITY_PREFIXES} | {"EU", "LOCALS", "CHANNELS"}
AUTO_MATCH_SCORE = 93
SUPERSCRIPT_TAGS = re.compile(r"[ᴴᴰᵁᴴᴰ⁴ᴷˢᵈ¹⁰⁸⁰ᵖᶜᴿᵃᴰ]+")
QUALITY_WORDS = re.compile(r"\b(HD|SD|UHD|FHD|4K|HEVC|H264|H265|1080P|720P|60FPS)\b", re.IGNORECASE)


def is_priority_channel(name):
    return name.startswith(PRIORITY_PREFIXES)


def extract_core_name(channel_name):
    """The part of a decorated IPTV name that identifies the channel: a callsign if present."""
    callsign = re.search(r"\(([A-Z]{4,5})\)", channel_name)
    if callsign:
        return callsign.group(1)
    clean = SUPERSCRIPT_TAGS.sub("", channel_name)
    clean = QUALITY_WORDS.sub("", clean)
    clean = re.sub(r"^[#|]+\s*", "", clean)
    clean = re.sub(r"\s*[#|]+$", "", clean)
    parts = [p.strip() for p in clean.split("|") if p.strip() and p.strip().upper() not in PREFIX_WORDS]
    if parts:
        return re.sub(r"[|#]+", " ", parts[0]).strip()
    return channel_name.strip()


def normalize_name(name):
    """Prefix plus name with quality tags and punctuation removed: 'US| CNN HD' -> 'US|CNN'."""
    prefix, sep, rest = name.partition("| ")
    if not sep:
        prefix, rest = "", name
    rest = QUALITY_WORDS.sub(" ", SUPERSCRIPT_TAGS.sub(" ", rest))
    rest = " ".join(re.sub(r"[^0-9A-Za-z]+", " ", rest).upper().split())
    return f"{prefix.strip().upper()}|{rest}"


def is_region(xml_id, region):
    suffix = xml_id.rsplit(".", 1)[-1] if "." in xml_id else ""
    return suffix.startswith(region)


def region_of(channel_name):
    if channel_name.startswith("CA| "):
        return "CA"
    if channel_name.startswith(("US| ", "SLING| ")):
        return "US"
    if channel_name.startswith(("UK| ", "UK-BBCI| ", "UK-NOWTV| ")):
        return "UK"
    return "ALL"


class Pools:
    """Display-name pools per region, prepared once for fast searching."""

    def __init__(self, by_name):
        regional = {r: {n: i for n, i in by_name.items() if is_region(i, r.lower())} for r in ("US", "CA", "UK")}
        self.maps = {r: (m or by_name) for r, m in regional.items()}
        self.maps["ALL"] = by_name
        self._names = {r: list(m) for r, m in self.maps.items()}
        self._lower = {r: [n.lower() for n in names] for r, names in self._names.items()}
        self._processed = {r: [utils.default_process(n) for n in names] for r, names in self._names.items()}

    def best(self, region, text, cutoff):
        hit = process.extractOne(utils.default_process(text), self._processed[region],
                                 scorer=fuzz.WRatio, processor=None, score_cutoff=cutoff)
        if not hit:
            return None
        name = self._names[region][hit[2]]
        return name, self.maps[region][name]

    def candidates(self, region, channel_name, limit=10):
        names, lower, pool = self._names[region], self._lower[region], self.maps[region]
        core = extract_core_name(channel_name)
        raw = re.sub(r"^[^|]*\|\s*", "", channel_name).strip()
        raw_clean = re.sub(r"\s*(HD|SD|WEST|EAST)\s*$", "", raw, flags=re.IGNORECASE).strip()
        terms = [t for t in dict.fromkeys([core, raw, raw_clean]) if len(t) >= 2]
        found = {}

        def add(i):
            found.setdefault(names[i], pool[names[i]])
            return len(found) >= limit

        for term in terms:  # one name contains the other
            t = term.lower()
            for i, n in enumerate(lower):
                if (t in n or (len(n) >= 3 and n in t)) and add(i):
                    return found
        for term in terms:  # every word of the term appears
            words = [w for w in term.lower().split() if len(w) > 1]
            if words:
                for i, n in enumerate(lower):
                    if all(w in n for w in words) and add(i):
                        return found
        for term in terms:  # closest fuzzy matches
            for _, _, i in process.extract(utils.default_process(term), self._processed[region],
                                           scorer=fuzz.WRatio, processor=None, limit=limit):
                if add(i):
                    return found
        return found


def carry_over_renames(current_names, known):
    """New names that differ from exactly one vanished matched name only by quality tags or punctuation."""
    current = set(current_names)
    vanished, new = defaultdict(list), defaultdict(list)
    for old in known:
        if old not in current and not old.startswith("#") and is_priority_channel(old):
            vanished[normalize_name(old)].append(old)
    for name in dict.fromkeys(current_names):
        if name not in known:
            new[normalize_name(name)].append(name)
    renames = {}
    for key, olds in vanished.items():
        if len(olds) == 1 and len(new.get(key, [])) == 1:
            renames[new[key][0]] = {"from": olds[0], "id": known[olds[0]]}
    return renames


def quick_match(channel_name, by_name, pools):
    core = extract_core_name(channel_name)
    if core in by_name:
        return by_name[core]
    hit = pools.best(region_of(channel_name), core, AUTO_MATCH_SCORE)
    return hit[1] if hit else None


@dataclass
class Resolution:
    matches: dict = field(default_factory=dict)
    how: dict = field(default_factory=dict)
    carried: dict = field(default_factory=dict)
    queue: list = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)


def resolve(names, known, no_guide, by_name, valid_ids, provider_ids=None, rejected=None, max_candidates=10):
    provider_ids = provider_ids or {}
    rejected = rejected or {}
    pools = Pools(by_name)
    renames = carry_over_renames(names, known)
    result = Resolution()

    def accept(name, xml_id, how, count):
        result.matches[name] = xml_id
        result.how[name] = how
        result.counts[count] += 1

    for name in dict.fromkeys(names):
        saved = known.get(name)
        refused = set(rejected.get(name, ()))
        rename = renames.get(name)
        if saved in valid_ids:
            accept(name, saved, "saved", "known")
        elif name in no_guide:
            result.counts["no_guide"] += 1
        elif rename and rename["id"] in valid_ids and rename["id"] not in refused:
            accept(name, rename["id"], "renamed", "carried")
            result.carried[name] = rename
        elif (auto := quick_match(name, by_name, pools)) and auto not in refused:
            accept(name, auto, "auto", "auto")
        else:
            entry = {"name": name, "reason": "vanished_id" if saved else "new",
                     "candidates": [{"id": i, "name": n}
                                    for n, i in pools.candidates(region_of(name), name, max_candidates).items()]}
            if saved:
                entry["previous_id"] = saved
            if provider_ids.get(name) in valid_ids:
                entry["provider_id"] = provider_ids[name]
            result.queue.append(entry)
            result.counts["queued"] += 1
    return result
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_matching.py -q`
Expected: `14 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/matching.py tests/test_matching.py
git commit -m "Add no-AI matching: saved, rename carry-over, rapidfuzz auto-match, candidate queue" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Guide writer

**Files:**
- Create: `src/guide.py`, `tests/test_guide.py`

**Interfaces:**
- Consumes: `fixtures_xmltv.make_source`
- Produces:
  - `guide.GuideStats`, with fields `channels`, `programmes`, `channels_with_upcoming`, `skipped_duplicates` and `skipped_out_of_window`
  - `guide.parse_xmltv_time(value) -> datetime | None`
  - `guide.write_guide(out_path, matches, source_paths, now, days_ahead=8.0, days_behind=1.0) -> GuideStats`

- [ ] **Step 1: Write the failing tests** in `tests/test_guide.py`

```python
import gzip
from datetime import datetime, timedelta, timezone

from lxml import etree

import guide
from fixtures_xmltv import make_source

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def read_guide(path):
    with gzip.open(path, "rb") as f:
        root = etree.parse(f).getroot()
    return ([c.get("id") for c in root.findall("channel")],
            [(p.get("channel"), p.findtext("title")) for p in root.findall("programme")])


def test_programmes_copied_to_every_channel_name(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    make_source(src, [("CNN.us", NOW, NOW + HOUR, "News"), ("Other.us", NOW, NOW + HOUR, "Ignored")])
    stats = guide.write_guide(str(out), {"US| CNN HD": "CNN.us", "US| CNN FHD": "CNN.us"}, [str(src)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| CNN FHD", "US| CNN HD"]
    assert programmes == [("US| CNN FHD", "News"), ("US| CNN HD", "News")]
    assert (stats.channels, stats.programmes, stats.channels_with_upcoming) == (2, 2, 2)


def test_duplicate_slots_across_sources_are_dropped(tmp_path):
    a, b, out = tmp_path / "a.xml.gz", tmp_path / "b.xml.gz", tmp_path / "guide.xml.gz"
    make_source(a, [("CNN.us", NOW, NOW + HOUR, "From A")])
    make_source(b, [("CNN.us", NOW, NOW + HOUR, "From B"), ("CNN.us", NOW + HOUR, NOW + 2 * HOUR, "Later B")])
    stats = guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(a), str(b)], NOW)
    assert read_guide(out)[1] == [("US| CNN", "From A"), ("US| CNN", "Later B")]
    assert stats.skipped_duplicates == 1


def test_programmes_outside_window_are_dropped(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    old = NOW - timedelta(days=3)
    soon = NOW + timedelta(days=2)
    far = NOW + timedelta(days=9)
    make_source(src, [("CNN.us", old, old + HOUR, "Old"), ("CNN.us", soon, soon + HOUR, "Soon"),
                      ("CNN.us", far, far + HOUR, "Far")])
    stats = guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(src)], NOW, days_ahead=8)
    assert read_guide(out)[1] == [("US| CNN", "Soon")]
    assert stats.skipped_out_of_window == 2
    assert stats.channels_with_upcoming == 0


def test_special_characters_in_names(tmp_path):
    src, out = tmp_path / "a.xml.gz", tmp_path / "guide.xml.gz"
    make_source(src, [("AE.us", NOW, NOW + HOUR, "Show")])
    guide.write_guide(str(out), {"US| A&E <HD> \"East\"": "AE.us"}, [str(src)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| A&E <HD> \"East\""]
    assert programmes == [("US| A&E <HD> \"East\"", "Show")]


def test_corrupt_source_is_skipped(tmp_path):
    good, full, bad, out = (tmp_path / n for n in ("good.xml.gz", "full.xml.gz", "bad.xml.gz", "guide.xml.gz"))
    make_source(good, [("CNN.us", NOW, NOW + HOUR, "Good")])
    make_source(full, [("CNN.us", NOW + i * HOUR, NOW + (i + 1) * HOUR, f"P{i}") for i in range(1, 150)])
    data = full.read_bytes()
    bad.write_bytes(data[: len(data) // 2])
    guide.write_guide(str(out), {"US| CNN": "CNN.us"}, [str(good), str(bad)], NOW)
    channels, programmes = read_guide(out)
    assert channels == ["US| CNN"]
    assert programmes[0] == ("US| CNN", "Good")


def test_parse_xmltv_time():
    assert guide.parse_xmltv_time("20260926120000 +0000") == NOW
    assert guide.parse_xmltv_time("20260926070000 -0500") == NOW
    assert guide.parse_xmltv_time("20260926120000") == NOW
    assert guide.parse_xmltv_time("garbage") is None
    assert guide.parse_xmltv_time(None) is None
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_guide.py -q`
Expected: `ModuleNotFoundError: No module named 'guide'`.

- [ ] **Step 3: Implement** `src/guide.py`

```python
"""Write the merged XMLTV guide: one channel per provider name, programmes copied from the matched source."""
import gzip
import os
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from lxml import etree


@dataclass
class GuideStats:
    channels: int
    programmes: int
    channels_with_upcoming: int
    skipped_duplicates: int
    skipped_out_of_window: int


def parse_xmltv_time(value):
    """'20260926120000 +0000' -> timezone-aware datetime, or None when unreadable."""
    if not value or len(value) < 14:
        return None
    try:
        moment = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    offset = value[14:].strip()
    if len(offset) == 5 and offset[0] in "+-" and offset[1:].isdigit():
        delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        return moment.replace(tzinfo=timezone(delta if offset[0] == "+" else -delta))
    return moment.replace(tzinfo=timezone.utc)


def write_guide(out_path, matches, source_paths, now, days_ahead=8.0, days_behind=1.0):
    names_by_id = defaultdict(list)
    for name in sorted(matches):
        names_by_id[matches[name]].append(name)
    earliest = now - timedelta(days=days_behind)
    latest = now + timedelta(days=days_ahead)
    next_day = now + timedelta(hours=24)
    seen, upcoming_ids = set(), set()
    programmes = duplicates = out_of_window = 0

    with gzip.open(out_path, "wb") as out, etree.xmlfile(out, encoding="utf-8") as xf:
        xf.write_declaration()
        with xf.element("tv", {"generator-info-name": "epg-bridge"}):
            for name in sorted(matches):
                channel = etree.Element("channel", id=name)
                etree.SubElement(channel, "display-name").text = name
                xf.write(channel)
            for path in source_paths:
                try:
                    with gzip.open(path, "rb") as src:
                        for _, elem in etree.iterparse(src, events=("end",), tag="programme"):
                            xml_id = elem.get("channel")
                            if xml_id in names_by_id:
                                start = parse_xmltv_time(elem.get("start"))
                                stop = parse_xmltv_time(elem.get("stop")) or start
                                key = (xml_id, start.timestamp() if start else elem.get("start"))
                                if start and (stop < earliest or start > latest):
                                    out_of_window += 1
                                elif key in seen:
                                    duplicates += 1
                                else:
                                    seen.add(key)
                                    if start and start < next_day and stop > now:
                                        upcoming_ids.add(xml_id)
                                    for name in names_by_id[xml_id]:
                                        dup = deepcopy(elem)
                                        dup.set("channel", name)
                                        xf.write(dup)
                                        programmes += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                except Exception as e:
                    print(f"    [WARN] Stopped reading {os.path.basename(path)}: {type(e).__name__}: {e}")
    upcoming = sum(len(names_by_id[i]) for i in upcoming_ids)
    return GuideStats(len(matches), programmes, upcoming, duplicates, out_of_window)
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_guide.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/guide.py tests/test_guide.py
git commit -m "Add guide writer with time window, cross-source de-duplication and corrupt-source tolerance" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Publish gate and publish folder

**Files:**
- Create: `src/checks.py`, `src/publish.py`, `tests/test_checks.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: `guide.GuideStats`
- Produces:
  - `checks.find_problems(stats, size_bytes, previous_status=None) -> list[str]`
  - `checks.MAX_BYTES` and `checks.FIRST_RUN_MIN_CHANNELS`
  - `publish.write_publish_dir(publish_dir, guide_path, json_files: dict[str, object], guide_index: dict)`

- [ ] **Step 1: Write the failing tests**

`tests/test_checks.py`:
```python
import checks
from guide import GuideStats


def stats(channels=2000, upcoming=1800):
    return GuideStats(channels=channels, programmes=100_000, channels_with_upcoming=upcoming,
                      skipped_duplicates=0, skipped_out_of_window=0)


def test_healthy_guide_passes():
    assert checks.find_problems(stats(), 40 * 2**20, {"channels": 2100}) == []


def test_empty_guide_fails():
    assert any("no channels" in p for p in checks.find_problems(stats(0, 0), 1000, None))


def test_big_drop_from_last_night_fails():
    assert any("down from 2,000" in p for p in checks.find_problems(stats(1500, 1400), 1000, {"channels": 2000}))


def test_first_run_needs_minimum_channels():
    assert checks.find_problems(stats(999, 999), 1000, None)
    assert checks.find_problems(stats(1000, 900), 1000, None) == []


def test_few_upcoming_programmes_fails():
    assert any("next 24 hours" in p for p in checks.find_problems(stats(2000, 900), 1000, None))


def test_oversized_guide_fails():
    assert any("MB" in p for p in checks.find_problems(stats(), 96 * 2**20, None))
```

`tests/test_publish.py`:
```python
import gzip
import json

import pytest

import publish


def test_publish_dir_contents(tmp_path):
    built = tmp_path / "g.xml.gz"
    built.write_bytes(b"guide-bytes")
    out = tmp_path / "publish"
    publish.write_publish_dir(str(out), str(built), {"status.json": {"channels": 1}, "channels.json": ["US| CNN"]},
                              {"CNN.us": ["CNN"]})
    assert (out / "epg.xml.gz").read_bytes() == b"guide-bytes"
    assert (out / "data" / "epg_repair.xml.gz").read_bytes() == b"guide-bytes"
    assert json.loads((out / "status.json").read_text(encoding="utf-8")) == {"channels": 1}
    assert json.loads((out / "channels.json").read_text(encoding="utf-8")) == ["US| CNN"]
    with gzip.open(out / "guide_index.json.gz", "rt", encoding="utf-8") as f:
        assert json.load(f) == {"CNN.us": ["CNN"]}
    assert "generated" in (out / "README.md").read_text(encoding="utf-8").lower()


def test_republish_replaces_previous_output(tmp_path):
    built = tmp_path / "g.xml.gz"
    built.write_bytes(b"x")
    out = tmp_path / "publish"
    publish.write_publish_dir(str(out), str(built), {"status.json": {}, "old.json": 1}, {})
    publish.write_publish_dir(str(out), str(built), {"status.json": {}}, {})
    assert not (out / "old.json").exists()


def test_refuses_to_wipe_an_unrelated_folder(tmp_path):
    built = tmp_path / "g.xml.gz"
    built.write_bytes(b"x")
    folder = tmp_path / "important"
    folder.mkdir()
    (folder / "notes.txt").write_text("keep")
    with pytest.raises(ValueError):
        publish.write_publish_dir(str(folder), str(built), {"status.json": {}}, {})
    assert (folder / "notes.txt").exists()
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_checks.py tests/test_publish.py -q`
Expected: `ModuleNotFoundError` for `checks` and `publish`.

- [ ] **Step 3: Implement**

`src/checks.py`:
```python
"""Decide whether a freshly built guide is safe to publish."""

MAX_BYTES = 95 * 1024 * 1024
FIRST_RUN_MIN_CHANNELS = 1000
MIN_SHARE_OF_LAST_NIGHT = 0.8
MIN_SHARE_WITH_UPCOMING = 0.5


def find_problems(stats, size_bytes, previous_status=None):
    problems = []
    last_night = (previous_status or {}).get("channels")
    if stats.channels == 0:
        problems.append("the guide has no channels")
    elif last_night and stats.channels < MIN_SHARE_OF_LAST_NIGHT * last_night:
        problems.append(f"only {stats.channels:,} channels, down from {last_night:,} last night")
    elif not last_night and stats.channels < FIRST_RUN_MIN_CHANNELS:
        problems.append(f"only {stats.channels:,} channels; a first run needs at least {FIRST_RUN_MIN_CHANNELS:,}")
    if stats.channels and stats.channels_with_upcoming < MIN_SHARE_WITH_UPCOMING * stats.channels:
        problems.append(f"only {stats.channels_with_upcoming:,} of {stats.channels:,} channels have "
                        f"programmes in the next 24 hours")
    if size_bytes > MAX_BYTES:
        problems.append(f"the guide is {size_bytes / 1048576:.0f} MB, over the {MAX_BYTES // 1048576} MB limit")
    return problems
```

`src/publish.py`:
```python
"""Assemble the folder the nightly job force-pushes to the publish-only `main` branch."""
import gzip
import json
import os
import shutil

README = """# Published guide - generated, do not edit

Rebuilt every night by `.github/workflows/nightly.yml` on the `code` branch and force-pushed here with no history.

- `epg.xml.gz` - the guide
- `data/epg_repair.xml.gz` - the same guide at an older address
- `matches.json` - tonight's guide ID for every channel and how it was matched
- `match_queue.json` - channels waiting to be matched in a Claude session
- `guide_index.json.gz` - every guide channel ID with its display names
- `channels.json` - tonight's channel list
- `status.json` - tonight's run details and scorecard
- `score_history.json` - the scorecard over time
"""


def write_publish_dir(publish_dir, guide_path, json_files, guide_index):
    if os.path.isdir(publish_dir) and os.listdir(publish_dir):
        if not os.path.exists(os.path.join(publish_dir, "status.json")):
            raise ValueError(f"{publish_dir} is not empty and is not a previous publish folder")
        shutil.rmtree(publish_dir)
    os.makedirs(os.path.join(publish_dir, "data"), exist_ok=True)
    shutil.copyfile(guide_path, os.path.join(publish_dir, "epg.xml.gz"))
    shutil.copyfile(guide_path, os.path.join(publish_dir, "data", "epg_repair.xml.gz"))
    for relative_path, data in json_files.items():
        with open(os.path.join(publish_dir, relative_path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
            f.write("\n")
    with gzip.open(os.path.join(publish_dir, "guide_index.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(guide_index, f, ensure_ascii=False, sort_keys=True)
    with open(os.path.join(publish_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_checks.py tests/test_publish.py -q`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/checks.py src/publish.py tests/test_checks.py tests/test_publish.py
git commit -m "Add publish gate and publish-folder writer" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Scorecard

**Files:**
- Create: `src/score.py`, `tests/test_score.py`

**Interfaces:**
- Consumes: `matching.region_of` and `guide.GuideStats`
- Produces:
  - `score.flag_reasons(name, xml_id) -> list[str]`, containing any of "region", "callsign" and "network"
  - `score.audited_accuracy(audit_log) -> (float | None, int)`
  - `score.scorecard(total_channels, matches, stats, audit_log) -> dict`, with keys `coverage`, `fresh`, `accuracy`, `audited`, `headline`, `headline_basis`, `flagged` and `flags`
  - `score.update_history(history, day, card) -> list`

- [ ] **Step 1: Write the failing tests** in `tests/test_score.py`

```python
import score
from guide import GuideStats


def test_region_flag():
    assert "region" in score.flag_reasons("US| CNN", "CNN.uk")
    assert score.flag_reasons("US| CNN", "CNN.us") == []
    assert score.flag_reasons("US| ABC 7 (WABC)", "WABC.us_locals1") == []
    assert score.flag_reasons("CA| CBC TORONTO", "CBLT.ca") == []
    assert score.flag_reasons("SPORTS| NBA 1", "NBA.uk") == []


def test_callsign_flag():
    assert "callsign" in score.flag_reasons("US| ABC 7 (WABC)", "KABC.us")
    assert "callsign" not in score.flag_reasons("US| ABC 7 (WABC)", "ABC.(WABC).New.York,.NY.us")


def test_network_flag():
    assert "network" in score.flag_reasons("US| FOX 5 NEW YORK", "CBSNewYork.us")
    assert "network" not in score.flag_reasons("US| FOX 5 NEW YORK", "WNYW.us")
    assert "network" not in score.flag_reasons("US| MSNBC", "MSNBC.us")


def test_audited_accuracy_counts_random_samples_only():
    log = [{"sample": "random", "verdict": "correct"}] * 3 + [{"sample": "random", "verdict": "wrong"}] + \
          [{"sample": "flagged", "verdict": "wrong"}] * 5
    assert score.audited_accuracy(log) == (0.75, 4)
    assert score.audited_accuracy([]) == (None, 0)


def test_scorecard_numbers():
    stats = GuideStats(channels=3, programmes=10, channels_with_upcoming=3, skipped_duplicates=0, skipped_out_of_window=0)
    matches = {"US| A": "A.us", "US| B": "B.uk", "US| C": "C.us"}
    card = score.scorecard(4, matches, stats, [])
    assert card["coverage"] == 0.75 and card["fresh"] == 1.0
    assert card["accuracy"] is None and card["headline_basis"] == "unaudited"
    assert card["headline"] == 0.75
    assert card["flagged"] == 1 and card["flags"] == {"US| B": ["region"]}
    card = score.scorecard(4, matches, stats, [{"sample": "random", "verdict": "correct"},
                                               {"sample": "random", "verdict": "wrong"}])
    assert card["accuracy"] == 0.5 and card["headline"] == 0.375


def test_update_history_replaces_same_day_and_caps_length():
    card = {"coverage": 0.5, "fresh": 1.0, "accuracy": None, "flagged": 2, "headline": 0.5}
    history = [{"date": f"2025-01-{d:02d}"} for d in range(1, 31)] * 13
    updated = score.update_history(history + [{"date": "2026-09-26", "headline": 0.1}], "2026-09-26", card)
    assert len(updated) == score.HISTORY_DAYS
    assert updated[-1] == {"date": "2026-09-26", **card}
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_score.py -q`
Expected: `ModuleNotFoundError: No module named 'score'`.

- [ ] **Step 3: Implement** `src/score.py`

```python
"""Nightly scorecard: coverage, freshness, audited accuracy and free automatic flags. No AI."""
import re

from matching import region_of

NETWORKS = ("ABC", "CBS", "NBC", "FOX", "CW", "PBS")
CALLSIGN = re.compile(r"\(([A-Z]{4,5})\)")
COUNTRY_SUFFIXES = {"US": ("us", "com"), "CA": ("ca",), "UK": ("uk",)}
AUDIT_WINDOW = 200
HISTORY_DAYS = 365


def flag_reasons(name, xml_id):
    reasons = []
    region = region_of(name)
    suffix = xml_id.rsplit(".", 1)[-1].lower() if "." in xml_id else ""
    if region in COUNTRY_SUFFIXES and suffix and not suffix.startswith(COUNTRY_SUFFIXES[region]):
        reasons.append("region")
    callsign = CALLSIGN.search(name)
    if callsign and callsign.group(1) not in xml_id.upper():
        reasons.append("callsign")
    in_name = {n for n in NETWORKS if re.search(rf"\b{n}\b", name.upper())}
    in_id = {n for n in NETWORKS if n in xml_id.upper()}
    if in_name and in_id and not (in_name & in_id):
        reasons.append("network")
    return reasons


def audited_accuracy(audit_log):
    recent = [e for e in audit_log if e.get("sample") == "random"][-AUDIT_WINDOW:]
    if not recent:
        return None, 0
    return sum(e["verdict"] == "correct" for e in recent) / len(recent), len(recent)


def scorecard(total_channels, matches, stats, audit_log):
    flags = {}
    for name, xml_id in matches.items():
        reasons = flag_reasons(name, xml_id)
        if reasons:
            flags[name] = reasons
    coverage = len(matches) / total_channels if total_channels else 0.0
    fresh = stats.channels_with_upcoming / stats.channels if stats.channels else 0.0
    accuracy, audited = audited_accuracy(audit_log)
    headline = coverage * fresh * (1.0 if accuracy is None else accuracy)
    return {
        "coverage": round(coverage, 4),
        "fresh": round(fresh, 4),
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "audited": audited,
        "headline": round(headline, 4),
        "headline_basis": "unaudited" if accuracy is None else f"{audited} random audits",
        "flagged": len(flags),
        "flags": flags,
    }


def update_history(history, day, card):
    entry = {"date": day, **{k: card[k] for k in ("coverage", "fresh", "accuracy", "flagged", "headline")}}
    kept = [h for h in history or [] if h.get("date") != day]
    return (kept + [entry])[-HISTORY_DAYS:]
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_score.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/score.py tests/test_score.py
git commit -m "Add nightly scorecard: coverage, freshness, audited accuracy, automatic flags" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: New `main.py` orchestration

**Files:**
- Modify (full rewrite): `src/main.py`
- Modify: `src/console_ui.py` (delete `dashboard`, `progress_bar` and `format_duration`)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6
- Produces:
  - A CLI: `main.py [--channels-from provider|known] [--previous-dir D] [--publish-dir D] [--data-dir D] [--cache-dir D] [--cache-max-age H] [--days-ahead N]`
  - `main.main(argv) -> int`, returning 0, 2 or 3
  - Published files: `epg.xml.gz`, `data/epg_repair.xml.gz`, `status.json`, `channels.json`, `matches.json`, `match_queue.json`, `score_history.json`, `guide_index.json.gz`, `README.md`
  - The shape of `matches.json`: `{name: {"id", "how", "flags"}}`
  - The shape of `match_queue.json`: `{"generated_at", "sources", "queue": [...], "carried": {...}}`

- [ ] **Step 1: Write the failing end-to-end tests** in `tests/test_main.py`

```python
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
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_main.py -q`
Expected: failures, because the old `main.py` imports `ai_client` and `fuzzywuzzy` and has no `main(argv)`.

- [ ] **Step 3: Implement.** Replace all of `src/main.py` with:

```python
"""Nightly EPG build: channel list -> matches (no AI) -> guide -> checks -> scorecard -> publish folder.

Exit codes: 0 published; 2 checks failed, nothing published; 3 published from a fallback channel
list because the IPTV login was rejected or is not configured.
"""
import argparse
import json
import os
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
LOGIN_HELP = "run tools/set_login.py on the PC"


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
    """Return (names, provider_ids, description, login_problem)."""
    saved = [n for n in known if not n.startswith("#") and matching.is_priority_channel(n)]
    if mode == "known":
        return saved, {}, "saved matches", None
    fallback = previous_channels or saved
    label = "last night's list" if previous_channels else "saved matches"
    url, user, password = (os.getenv(k, "").strip() for k in ("XC_URL", "XC_USERNAME", "XC_PASSWORD"))
    if not (url and user and password):
        return fallback, {}, f"{label} (login not configured)", f"The IPTV login is not configured - {LOGIN_HELP}."
    try:
        channels = provider.fetch_channels(url, user, password)
    except provider.LoginRejected as e:
        return fallback, {}, f"{label} (login rejected)", (
            f"The provider rejected the IPTV login ({e}). If the same login works on the PC, the provider "
            f"is blocking GitHub; otherwise {LOGIN_HELP}.")
    except provider.ProviderUnavailable as e:
        ui.warn(f"Provider unavailable ({e}) - using {label}")
        return fallback, {}, f"{label} (provider unavailable)", None
    names = [c["name"] for c in channels if matching.is_priority_channel(c["name"])]
    return names, {c["name"]: c["epg_id"] for c in channels if c["epg_id"]}, "provider", None


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
        f"- Matched: {counts.get('known', 0):,} saved, {counts.get('carried', 0):,} renamed, "
        f"{counts.get('auto', 0):,} automatic",
        f"- Waiting for a Claude matching session: {counts.get('queued', 0):,} (no guide: {counts.get('no_guide', 0):,})",
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
    no_guide = load_json(os.path.join(args.data_dir, "no_guide.json"), {})
    rejected = load_json(os.path.join(args.data_dir, "rejected_matches.json"), {})
    audit_log = load_json(os.path.join(args.data_dir, "audit_log.json"), [])
    prev = args.previous_dir
    previous_channels = load_json(prev and os.path.join(prev, "channels.json"), None)
    previous_status = load_json(prev and os.path.join(prev, "status.json"), {})
    previous_history = load_json(prev and os.path.join(prev, "score_history.json"), [])

    ui.step(1, 5, "Channel list")
    names, provider_ids, list_source, login_problem = get_channel_list(args.channels_from, known, previous_channels)
    names = list(dict.fromkeys(names))
    ui.info(f"{len(names):,} channels from {list_source}")

    ui.step(2, 5, "Guide sources")
    ref = epg_cache.fetch_reference_data(epg_cache.SOURCES, args.cache_dir, args.cache_max_age)

    ui.step(3, 5, "Matching (no AI)")
    result = matching.resolve(names, known, no_guide, ref.by_name, ref.valid_ids, provider_ids, rejected)
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

    card = score.scorecard(len(names), result.matches, stats, audit_log)
    history = score.update_history(previous_history, now.date().isoformat(), card)
    previous_names = set(previous_channels or [])
    added = sorted(set(names) - previous_names) if previous_channels else []
    removed = sorted(previous_names - set(names)) if previous_channels else []
    status = {
        "generated_at": now.isoformat(timespec="seconds"),
        "channel_list": list_source,
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
```

In `src/console_ui.py`, delete `format_duration`, `progress_bar` and `dashboard` (lines 71–170 of the current file). Keep the colours, `enable_windows_ansi`, `banner`, `step`, `success`, `warn`, `error` and `info`.

- [ ] **Step 4: Run the whole suite and see it pass**

Run: `py -m pytest -q`
Expected: all tests pass (`54 passed`).

- [ ] **Step 5: Commit**

```powershell
git add src/main.py src/console_ui.py tests/test_main.py
git commit -m "Rewrite main.py as a non-interactive, AI-free nightly build with checks and scorecard" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Matching and audit session tools

**Files:**
- Create: `src/match_session.py`, `tests/test_match_session.py`

**Interfaces:**
- Consumes: the published `match_queue.json`, `matches.json` and `guide_index.json.gz`, read from `origin/main` or a folder
- Produces a CLI with these subcommands: `show`, `search`, `apply`, `prepass`, `audit` and `audit-apply`
- Produces these pure functions:
  - `pending(queue_doc, known, no_guide)`
  - `apply_decisions(decisions, index_ids, known, no_guide, carried, today) -> (applied, rejected)`
  - `build_prepass(queue_doc, suggestions, index_ids) -> dict`
  - `pick_audit_sample(matches_doc, audit_log, size=25, rng=None) -> dict`
  - `apply_verdicts(verdicts, sample, index_ids, known, no_guide, rejected, audit_log, today) -> (counts, problems)`
  - `load_published(name, source)`
- Local scratch files (gitignored): `decisions*.json`, `verdicts*.json`, `audit_sample.json`

- [ ] **Step 1: Write the failing tests** in `tests/test_match_session.py`

```python
import gzip
import json
import random

import match_session as ms


def test_apply_decisions():
    known = {"US| OLD": "Old.us"}
    no_guide = {"US| X": "2026-01-01"}
    decisions = {"US| CNN": "CNN.us", "US| PPV 1": "NO_GUIDE", "US| MAYBE": "SKIP", "US| BAD": "NotReal.us",
                 "US| X": "ESPN.us"}
    carried = {"US| NEW NAME": {"from": "US| OLD NAME", "id": "ESPN.us"}}
    applied, rejected = ms.apply_decisions(decisions, {"CNN.us", "ESPN.us"}, known, no_guide, carried, "2026-09-26")
    assert known == {"US| OLD": "Old.us", "US| NEW NAME": "ESPN.us", "US| CNN": "CNN.us", "US| X": "ESPN.us"}
    assert no_guide == {"US| PPV 1": "2026-09-26"}
    assert rejected == {"US| BAD": "NotReal.us"}
    assert applied == {"matched": 2, "no_guide": 1, "carried": 1, "skipped": 1}


def test_pending_hides_decided_channels():
    queue_doc = {"queue": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
    assert [e["name"] for e in ms.pending(queue_doc, {"A": "x"}, {"B": "d"})] == ["C"]


def test_prepass_draft():
    queue_doc = {"queue": [{"name": "US| CNN"}, {"name": "SPORTS| PPV EVENT 3"}, {"name": "US| NBC"},
                           {"name": "US| REPLAY CHANNEL"}]}
    suggestions = {"US| CNN": "CNN.us", "US| NBC": "Invented.us", "US| NOT QUEUED": "ESPN.us"}
    assert ms.build_prepass(queue_doc, suggestions, {"CNN.us", "ESPN.us"}) == {
        "US| CNN": "CNN.us", "SPORTS| PPV EVENT 3": "NO_GUIDE", "US| REPLAY CHANNEL": "NO_GUIDE"}


def test_no_guide_pattern_uses_whole_words():
    for name in ("US| PPV 1", "SPORTS| EVENT 12", "US| 24/7 SIMPSONS", "US| NFL REPLAY", "SPORTS| EVENTS 3"):
        assert ms.NO_GUIDE_PATTERN.search(name), name
    for name in ("US| PREVENT TV", "US| DIRECTV", "US| FLOOP"):
        assert not ms.NO_GUIDE_PATTERN.search(name), name


def test_load_published_from_folder(tmp_path):
    (tmp_path / "match_queue.json").write_text(json.dumps({"queue": [{"name": "A"}]}), encoding="utf-8")
    with gzip.open(tmp_path / "guide_index.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"CNN.us": ["CNN"]}, f)
    assert ms.load_published("match_queue.json", str(tmp_path)) == {"queue": [{"name": "A"}]}
    assert ms.load_published("guide_index.json.gz", str(tmp_path)) == {"CNN.us": ["CNN"]}


def test_audit_sample_mixes_flagged_and_random():
    matches = {f"US| CH{i}": {"id": f"C{i}.us", "how": "saved", "flags": []} for i in range(40)}
    matches.update({f"US| BAD{i}": {"id": f"B{i}.uk", "how": "auto", "flags": ["region"]} for i in range(20)})
    sample = ms.pick_audit_sample(matches, [], size=10, rng=random.Random(1))
    kinds = [v["sample"] for v in sample.values()]
    assert len(sample) == 10 and kinds.count("flagged") == 5 and kinds.count("random") == 5
    assert all(not v["flags"] for v in sample.values() if v["sample"] == "random")


def test_audit_skips_flagged_matches_already_confirmed():
    matches = {"US| A": {"id": "A.uk", "how": "saved", "flags": ["region"]}}
    log = [{"name": "US| A", "id": "A.uk", "verdict": "correct", "sample": "flagged"}]
    assert ms.pick_audit_sample(matches, log, size=2, rng=random.Random(1)) == {}


def test_apply_verdicts():
    sample = {
        "US| A": {"id": "A.us", "how": "saved", "flags": [], "sample": "random"},
        "US| B": {"id": "B.uk", "how": "auto", "flags": ["region"], "sample": "flagged"},
        "US| C": {"id": "C.us", "how": "saved", "flags": [], "sample": "random"},
        "US| D": {"id": "D.us", "how": "renamed", "flags": [], "sample": "random"},
        "US| E": {"id": "E.us", "how": "saved", "flags": [], "sample": "random"},
    }
    known = {"US| A": "A.us", "US| C": "C.us", "US| E": "E.us"}
    no_guide, rejected, log = {}, {}, []
    verdicts = {"US| A": "correct", "US| B": "B.us", "US| C": "wrong", "US| D": "NO_GUIDE", "US| E": "Fake.us",
                "US| Z": "correct"}
    counts, problems = ms.apply_verdicts(verdicts, sample, {"A.us", "B.us", "C.us", "D.us", "E.us"},
                                         known, no_guide, rejected, log, "2026-09-26")
    assert known == {"US| A": "A.us", "US| E": "E.us", "US| B": "B.us"}
    assert no_guide == {"US| D": "2026-09-26"}
    assert rejected == {"US| B": ["B.uk"], "US| C": ["C.us"], "US| D": ["D.us"]}
    assert [(e["name"], e["verdict"], e["sample"]) for e in log] == [
        ("US| A", "correct", "random"), ("US| B", "wrong", "flagged"), ("US| C", "wrong", "random"),
        ("US| D", "wrong", "random")]
    assert counts == {"correct": 1, "fixed": 1, "no_guide": 1, "wrong": 1}
    assert problems == {"US| E": "Fake.us is not a real guide ID", "US| Z": "not in the current audit sample"}


def test_apply_command_end_to_end(tmp_path, monkeypatch):
    published = tmp_path / "publish"
    published.mkdir()
    (published / "match_queue.json").write_text(json.dumps({"queue": [], "carried": {}}), encoding="utf-8")
    with gzip.open(published / "guide_index.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"CNN.us": ["CNN"]}, f)
    monkeypatch.setattr(ms, "KNOWN_FILE", str(tmp_path / "known.json"))
    monkeypatch.setattr(ms, "NO_GUIDE_FILE", str(tmp_path / "no_guide.json"))
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({"US| CNN": "CNN.us"}), encoding="utf-8")
    assert ms.main(["--source", str(published), "apply", str(decisions)]) == 0
    assert json.loads((tmp_path / "known.json").read_text(encoding="utf-8")) == {"US| CNN": "CNN.us"}
```

- [ ] **Step 2: Run them and see them fail**

Run: `py -m pytest tests/test_match_session.py -q`
Expected: `ModuleNotFoundError: No module named 'match_session'`.

- [ ] **Step 3: Implement** `src/match_session.py`

```python
"""Tools for Claude matching and audit sessions - see CLAUDE.md.

There are no AI API calls here: Claude reads the output and decides in-session.
"""
import argparse
import gzip
import json
import os
import random
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN_FILE = os.path.join(ROOT, "data", "known_matches.json")
NO_GUIDE_FILE = os.path.join(ROOT, "data", "no_guide.json")
REJECTED_FILE = os.path.join(ROOT, "data", "rejected_matches.json")
AUDIT_LOG_FILE = os.path.join(ROOT, "data", "audit_log.json")
AUDIT_SAMPLE_FILE = os.path.join(ROOT, "audit_sample.json")
NO_GUIDE_PATTERN = re.compile(r"\b(PPV|EVENTS?|REPLAY|LOOP)\b|\b24/7\b", re.IGNORECASE)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def load_published(name, source):
    """Read a file the nightly job published, from a local folder or a git ref such as origin/main."""
    if os.path.isdir(source):
        with open(os.path.join(source, name), "rb") as f:
            raw = f.read()
    else:
        raw = subprocess.run(["git", "show", f"{source}:{name}"], cwd=ROOT, capture_output=True, check=True).stdout
    if name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def pending(queue_doc, known, no_guide):
    return [e for e in queue_doc.get("queue", []) if e["name"] not in known and e["name"] not in no_guide]


def apply_decisions(decisions, index_ids, known, no_guide, carried, today):
    applied = {"matched": 0, "no_guide": 0, "carried": 0, "skipped": 0}
    rejected = {}
    for name, entry in carried.items():
        if name not in known and entry["id"] in index_ids:
            known[name] = entry["id"]
            applied["carried"] += 1
    for name, decision in decisions.items():
        if decision == "SKIP":
            applied["skipped"] += 1
        elif decision == "NO_GUIDE":
            no_guide[name] = today
            known.pop(name, None)
            applied["no_guide"] += 1
        elif decision in index_ids:
            known[name] = decision
            no_guide.pop(name, None)
            applied["matched"] += 1
        else:
            rejected[name] = decision
    return applied, rejected


def build_prepass(queue_doc, suggestions, index_ids):
    draft = {}
    for entry in queue_doc.get("queue", []):
        name = entry["name"]
        if NO_GUIDE_PATTERN.search(name):
            draft[name] = "NO_GUIDE"
        elif suggestions.get(name) in index_ids:
            draft[name] = suggestions[name]
    return draft


def pick_audit_sample(matches_doc, audit_log, size=25, rng=None):
    """Up to half flagged matches (not already confirmed), the rest a random sample of unflagged matches."""
    rng = rng or random.Random()
    confirmed = {(e["name"], e["id"]) for e in audit_log if e["verdict"] == "correct"}
    flagged = [(n, m) for n, m in sorted(matches_doc.items()) if m.get("flags") and (n, m["id"]) not in confirmed]
    flagged = flagged[: size // 2]
    others = [(n, m) for n, m in sorted(matches_doc.items()) if not m.get("flags")]
    randoms = rng.sample(others, min(size - len(flagged), len(others)))
    sample = {n: {"id": m["id"], "how": m["how"], "flags": m["flags"], "sample": "flagged"} for n, m in flagged}
    sample.update({n: {"id": m["id"], "how": m["how"], "flags": [], "sample": "random"} for n, m in randoms})
    return sample


def apply_verdicts(verdicts, sample, index_ids, known, no_guide, rejected, audit_log, today):
    counts = {"correct": 0, "fixed": 0, "no_guide": 0, "wrong": 0}
    problems = {}
    for name, verdict in verdicts.items():
        info = sample.get(name)
        if info is None:
            problems[name] = "not in the current audit sample"
            continue
        if verdict not in ("correct", "wrong", "NO_GUIDE") and verdict not in index_ids:
            problems[name] = f"{verdict} is not a real guide ID"
            continue
        audit_log.append({"date": today, "name": name, "id": info["id"], "how": info["how"],
                          "sample": info["sample"], "verdict": "correct" if verdict == "correct" else "wrong"})
        if verdict == "correct":
            counts["correct"] += 1
            continue
        refused = rejected.setdefault(name, [])
        if info["id"] not in refused:
            refused.append(info["id"])
        if verdict == "NO_GUIDE":
            known.pop(name, None)
            no_guide[name] = today
            counts["no_guide"] += 1
        elif verdict == "wrong":
            known.pop(name, None)
            counts["wrong"] += 1
        else:
            known[name] = verdict
            no_guide.pop(name, None)
            counts["fixed"] += 1
    return counts, problems


def refresh(source):
    if not os.path.isdir(source) and source.startswith("origin/"):
        subprocess.run(["git", "fetch", "-q", "origin", source.split("/", 1)[1]], cwd=ROOT, check=True)


def cmd_show(args):
    queue_doc = load_published("match_queue.json", args.source)
    todo = pending(queue_doc, load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {}))
    print(f"{len(todo):,} channels waiting (queue built {queue_doc.get('generated_at')})")
    failed = [k for k, v in queue_doc.get("sources", {}).items() if v == "failed"]
    if failed:
        print(f"Sources that failed that night: {', '.join(failed)} - leave their vanished_id entries alone")
    for entry in todo[args.offset:args.offset + args.batch]:
        extra = "".join(f" {k}={entry[k]}" for k in ("previous_id", "provider_id") if k in entry)
        print(f"\n## {entry['name']}  [{entry['reason']}{extra}]")
        for c in entry["candidates"]:
            print(f"   {c['id']}  --  {c['name']}")


def cmd_search(args):
    index = load_published("guide_index.json.gz", args.source)
    needle = args.text.lower()
    hits = [(i, n) for i, n in index.items() if needle in i.lower() or any(needle in x.lower() for x in n)]
    for i, n in hits[:args.limit]:
        print(f"{i}  --  {' | '.join(n[:4])}")
    print(f"({len(hits):,} matches)")


def cmd_apply(args):
    index_ids = set(load_published("guide_index.json.gz", args.source))
    carried = load_published("match_queue.json", args.source).get("carried", {})
    known, no_guide = load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {})
    applied, rejected = apply_decisions(load_json(args.decisions, {}), index_ids, known, no_guide, carried,
                                        date.today().isoformat())
    save_json(KNOWN_FILE, known)
    save_json(NO_GUIDE_FILE, no_guide)
    print("Applied:", applied)
    for name, value in rejected.items():
        print(f"REJECTED (not a real guide ID): {name} -> {value}")
    return 1 if rejected else 0


def cmd_prepass(args):
    queue_doc = load_published("match_queue.json", args.source)
    index_ids = set(load_published("guide_index.json.gz", args.source))
    draft = build_prepass(queue_doc, load_json(args.suggestions, {}), index_ids)
    save_json(args.out, draft)
    no_guide = sum(1 for v in draft.values() if v == "NO_GUIDE")
    print(f"Draft written to {args.out}: {len(draft) - no_guide:,} suggested matches, {no_guide:,} NO_GUIDE "
          f"by name. Review it, then run apply on it.")


def cmd_audit(args):
    matches_doc = load_published("matches.json", args.source)
    index = load_published("guide_index.json.gz", args.source)
    sample = pick_audit_sample(matches_doc, load_json(AUDIT_LOG_FILE, []), args.size)
    save_json(AUDIT_SAMPLE_FILE, sample)
    print(f"Audit sample of {len(sample)} saved to {AUDIT_SAMPLE_FILE}. Verdicts: correct | wrong | NO_GUIDE | <right ID>")
    for name, info in sample.items():
        flags = f" FLAGS={','.join(info['flags'])}" if info["flags"] else ""
        display = index.get(info["id"]) or ["(not in tonight's sources)"]
        print(f"\n## {name}  [{info['sample']}, {info['how']}{flags}]")
        print(f"   {info['id']}  --  {' | '.join(display[:4])}")


def cmd_audit_apply(args):
    sample = load_json(AUDIT_SAMPLE_FILE, {})
    index_ids = set(load_published("guide_index.json.gz", args.source))
    known, no_guide = load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {})
    rejected, audit_log = load_json(REJECTED_FILE, {}), load_json(AUDIT_LOG_FILE, [])
    counts, problems = apply_verdicts(load_json(args.verdicts, {}), sample, index_ids, known, no_guide, rejected,
                                      audit_log, date.today().isoformat())
    for path, data in ((KNOWN_FILE, known), (NO_GUIDE_FILE, no_guide), (REJECTED_FILE, rejected),
                       (AUDIT_LOG_FILE, audit_log)):
        save_json(path, data)
    print("Recorded:", counts)
    for name, problem in problems.items():
        print(f"NOT RECORDED: {name}: {problem}")
    if not problems:
        os.remove(AUDIT_SAMPLE_FILE)
    return 1 if problems else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="origin/main", help="git ref or local publish folder to read from")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("show", help="next channels waiting to be matched")
    s.add_argument("--batch", type=int, default=50)
    s.add_argument("--offset", type=int, default=0)
    s.set_defaults(func=cmd_show)
    s = sub.add_parser("search", help="search every guide channel")
    s.add_argument("text")
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(func=cmd_search)
    s = sub.add_parser("apply", help="save match decisions")
    s.add_argument("decisions")
    s.set_defaults(func=cmd_apply)
    s = sub.add_parser("prepass", help="first session: draft decisions from March suggestions and name patterns")
    s.add_argument("--suggestions", default=os.path.join(ROOT, "suggested_matches.json"))
    s.add_argument("--out", default=os.path.join(ROOT, "decisions_prepass.json"))
    s.set_defaults(func=cmd_prepass)
    s = sub.add_parser("audit", help="sample tonight's matches for checking")
    s.add_argument("--size", type=int, default=25)
    s.set_defaults(func=cmd_audit)
    s = sub.add_parser("audit-apply", help="record audit verdicts and fix wrong matches")
    s.add_argument("verdicts")
    s.set_defaults(func=cmd_audit_apply)
    args = p.parse_args(argv)
    refresh(args.source)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `py -m pytest tests/test_match_session.py -q`
Expected: `9 passed`. Also run `py -m pytest -q` and expect everything to pass.

- [ ] **Step 5: Commit**

```powershell
git add src/match_session.py tests/test_match_session.py
git commit -m "Add Claude matching and audit session tools" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Remove Gemini and retired files; docs; new data files

**Files:**
- Delete:
  - Gemini: `src/ai_client.py`, `src/analyze.py`, `src/audit_matches.py`, `src/hunt_missing.py`, `src/recycle_missing.py`, `check_models.py`
  - Unused code: `src/clean_log.py`, `src/filter_missing.py`, `src/channel_database.py`
  - Retired run scripts: `run_epg_bridge.bat`, `run_epg_bridge.sh`, `setup_cron.sh`, `check_epg_status.sh`, `src/update_all.bat`, `src/update_all.sh`, `src/weekly_maintenance.bat`, `src/push_to_github.py`, `src/deploy_epg.py`
  - Junk: `files.zip`, `src/New Text Document.txt`, `audit_report.md`, `src/data/`
- Untrack but keep locally: `epg.xml.gz`, `src/epg.xml.gz`, `data/epg_repair.xml`, `data/epg_repair.xml.gz`, `data/playlist_cache.json`, everything under `logs/`, `suggested_matches.json`
- Create: `data/no_guide.json`, `data/rejected_matches.json`, `data/audit_log.json`, `CLAUDE.md`
- Modify: `.gitignore`, `.env.example`, `README.md`
- Add (already written): `tools/set_login.py`, the spec, and this plan

- [ ] **Step 1: Remove and untrack**

```powershell
git rm -q src/ai_client.py src/analyze.py src/audit_matches.py src/hunt_missing.py src/recycle_missing.py check_models.py src/clean_log.py src/filter_missing.py src/channel_database.py run_epg_bridge.bat run_epg_bridge.sh setup_cron.sh check_epg_status.sh src/update_all.bat src/update_all.sh src/weekly_maintenance.bat src/push_to_github.py src/deploy_epg.py files.zip "src/New Text Document.txt" audit_report.md
git rm -q -r src/data
git rm -q --cached epg.xml.gz src/epg.xml.gz data/epg_repair.xml data/epg_repair.xml.gz data/playlist_cache.json suggested_matches.json
git rm -q -r --cached logs
```

Run: `Select-String -Path src\*.py,tests\*.py,requirements*.txt -Pattern "genai|gemini|fuzzywuzzy|ai_client" -List`
Expected: no output.

- [ ] **Step 2: New data files.** Each of `data/no_guide.json` and `data/rejected_matches.json` contains `{}` plus a newline. `data/audit_log.json` contains `[]` plus a newline.

- [ ] **Step 3: `.gitignore`** (replace the whole file)

```
.env
venv/
venv_nas/
__pycache__/
.pytest_cache/

# Generated locally or by the nightly job (published on the main branch)
publish/
previous/
data/cache/
logs/
*.log
epg.xml
epg*.xml.gz
data/epg_repair.xml
data/epg_repair.xml.gz
data/playlist_cache.json

# Matching-session scratch files
suggested_matches.json
decisions*.json
verdicts*.json
audit_sample.json

*.zip
```

- [ ] **Step 4: `.env.example`** (replace the whole file)

```
# IPTV provider login - set it with: venv\Scripts\python tools\set_login.py
XC_URL=http://your.provider.com
XC_USERNAME=your_username
XC_PASSWORD=your_password

# Hours to reuse downloaded guide sources on local runs
CACHE_MAX_AGE=24
```

- [ ] **Step 5: `README.md`** (replace the whole file)

````markdown
# EPG Bridge

Builds a merged XMLTV TV guide for an IPTV channel list, for TiviMate.

- **Nightly build:** `.github/workflows/nightly.yml` runs `src/main.py` on GitHub every night. It does four things:
  - reads the provider's channel list
  - matches channels to free guide sources using saved matches and simple rules (no AI)
  - checks the result
  - publishes it to the `main` branch (`epg.xml.gz`)
- **Scorecard:** every run reports coverage, freshness, audited accuracy and flagged matches. See `status.json` and `score_history.json` on `main`, or the run summary.
- **New channels and audits:** handled in a Claude Code session. See `CLAUDE.md`.
- **Login changed?** Run `venv\Scripts\python tools\set_login.py`.

## Local setup

```
python -m venv venv
venv\Scripts\pip install -r requirements-dev.txt
venv\Scripts\python -m pytest -q
venv\Scripts\python src\main.py --channels-from known --publish-dir publish
```

## Layout

- `src/main.py`: the nightly build. It uses:
  - `provider.py` for the channel list
  - `epg_cache.py` for the guide sources
  - `matching.py`, `guide.py`, `checks.py`, `score.py` and `publish.py`
- `src/match_session.py`: tools for Claude matching and audit sessions
- `data/known_matches.json`: channel name → guide ID
- `data/no_guide.json`, `data/rejected_matches.json`, `data/audit_log.json`: session decisions
````

- [ ] **Step 6: `CLAUDE.md`**

```markdown
# EPG Bridge - notes for Claude

This project builds the TV guide (XMLTV) that TiviMate uses for the user's IPTV channels.

## How it runs
- `.github/workflows/nightly.yml` runs `src/main.py` on GitHub every night at 09:00 UTC. It runs from the `code` branch, which is the default, and force-pushes the result to the publish-only `main` branch.
- TiviMate reads `main/epg.xml.gz` through tinyurl.com/bdzutmzd. The same file is also at `main/data/epg_repair.xml.gz` for tinyurl.com/5xkmff7s. Those paths must keep working.
- Guide channel IDs are the provider's exact channel names, which is how TiviMate matches them. Never rename or "clean up" names in `data/known_matches.json`.
- Tonight's results are on `main`:
  - `status.json`: counts and the scorecard
  - `matches.json`: every match and how it was made
  - `match_queue.json`: channels waiting to be matched
  - `score_history.json`: the scorecard over time

## Hard rules
- No AI or LLM API calls in this project: not Gemini, OpenAI, Anthropic or anything else. It was shut down once for burning API credits. You do the matching and auditing yourself, in the session.
- Never type, paste or store the IPTV password. If the login changes, the user runs `venv\Scripts\python tools\set_login.py`.
- Never commit to `main`. The workflow owns it. Work on `code`.
- The repo is public. Never commit `.env`, the provider's address or raw playlist data.

## Session routine ("match the queue")
Run everything from the repo root (`C:\Users\Admin\Documents\AI_EPG_Bridge`), on `code`. Start with `git pull`.

### 1. Audit first (every session)
1. `venv\Scripts\python src\match_session.py audit` shows 25 of tonight's matches. Up to half are flagged matches; the rest are a random sample.
2. Write `verdicts.json` in the form `{"<exact channel name>": "correct" | "wrong" | "NO_GUIDE" | "<right guide ID>"}`.
3. `venv\Scripts\python src\match_session.py audit-apply verdicts.json` records the verdicts, which drive the Accuracy score. It also fixes or removes wrong matches. The automatic rules never pick a rejected pair again.

### 2. Match the queue
1. `venv\Scripts\python src\match_session.py show` lists the next 50 channels waiting, each with its guide candidates (`ID -- display name`). Add `--offset 50` for the next page.
2. When a channel is unclear, `venv\Scripts\python src\match_session.py search "<text>"` searches every guide channel.
3. Write `decisions.json` in the form `{"<exact channel name>": "<guide ID>" | "NO_GUIDE" | "SKIP"}`.
4. `venv\Scripts\python src\match_session.py apply decisions.json` rejects anything that isn't a real guide ID. It saves `data/known_matches.json` and `data/no_guide.json`, along with tonight's automatic renames.
5. After every batch, commit the changed files under `data/` and push, so progress survives if the session ends. Use a commit message like "Match session: +N matched, +M no guide".

### How to decide
- **Region:** US channels take IDs ending in `.us`, `.us2`, `.us_locals1` and so on. Canadian channels take `.ca` and UK channels `.uk`.
- **Call signs win:** "ABC (WABC)" gets the WABC ID, not a generic ABC.
- **Same network only:** a FOX channel never gets a CBS, NBC or ABC affiliate.
- **Exact content:** "Discovery" is not "Discovery Science", "AMC" is not "AMC+", and "Sportsnet Ontario" is not "Sportsnet West".
- **Feeds:** "West" and "Pacific" are the same feed. "East" is the default.
- **No guide:** pay-per-view, event, replay and 24/7 loop channels are `NO_GUIDE`.
- **Unsure:** use `SKIP`, which leaves the channel queued. A wrong guide is worse than none.

If `show` says a source failed that night, leave that night's `vanished_id` entries alone. They clear once the source is back.

### First session only
`venv\Scripts\python src\match_session.py prepass` writes `decisions_prepass.json`, drafted from two things:
- the March AI suggestions (`suggested_matches.json`, which exists only on the PC)
- the NO_GUIDE name patterns

Review the draft, drop anything wrong, then `apply` it.

## Local test build
`venv\Scripts\python src\main.py --channels-from known --publish-dir publish` builds into `publish/` without touching GitHub.

Tests: `venv\Scripts\python -m pytest -q`
```

- [ ] **Step 7: Check and commit**

Run: `py -m pytest -q` (expect everything to pass), then `git status --short` (expect no `.env` and no large files staged).

```powershell
git add -A .gitignore .env.example README.md CLAUDE.md data/no_guide.json data/rejected_matches.json data/audit_log.json tools/set_login.py docs
git commit -m "Remove Gemini and retired scripts, stop tracking generated files, add session docs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Nightly workflow

**Files:**
- Create: `.github/workflows/nightly.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: Nightly guide

on:
  schedule:
    - cron: "0 9 * * *"  # 3 AM MDT / 2 AM MST
  workflow_dispatch:
    inputs:
      publish:
        description: "Publish to main (leave unticked for a test run)"
        type: boolean
        default: false
  push:
    branches: [code]
    paths:
      - "src/**"
      - "tests/**"
      - "requirements*.txt"
      - ".github/workflows/nightly.yml"

permissions:
  contents: write

concurrency:
  group: nightly-guide
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    env:
      PUBLISH: ${{ github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && inputs.publish) }}
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: requirements*.txt

      - name: Install
        run: pip install -r requirements-dev.txt

      - name: Unit tests
        run: python -m pytest -q

      - name: Get last night's published files
        run: |
          mkdir -p previous
          if git fetch -q --depth=1 origin main; then
            for f in channels.json status.json score_history.json; do
              git show "FETCH_HEAD:$f" > "previous/$f" 2>/dev/null || rm -f "previous/$f"
            done
          fi

      - name: Build guide
        id: build
        env:
          XC_URL: ${{ secrets.XC_URL }}
          XC_USERNAME: ${{ secrets.XC_USERNAME }}
          XC_PASSWORD: ${{ secrets.XC_PASSWORD }}
        run: |
          set +e
          python -u src/main.py --previous-dir previous --publish-dir publish
          code=$?
          echo "exit_code=$code" >> "$GITHUB_OUTPUT"
          if [ "$code" -ne 0 ] && [ "$code" -ne 3 ]; then exit "$code"; fi

      - name: Keep test build
        if: env.PUBLISH != 'true'
        uses: actions/upload-artifact@v7
        with:
          name: guide-test-build
          path: publish/
          retention-days: 3

      - name: Publish to main
        if: env.PUBLISH == 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          cd publish
          git init -q -b main
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -q -m "Guide $(date -u +%Y-%m-%d)"
          git push -q --force "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" main

      - name: Fail loudly about the login
        if: steps.build.outputs.exit_code == '3'
        run: |
          echo "::error::The provider rejected the IPTV login (or it isn't set). Run tools/set_login.py on the PC."
          exit 1
```

- [ ] **Step 2: Validate the YAML locally**

Run: `py -c "import yaml,sys; yaml.safe_load(open('.github/workflows/nightly.yml')); print('ok')"`. If PyYAML is missing, run `py -m pip install pyyaml` first.
Expected: `ok`.

- [ ] **Step 3: Commit**

```powershell
git add .github/workflows/nightly.yml
git commit -m "Add nightly GitHub Actions build that publishes to main" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Full local test build against real sources

- [ ] **Step 1: Build.** Use the provider when the login works, falling back to the saved list otherwise.

Run: `py -u src\main.py --publish-dir publish --cache-max-age 0`
Expected: exit code 0 (or 3 if the login is still out of date). Every source except any temporarily down shows `downloaded`. Runtime under 45 minutes.

- [ ] **Step 2: Compare with March**, using `publish\status.json`:
  - `channels`: roughly 6,100 or more (March had 6,112)
  - `size_mb`: well under 45 MB
  - `channels_with_upcoming`: at least 80% of `channels`
  - `score.coverage` and `score.flagged`: record these as the baseline
  - `counts.queued`: the size of the matching backlog

- [ ] **Step 3: Check that stopping at the first programme misses no channels.** Run a full-parse count of channel IDs over each cached source and compare it with `parse_epg_channels`. The totals must be equal. If one isn't, change `parse_epg_channels` to keep reading, clearing each programme element, and repeat the build.

- [ ] **Step 4: Spot-check the guide** by opening `publish\epg.xml.gz`:
  - it parses
  - a few well-known channels (for example `US| CNN`) have programmes for today
  - no channel ID carries whitespace changes compared with the provider's names

---

### Task 12: Push `code` and let GitHub run a test build

- [ ] **Step 1:** `git push -u origin code`. This triggers the push-event test run, which doesn't publish.
- [ ] **Step 2:** Watch it with `gh run list --branch code --limit 1`, then `gh run watch <id> --exit-status`.
  - Expected: the tests pass and the build exits 0.
  - Exit code 3 with "login rejected" means the provider rejects GitHub or the secrets are wrong. Compare against a local provider fetch.
- [ ] **Step 3:** Download the artifact (`gh run download <id> -n guide-test-build -D previous_test`) and compare its `status.json` with the local build: channel list source, counts, size and sources.

---

### Task 13: Go live (needs one "yes" from the user)

- [ ] **Step 1: Ask for confirmation.** Ask once: "Switch the repo's default branch to `code` and replace `main` with the new guide?"
- [ ] **Step 2: Switch the default branch.** Run `gh repo edit mattdawe-collab/epg-host --default-branch code`.
- [ ] **Step 3: Publish.** Run `gh workflow run nightly.yml --ref code -f publish=true`, then watch it until it succeeds.
- [ ] **Step 4: Verify.**
  - `Invoke-WebRequest https://tinyurl.com/bdzutmzd -Method Head` and `https://tinyurl.com/5xkmff7s` both report the new size.
  - Download the guide and confirm programmes exist for today and tomorrow.
  - `gh api repos/mattdawe-collab/epg-host --jq .default_branch` returns `code`.
  - The workflow is `active` in `gh workflow view nightly.yml`.
- [ ] **Step 5: Tidy up locally.** In the PC copy, delete `previous_test/` and `publish/`. Both are gitignored build outputs.

---

### Task 14: Wrap-up

- [ ] **Step 1: Update memory.** The working copy is now the PC copy on `code`, and the NAS copy is retired. Copy the project memories into the PC project's memory folder, `C:\Users\Admin\.claude\projects\C--Users-Admin-Documents-AI-EPG-Bridge\memory\`.
- [ ] **Step 2: Report to the user.** Tell them:
  - the headline score and its parts
  - the backlog size
  - how to remove the NAS cron line
  - the recommendation to delete the Gemini key
  - that the first matching and audit session is the next step
````
