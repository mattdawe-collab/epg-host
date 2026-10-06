# EPG Bridge - notes for Claude

This project builds the TV guide (XMLTV) that TiviMate uses for the user's IPTV channels.

## How it runs
- `.github/workflows/nightly.yml` runs `src/main.py` on GitHub every night at 09:00 UTC. It runs from the `code` branch, which is the default, and force-pushes the result to the publish-only `main` branch.
- TiviMate reads `main/epg.xml.gz` through tinyurl.com/bdzutmzd. The same file is also at `main/data/epg_repair.xml.gz` for tinyurl.com/5xkmff7s. Those paths must keep working.
- Guide channel IDs are the provider's exact channel names, which is how TiviMate matches them. Never rename or "clean up" names in `data/known_matches.json`.
- The provider's names look like `US: CNN HD`; the tag before `: ` is the group. Until 2026 they looked like `US| CNN HD`, and the saved matches under old names carry over automatically (see `TAG_ALIASES` in `src/matching.py`).
- Tonight's results are on `main`:
  - `status.json`: counts and the scorecard
  - `matches.json`: every match and how it was made
  - `match_queue.json`: channels waiting to be matched
  - `score_history.json`: the scorecard over time

## Data files (on `code`)
- `data/known_matches.json`: trusted decisions from Claude sessions, including matches confirmed in audits. They always win.
- `data/legacy_matches.json`: old Gemini-era matches, keyed by the provider's old `|` names. Audits found about 40% of them wrong. They're used, or carried over to the new names, only when they pass the free checks (country, callsign, network).
- `data/no_guide.json`, `data/rejected_matches.json` and `data/audit_log.json`: session decisions and the audit history that drives the Accuracy score.
- Pay-per-view, event, replay, loop and 24/7 channels are settled as "no guide" automatically and left out of coverage.

## Provider access (since 2026-09-30)
The provider sits behind Cloudflare bot protection: scripted requests get HTTP 403, from GitHub and from the PC alike. The nightly build reuses the last channel list it saw (from 2026-09-29) and says so in `status.json`. Don't try to get around the protection (no fake browser headers, no proxies). If channel names change, ask the user for a playlist export they download themselves.

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
3. `venv\Scripts\python src\match_session.py audit-apply verdicts.json` records the verdicts, which drive the Accuracy score.
   - `correct` saves the match to `known_matches.json` as trusted.
   - `wrong` or `NO_GUIDE` rejects the pair; the automatic rules never pick it again.

### 2. Match the queue
1. `venv\Scripts\python src\match_session.py show` lists the next 50 channels waiting, each with its guide candidates (`ID -- display name`). Add `--offset 50` for the next page.
2. When a channel is unclear, `venv\Scripts\python src\match_session.py search "<text>"` searches every guide channel.
3. Write `decisions.json` in the form `{"<exact channel name>": "<guide ID>" | "NO_GUIDE" | "SKIP"}`.
4. `venv\Scripts\python src\match_session.py apply decisions.json` rejects anything that isn't a real guide ID. It saves `data/known_matches.json` and `data/no_guide.json`, along with tonight's automatic renames.
5. After every batch, commit the changed files under `data/` and push, so progress survives if the session ends. Use a commit message like "Match session: +N matched, +M no guide".

### How to decide
- **Region:** US channels take IDs ending in `.us`, `.us2`, `.us_locals1` and so on. Canadian channels take `.ca` and UK channels `.uk`.
- **Call signs win:** "ABC (WABC)" gets the WABC ID, not a generic ABC. The nightly build already matches callsigns automatically. The queue holds the locals with no callsign in the name, like "US: ABC 3 HD [PENSACOLA]"; use your knowledge of US TV markets to find the station (WEAR) and `search` for it.
- **Sub-channels:** when the network is on a station's second channel (NBC on WPTA-DT2 in Fort Wayne), pick the `-DT2` ID.
- **Same network only:** a FOX channel never gets a CBS, NBC or ABC affiliate.
- **Exact content:** "Discovery" is not "Discovery Science", "AMC" is not "AMC+", and "Sportsnet Ontario" is not "Sportsnet West".
- **Feeds:** "West" and "Pacific" are the same feed. "East" is the default.
- **Rebrands:** EPIX is now MGM+ (EPIX 2 = MGM+ Hits, EPIX Hits = MGM+ Marquee); Showtime is Paramount+ with Showtime; the guide calls most Sky Cinema channels "Sky Action", "Sky Premiere" and so on. When you find another rebrand, add it to `BRAND_ALIASES` in `src/matching.py`, with a test.
- **No guide:** pay-per-view, event, replay and 24/7 loop channels are `NO_GUIDE`.
- **Unsure:** use `SKIP`, which leaves the channel queued. A wrong guide is worse than none.

A queue entry with `reason: unverified_legacy` had an old Gemini match that failed the checks. Its `previous_id` is that old guess, and it is usually a wrong-country feed.

If `show` says a source failed that night, leave that night's `vanished_id` entries alone. They clear once the source is back.

### First session only
`venv\Scripts\python src\match_session.py prepass` writes `decisions_prepass.json`, drafted from two things:
- the March AI suggestions (`suggested_matches.json`, which exists only on the PC)
- the NO_GUIDE name patterns

Review the draft, drop anything wrong, then `apply` it.

## Local test build
`venv\Scripts\python src\main.py --channels-from known --publish-dir publish` builds into `publish/` without touching GitHub.

Tests: `venv\Scripts\python -m pytest -q`
