# AI EPG Bridge v2.0

**Comprehensive IPTV to EPG Matching System**

This system automatically matches your IPTV channels to EPG (Electronic Program Guide) data from multiple sources, creating a merged EPG file that works with your IPTV setup.

## Features

- **Multi-Strategy Matching**: Uses a combination of:
  - Pre-built channel database (1000+ known channels)
  - Callsign extraction and direct matching
  - Network-aware fuzzy matching
  - AI-assisted matching (Gemini 3 Flash) for difficult cases

- **Self-Auditing**: Automatically detects and warns about:
  - Network mismatches (ABC channel → CBS station)
  - Region mismatches (Canadian channel → US ID)
  - Subchannel issues (main channel → subchannel ID)

- **Smart Caching**: EPG sources are cached locally and only refreshed when needed

- **Multiple EPG Sources**: Combines data from:
  - epgshare01.online (US/International)
  - epghub.xyz (Canada)
  - globetvapp EPG (USA/Canada)

## Installation

1. Clone or download this repository
2. Install Python 3.8 or higher
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your settings

## Configuration

Edit `.env` with your settings:

```env
# Gemini AI API key (get from https://makersuite.google.com/app/apikey)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

# Your IPTV provider's Xtream Codes credentials
XC_URL=http://your.provider.com
XC_USERNAME=your_username
XC_PASSWORD=your_password

# Output path for generated EPG
OUTPUT_PATH=./data/epg_output.xml
```

## Usage

Run the main script:

```bash
cd src
python main.py
```

### Modes

1. **Normal mode**: Uses cached EPG, database + fuzzy matching (fast)
2. **Force EPG refresh**: Re-downloads all EPG sources
3. **Full AI mode**: Uses AI for all unmatched channels (slower, costs API tokens)
4. **Audit mode**: Check existing matches for issues

## Output Files

- `data/epg_output.xml.gz` - The generated EPG file (gzipped)
- `data/known_matches.json` - Database of confirmed matches
- `logs/missing_channels.txt` - Channels that couldn't be matched
- `logs/audit_warnings.txt` - Potential issues with matches

## Channel Database

The system includes a comprehensive database of:

### US Channels
- All major network feeds (ABC/NBC/CBS/FOX East/West)
- Cable channels (ESPN, CNN, TNT, etc.)
- Premium channels (HBO, Showtime, etc.)

### Canadian Channels  
- CBC, CTV, Global network feeds and regionals
- Specialty channels (TSN, Sportsnet, etc.)
- French channels (TVA, Radio-Canada, RDS, etc.)

### UK Channels
- BBC, ITV, Channel 4, Channel 5
- Sky channels
- UKTV channels

## Troubleshooting

### Low Match Rate

1. Run in "Full AI mode" to use AI for unmatched channels
2. Check `logs/missing_channels.txt` for what's not matching
3. Add custom mappings to `suggested_matches.json`

### Network Mismatches

The audit system will catch most issues. Check `logs/audit_warnings.txt` after each run.

### EPG Not Loading

1. Make sure your IPTV player supports XMLTV format
2. Try the uncompressed version if .gz doesn't work
3. Verify the file path in your player settings

## Adding Custom Channels

Edit `src/channel_database.py` to add new channel mappings:

```python
CANADIAN_CHANNELS = {
    "NEW CHANNEL NAME": "xmlid.from.epg.source.ca",
    ...
}
```

## License

MIT License - Feel free to use and modify.

## Support

For issues or feature requests, open an issue on GitHub.
