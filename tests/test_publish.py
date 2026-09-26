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
