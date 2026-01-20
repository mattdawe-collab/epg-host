import gzip
import shutil
import os

# 1. Configuration
# We are currently in Y:\AI_EPG_Bridge\src, so we go up one level
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(BASE_DIR, "data", "epg_repair.xml.gz")
DEST_FILE = os.path.join(BASE_DIR, "epg.xml")

print(f"Source: {SOURCE_FILE}")
print(f"Target: {DEST_FILE}")

# 2. Verify source exists
if not os.path.exists(SOURCE_FILE):
    print("Error: Source file not found! Run the build script first.")
    exit(1)

# 3. Unzip and Overwrite
print("Unzipping and moving file...")
try:
    with gzip.open(SOURCE_FILE, 'rb') as f_in:
        with open(DEST_FILE, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print("Success! epg.xml has been updated in the project root.")
except Exception as e:
    print(f"Error: {e}")