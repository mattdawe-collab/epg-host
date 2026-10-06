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
- **Channels renamed or added?** Run `venv\Scripts\python tools\import_playlist.py`. The provider blocks scripts, so it opens your channel list in Chrome; press Ctrl+S and Save. It keeps only channel names, guide IDs and groups (never stream links, which contain your login), saves them to `data/channels_import.json`, pushes that and starts a rebuild.

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
- `data/channels_import.json`: the channel list from the last playlist import, used while the provider blocks scripts
- `data/no_guide.json`, `data/rejected_matches.json`, `data/audit_log.json`: session decisions
