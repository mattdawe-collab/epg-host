import re

# Files
INPUT_FILE = "logs/priority_missing.txt"
OUTPUT_FILE = "logs/high_priority_hunt.txt"

# Keywords for "Tier 1" channels (Movies + Traditional Networks)
TIER_1_KEYWORDS = [
    "HBO", "MAX", "CINEMAX", "SHOWTIME", "STARZ", "MGM", "AMC", "TCM", "FX",
    "PBS", "FOX", "ABC", "NBC", "CBS", "CW", "MYTV", "ION",
    "CBC", "CTV", "GLOBAL", "CITY", "TSN", "SPORTS", "ESPN"
]

def is_likely_movie(name):
    # Regex to find (19xx) or (20xx) - likely a VOD movie
    return bool(re.search(r'\((19|20)\d{2}\)', name))

def main():
    print(f"Reading {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: priority_missing.txt not found.")
        return

    # 1. Deduplicate while keeping order (sets lose order)
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    print(f"Total entries: {len(lines)}")
    print(f"Unique entries: {len(unique_lines)}")

    # 2. Filter and Sort
    tier_1 = []
    tier_2 = []
    ignored = 0

    for channel in unique_lines:
        # Skip Movies
        if is_likely_movie(channel):
            ignored += 1
            continue
        
        # Skip garbage (single characters, etc)
        if len(channel) < 2:
            ignored += 1
            continue

        # Check for Tier 1 Keywords
        upper_name = channel.upper()
        if any(keyword in upper_name for keyword in TIER_1_KEYWORDS):
            tier_1.append(channel)
        else:
            tier_2.append(channel)

    # 3. Save Result (Tier 1 first, then Tier 2)
    final_list = tier_1 + tier_2
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write("\n".join(final_list))

    print("-" * 30)
    print(f"Movies/Junk Ignored: {ignored}")
    print(f"Tier 1 Found (Priority): {len(tier_1)}")
    print(f"Tier 2 Found (Others): {len(tier_2)}")
    print(f"Total to Hunt: {len(final_list)}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("-" * 30)

if __name__ == "__main__":
    main()
