# EPG Bridge revival: zero-API nightly build — design

Date: 2026-09-26 · Status: draft for review · Repo: `mattdawe-collab/epg-host` (public)

## Why

The bridge builds a merged XMLTV guide for TiviMate by matching your IPTV provider's channels to free guide sources. It was switched off around March 2026 because Gemini API calls used up your credits. The published guide hasn't changed since 2026-03-25.

| What went wrong | What this design does |
|---|---|
| Every run re-sent the ~2,400 never-matched channels to Gemini, with no cap | No AI API calls at all. Matching happens in Claude sessions, and answers are remembered |
| Runs were manual (PC) or failed silently: the NAS cron failed ~190 nights, and the NAS's March commits never reached GitHub | A nightly GitHub Actions run. GitHub emails you when it fails |
| Every update added a 45 MB file to git history (repo is now ~430 MB) | The guide is published to a branch that's replaced each night |
| The `epghub.xyz` source has been dead since ~Feb 2026 | Removed |
| A provider rename silently drops that channel's guide | The nightly job reads the current channel list and carries simple renames over |

## Decisions (2026-09-26)

1. No AI API calls anywhere in the pipeline. New channels are matched by Claude inside Claude Code sessions, which uses your Claude plan instead of API credits.
2. The nightly build runs on GitHub Actions, not the NAS or the PC.
3. The nightly job reads the channel list using an IPTV login stored as an encrypted GitHub secret. If GitHub can't reach the provider, the fallback is refreshing the list during Claude sessions on the PC.
4. The TinyURLs keep working without changing TinyURL or TiviMate.
5. The PC copy (`C:\Users\Admin\Documents\AI_EPG_Bridge`) becomes the only working copy. The NAS copy is retired.

## Goals

- TiviMate's guide refreshes every night with no action from you.
- Zero AI API calls, now or by accident.
- `tinyurl.com/bdzutmzd` (→ `main/epg.xml.gz`) and `tinyurl.com/5xkmff7s` (→ `main/data/epg_repair.xml.gz`) serve the fresh guide.
- The guide follows provider channel renames, additions and removals.
- New channels are matched in Claude sessions, and a settled channel is never asked about twice.
- A broken run never replaces a good guide, and you hear about it.
- The repo stops growing.
- We score ourselves every night on coverage, freshness and audited accuracy (see Scorecard).

**Not in scope:**
- Changing the guide format TiviMate depends on (channel IDs = provider channel names).
- Rewriting old git history.
- Smarter matching beyond rename carry-over.
- `tinyurl.com/4df342dp`. It points at the uncompressed `data/epg_repair.xml`, and the full guide uncompressed is far over GitHub's 100 MB file limit. After the switch that link returns "not found". Today it serves a 0.2 MB file from 2025-12-31, so nothing that works now depends on it.

## Overview

```
Nightly (GitHub Actions)                                          Published on `main` (replaced nightly)
  provider API  ─► channel list ─┐                                ├─ epg.xml.gz              ◄─ tinyurl bdzutmzd
  guide sources ─► downloads ────┼─► match ─► build ─► checks ─►  ├─ data/epg_repair.xml.gz  ◄─ tinyurl 5xkmff7s
  `code` branch ─► saved matches ┘   (no AI)                      └─ queue, guide index, channel list, status

On demand (Claude session on the PC): read queue from `main` ─► decide ─► validate ─► save to `code`
```

## Branches

