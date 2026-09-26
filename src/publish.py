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
