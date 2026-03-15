import gzip
import shutil
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(BASE_DIR, "data", "epg_repair.xml.gz")
DEST_FILE = os.path.join(BASE_DIR, "epg.xml")


def run():
    """Unzip epg_repair.xml.gz to epg.xml. Returns True on success."""
    if not os.path.exists(SOURCE_FILE):
        return False

    try:
        with gzip.open(SOURCE_FILE, 'rb') as f_in:
            with open(DEST_FILE, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import console_ui as ui
    ui.banner("DEPLOY EPG")
    if run():
        ui.success(f"epg.xml updated at {DEST_FILE}")
    else:
        ui.error("Deploy failed - source file not found or unzip error")
