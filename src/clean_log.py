import os

# --- CONFIGURATION ---
INPUT_FILE = r'data/logs/missing_channels.txt'  # Adjusted path based on your structure
OUTPUT_FILE = r'data/logs/priority_missing.txt'

# 1. THE JUNK FILTER
# If a channel contains ANY of these, we toss it out.
IGNORE_KEYWORDS = [
    "backup", "raw", "hevc", "vip", "feed", "event", "ppv", 
    "24/7", "loop", "uncut", "rec", "replay", "vod", 
    "pluto", "samsung", "rakuten", "plex", # FAST channels often have generic metadata
    "alternate", "alt", "game", "match", "live",
    "nba league pass", "nhl centre ice", "mlb extra innings",
    "nfl sunday ticket", "redzone", "4k", "uhd"
]

# 2. THE CATEGORIZER
# We will sort what remains into these buckets
CATEGORIES = {
    "US Locals": ["abc ", "cbs ", "fox ", "nbc ", "pbs ", "cw ", "my", "ktla", "wgn", "wpix"],
    "US Sports": ["espn", "fs1", "fs2", "golf", "tennis", "nfl", "nhl", "nba", "mlb", "beinsports"],
    "US Entertainment": ["hbo", "starz", "showtime", "cinemax", "amc", "tnt", "tbs", "usa", "fx", "discovery", "history", "tlc", "hgtv", "food"],
    "UK": ["uk|", "bbc", "itv", "sky", "bt sport"],
    "Canada": ["ca|", "ctv", "cbc", "global", "tsn", "sportsnet"],
    "International": [] # Catch-all for everything else
}

def clean_log():
    # Handle paths relative to where the script is run
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "logs", "missing_channels.txt")
    output_path = os.path.join(base_dir, "logs", "priority_missing.txt")

    if not os.path.exists(input_path):
        print(f"Error: Could not find {input_path}")
        return

    print(f"Reading: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)
    kept_channels = {key: [] for key in CATEGORIES}
    
    ignored_count = 0

    for line in lines:
        line = line.strip()
        if not line: continue
        
        lower_line = line.lower()

        # CHECK 1: IS IT JUNK?
        is_junk = False
        for keyword in IGNORE_KEYWORDS:
            if keyword in lower_line:
                is_junk = True
                break
        
        if is_junk:
            ignored_count += 1
            continue

        # CHECK 2: CATEGORIZE IT
        categorized = False
        # Check specific categories first
        for cat, keywords in CATEGORIES.items():
            if cat == "International": continue # Skip catch-all for now
            
            for keyword in keywords:
                if keyword in lower_line:
                    kept_channels[cat].append(line)
                    categorized = True
                    break
            if categorized: break
        
        # If not matched above, put in International/Other
        if not categorized:
            kept_channels["International"].append(line)

    # WRITE THE CLEAN FILE
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== CLEANED MISSING CHANNEL REPORT ===\n")
        f.write(f"Original Count: {total_lines}\n")
        f.write(f"Junk Removed:   {ignored_count}\n")
        f.write(f"Channels Left:  {total_lines - ignored_count}\n")
        f.write("======================================\n\n")

        for cat, channels in kept_channels.items():
            if channels:
                f.write(f"--- {cat} ({len(channels)}) ---\n")
                # Sort alphabetically for easier reading
                for channel in sorted(channels):
                    f.write(f"{channel}\n")
                f.write("\n")

    print(f"Success! Filtered log saved to: {output_path}")
    print(f"Removed {ignored_count} junk lines.")

if __name__ == "__main__":
    clean_log()