- **`code`** (new, becomes the repo's default branch) holds the source code plus the curated data:
  - `data/known_matches.json`: channel name → guide ID.
  - `data/no_guide.json`: channels settled as having no guide.

  It changes only when the code changes or a matching session saves.
- **`main`** (publish-only) is rebuilt every night as a single commit with no history and force-pushed. It holds only generated files. Keeping the name `main` keeps the TinyURL targets alive.

The nightly job only reads `code` and never writes to it, so it can't conflict with a matching session.

## Nightly build

It runs on `ubuntu-latest` with Python 3.13 at 09:00 UTC, which is 3 AM MDT or 2 AM MST. There's also a manual "Run workflow" button with a `publish` on/off switch. The time limit is 90 minutes.

1. **Channel list.** Call the provider's `get_live_streams` API using the `XC_URL`, `XC_USERNAME` and `XC_PASSWORD` secrets, and keep the priority channels (the existing prefix list in `main.py`). If the call still fails after 3 tries, reuse last night's `channels.json` from `main` and flag the run as "channel list stale". On the first run, with no `channels.json` yet, use the names in `known_matches.json`.
2. **Match.** No AI. Decisions saved in sessions come first, then automatic rules. Each channel takes the first rule that applies:
   1. A `known_matches.json` entry whose guide ID exists in tonight's sources.
   2. The channel is in `no_guide.json`, so it's skipped.
   3. **Rename carry-over.** A matched channel disappeared tonight and a new channel appeared with the same *normalized* name. Normalizing keeps the same prefix and strips quality tags (HD, FHD, UHD, 4K, ᴴᴰ…) and punctuation. The new name inherits the guide ID, but only when that normalized name pairs exactly one vanished channel with exactly one new channel.
   4. The existing exact and fuzzy (score ≥ 93) name matching. One bug is fixed: for channels with prefixes like `SLING|`, `PLAY+|` or `SPORTS|`, the matcher used the prefix itself ("SLING") as the channel's name. Fuzzy matching moves from `fuzzywuzzy` to the faster `rapidfuzz`.
   5. Otherwise the channel is added to the queue. A channel whose saved guide ID vanished from tonight's sources is queued too, with the old ID as a hint.
3. **Sources.** Download the nine working sources fresh each run: the current list minus `epghub.xyz`. A failed download is logged and skipped. It isn't fatal by itself, because the checks in step 5 catch a guide that shrank.
4. **Build.** The output format is unchanged: one `<channel>` per provider channel name, with programmes copied from the matched source channel. Two cleanups:
   - Keep only programmes from 1 day ago to 8 days ahead. The March guide still held programmes from September 2025 and May 2026.
   - When sources overlap, keep one programme per guide channel per start time; the first source wins. About 25% of the March guide's programmes were duplicates.

   A downloaded file that isn't gzip, such as an error page, never replaces a good copy. A source that turns out corrupt partway through is skipped without stopping the build.
5. **Checks before publishing.** If any check fails, the run fails, nothing is published, yesterday's guide stays up, and GitHub emails you.
   - At least 80% of last night's channel count (on the first run, at least 1,000 channels).
   - At least half the guide's channels have a programme in the next 24 hours. This threshold gets tuned after the dry run.
   - The compressed file is under 95 MB (GitHub's hard limit is 100 MB). If it's over, drop programmes starting more than 5 days out and check once more.
6. **Publish.** Build a fresh single-commit `main` containing:
   - `epg.xml.gz` and `data/epg_repair.xml.gz`. They're the identical file, so git stores it once.
   - `match_queue.json`: each queued channel with up to 10 candidates (guide ID, display name, source), plus the provider's own EPG ID when it's a real guide ID.
   - `guide_index.json.gz`: every guide ID with its display names, used for searching during sessions.
   - `channels.json`: tonight's priority channel names, used as the fallback in step 1.
   - `status.json`, plus a short `README.md` explaining what the branch is.

   Then force-push `main`. The run summary shows channels, matched, carried over, queued, added and removed since last night, and any source failures.

**Rejected logins.** The provider answers a rejected login with HTTP 513 and an empty body. This happened on 2026-09-26 because the saved login was out of date. The nightly job reports this case by name, "provider rejected the login — run `tools/set_login.py`", rather than as a generic failure. A rejected login still publishes a guide from last night's channel list, then marks the run as failed so GitHub emails you. A network failure only flags the run as "channel list stale", because that usually fixes itself.

**Changing the login.** `tools/set_login.py` asks you for the server URL, username and password, confirms the provider accepts them, then writes them to `.env` and to the GitHub secrets. Claude never enters the password itself.

**Keeping the login private:**
- The provider login lives only in GitHub secrets and your local `.env`.
- The code never prints the API URL, and network errors are logged with the query string stripped. GitHub also masks secret values in logs.
- Nothing containing the provider's address is committed. The raw playlist cache stops being committed.

## Provider renamed its channels (found 2026-09-26)

Some time after March, the provider switched from `US| CNN HD` to `US: CNN HD` and regrouped its channels. None of the 7,378 saved names still exist.

- **The main groups now:** `US`, `UK`, `NOW`, `CA`, `CA EN`, `CA FR`, `PRIME`, `PLAY+`, `AT&T`, `TV`, `4K`, `ENGLISH`, `SPORTS`. That's 8,886 channels. The old `|` prefixes stay recognised so saved matches can be carried over.
- **Old groups mapped to new ones** (found by comparing channel names): SLING→AT&T, GO→TV, UK-NOWTV→NOW, UK-BBCI→UK, NHL TEAM→US, CA→CA / CA EN / CA FR. The rest kept their names.
- **Rename carry-over, changed:** a new name inherits a saved match when it equals a vanished saved name once quality tags, punctuation and the group mapping above are ignored, and when all of those vanished names agree on one guide ID. *Every* quality copy of a channel ("US: CNN HD", "US: CNN 4K") inherits the match; they're the same channel.
- **First build under the new names:** 3,420 carried, 394 automatic, 5,072 queued. Coverage 42.9%, fresh 91.6%. The old matches carry over nightly, and each session's `apply` saves them under the new names.

## Accuracy fixes (after the first audit, 2026-09-26)

An independent audit of random samples found:
- **Carried-over old matches: about 60% correct.** The Gemini-era saves were often wrong-country feeds.
- **Automatic matches: about 52% correct.** They matched on generic words like "PPV" and "WEST", used +1 timeshift feeds, and took other countries' feeds for bare brand names.

These changes followed:

- **Trust order:**
  1. Session decisions (`known_matches.json`) and matches confirmed in audits
  2. `no_guide`
  3. Automatic no-guide (PPV / EVENT / REPLAY / LOOP / 24/7 names)
  4. Legacy matches (`legacy_matches.json`), exact or carried over, only if they pass `flag_reasons`
  5. Strict automatic matching
  6. The queue
- **Strict automatic matching:**
  - an exact name within the channel's country, or a plain-ratio (no partial matching) score of at least 93
  - never a +1 feed for a non-timeshift channel
  - never a generic word as the whole name
  - never a match that fails `flag_reasons`
  - "(WEST)" and "(EAST)" are feed words, not call signs
- **Group regions:** `TV:` (formerly GO) has no single country.
- **Carry-over:** `+` is kept, so AMC+ is not AMC. Decorations such as ᴿᴬᵂ and ◉ are removed properly.
- **Coverage** is measured against channels that can have a guide: settled no-guide channels are left out.
- **First build after the fixes:** 3,220 channels in the guide, 1,183 auto no-guide, 4,483 queued. Coverage 41.8%, fresh 93.3%, 0 flagged.

## Scorecard (requested 2026-09-26)

Every nightly run scores the guide. The scores go in `status.json`, the run summary and `score_history.json` on `main`. The history is carried forward from last night's copy, keeping 365 days.

| Score | Meaning |
|---|---|
| **Coverage** | Channels with a guide ÷ all priority channels in tonight's list |
| **Fresh** | Guide channels with a programme in the next 24 hours ÷ guide channels |
| **Accuracy** | Share of *randomly sampled* audited matches judged correct, over the most recent 200 random audits (see sessions). Flagged matches are audited so they get fixed, but they don't count toward Accuracy, since that would skew it. Shows "not audited yet" until the first audit. |
| **Flags** | Matches that fail a free automatic check, reported as a count with examples |
| **Headline** | Coverage × Fresh × Accuracy: an estimate of the share of channels with a correct, current guide. Before any audit it uses accuracy 1.0 and is labelled "unaudited". |

The automatic checks that raise a flag, with no AI involved:
- **Region:** a `US|`, `SLING|`, `CA|` or `UK|` channel is matched to a guide ID whose suffix is a different two-letter country code, such as `.co` or `.in`. Numbered and underscored variants like `.ca2` and `.us_locals1` count as that country. Platform suffixes such as `.plex` or `.com` aren't countries and are never flagged.
- **Call sign:** the channel name contains a call sign in parentheses, such as "(WABC)", and the guide ID doesn't.
- **Network:** the channel name says ABC, CBS, NBC, FOX, CW or PBS, and the guide ID names a different one of those networks but not the one in the name.

`matches.json` on `main` lists tonight's match for every channel: the guide ID and how it was matched (saved, renamed or automatic). Audits sample from this file.

## Matching sessions (Claude, on demand)

You start a Claude Code session in the working copy and say "match the queue". `CLAUDE.md` on `code` spells out the routine:

1. Pull `code`, and fetch `main` for tonight's queue.
2. `python src/match_session.py show` prints the next batch of 50 channels with their candidates. `python src/match_session.py search "<text>"` searches the full guide index.
3. Claude writes a decision for each channel in the batch: a guide ID, `NO_GUIDE`, or `SKIP` (unsure, stays queued).
4. `python src/match_session.py apply decisions.json` rejects any guide ID that isn't in tonight's index, then updates `known_matches.json` and `no_guide.json`.
5. Commit and push `code` after each batch, so progress survives if the session ends. The next nightly run picks up the new matches.

If tonight's `status.json` shows a source failed, Claude leaves that source's "guide ID vanished" entries alone, since they'll clear once the source is back.

**Audit (every session, before matching):**
1. `python src/match_session.py audit` prints 25 of tonight's matches. Flagged matches come first, then a random sample, and each shows the guide channel's display names.
2. Claude writes a verdict for each one: `correct`, `wrong`, `NO_GUIDE`, or the correct guide ID.
3. `python src/match_session.py audit-apply verdicts.json` records each verdict in `data/audit_log.json` (name, guide ID, random or flagged, verdict, date), which is where Accuracy comes from. Anything other than `correct` also changes the match:
   - **A guide ID:** that ID replaces the old match.
   - **`NO_GUIDE`:** the channel moves to `no_guide.json`.
   - **`wrong`:** the pair goes into `data/rejected_matches.json` and the saved match is removed, so the channel returns to the queue. The automatic rules (rename carry-over and exact/fuzzy matching) never pick a rejected pair again.

**First session (the ~2,400 backlog).** Two things happen before any one-by-one matching:
- The 3,479 March suggestions (`suggested_matches.json`, uncommitted in the PC copy) are checked against the guide index. The ones pointing at real IDs are shown for a quick bulk review rather than accepted blindly.
- Channels whose names mark them as pay-per-view, event, replay or 24/7 loop feeds are pre-marked `NO_GUIDE`. This uses whole-word patterns, and the list is shown for a sanity check.

## Cleanup (on `code`)

- **Remove Gemini.**
  - Delete `src/ai_client.py`, `src/analyze.py`, `src/audit_matches.py`, `src/hunt_missing.py`, `src/recycle_missing.py` and `check_models.py`.
  - Drop `google-genai` from `requirements.txt`.
  - Remove the `GEMINI_*` and `OFFLINE_MODE` settings from the code and `.env.example`.
- **Remove retired scripts and junk.**
  - Scripts: `run_epg_bridge.sh`, `run_epg_bridge.bat`, `setup_cron.sh`, `check_epg_status.sh`, `src/update_all.bat`, `src/update_all.sh`, `src/weekly_maintenance.bat`, `src/push_to_github.py`, `src/deploy_epg.py`.
  - Unused code: `src/clean_log.py`, `src/filter_missing.py`, `src/channel_database.py`.
  - Junk: `files.zip`, `src/New Text Document.txt`, `audit_report.md`, `src/data/`.
- **Stop tracking generated files.** From now on they exist only on `main`, or nowhere. Update `.gitignore` to match.
  - `epg.xml.gz`, `src/epg.xml.gz`, `data/epg_repair.xml`, `data/epg_repair.xml.gz`
  - `data/playlist_cache.json`, `logs/*`
  - `suggested_matches.json`, once the first session has used it
- **`main.py` becomes non-interactive.**
  - No VPN prompts. It takes its options from command-line flags, so the same code runs in GitHub Actions and on the PC.
  - Progress bars (`tqdm`) are dropped; each step prints its counts instead.
  - `main.py` is split into small modules: `provider.py`, `matching.py`, `guide.py`, `checks.py`, `publish.py`, plus the existing `epg_cache.py`.
- Rewrite `README.md`, and add `CLAUDE.md` and `.github/workflows/nightly.yml`.
- **Local:** the PC copy switches to `code`, and `GEMINI_API_KEY` is removed from its `.env`.

## One-time rollout

Steps marked **you** need you. Steps marked **confirm** change GitHub, and I'll ask before each one.

1. Create `code` from the current `origin/main` in the PC copy. Make the code and cleanup changes, get the tests passing, and do a full local test build.
2. **You:** run `tools/set_login.py` and paste the current login. It sets the `XC_URL`, `XC_USERNAME` and `XC_PASSWORD` secrets and updates `.env`.
3. Push `code`. Pushing code changes to `code` triggers a test run automatically, since GitHub only allows a manual "Run workflow" once the workflow is on the default branch. The test run doesn't publish. It proves GitHub can reach the provider and the sources. Review the run summary and the built guide, which is uploaded as a run artifact.
4. **Confirm (one yes for both):** make `code` the repo's default branch, then do a manual run with `publish` on. This replaces `main`. Its old history stays reachable from `code`, so nothing is lost.
5. Check that `bdzutmzd` and `5xkmff7s` serve a fresh file with today's programmes, that the schedule is active, and that GitHub's Actions failure emails are on. **You:** glance at TiviMate.
6. **You:** remove the NAS cron line: edit `/etc/config/crontab`, delete the `run_epg_bridge.sh` line, then run `crontab /etc/config/crontab`. Then archive the NAS folder.
7. **You (recommended):** delete the Gemini API key in Google AI Studio.

## Testing

- **Unit tests** (pytest, small fixtures) cover:
  - name normalization and rename carry-over, including ambiguous cases that must *not* carry over
  - queue building (known, no-guide, vanished ID)
  - the publish checks (count drop, coverage, size and trimming)
  - `apply` validation
  - the error-message sanitizer: credentials never appear in error text
- **Local dry run** on the PC with `publish` off: compare channel and programme counts with the March 25 guide.
- **GitHub dry run, then live run**, as in rollout steps 4–6.

## Risks

| Risk | Mitigation |
|---|---|
| The provider can't be reached from GitHub (you used to need a VPN at home; on 2026-09-26 the PC reached it without one) | Rollout step 4 finds out. Fallback: refresh `channels.json` during Claude sessions on the PC, and the nightly builds use it. |
| The login changes again | The nightly run fails with "provider rejected the login". Run `tools/set_login.py`. |
| The provider objects to logins from new IP addresses | It's one small API call per night, on a spare account. |
| A guide source blocks GitHub's servers | Rollout step 4 finds out. `main.py` stays runnable on the PC, so the nightly job could move to Windows Task Scheduler. |
| The guide outgrows GitHub's 100 MB file limit | Trim to 5 days ahead, and fail loudly if it's still too big. |
| GitHub disables schedules after 60 days without repo activity | The nightly push to `main` should count as activity. Verify after the first week, and add a keep-alive step if it doesn't. |
| Failure emails go to the wrong place | Commit the workflow under an email linked to your GitHub account, and check notification settings (rollout step 3). |
| A fuzzy auto-match picks the wrong channel | Same as today. An explicit match saved in a session always wins. |
