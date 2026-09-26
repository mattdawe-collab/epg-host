import gzip
import json
import random

import match_session as ms


def test_apply_decisions():
    known = {"US| OLD": "Old.us"}
    no_guide = {"US| X": "2026-01-01"}
    decisions = {"US| CNN": "CNN.us", "US| PPV 1": "NO_GUIDE", "US| MAYBE": "SKIP", "US| BAD": "NotReal.us",
                 "US| X": "ESPN.us"}
    carried = {"US| NEW NAME": {"from": "US| OLD NAME", "id": "ESPN.us"}}
    applied, rejected = ms.apply_decisions(decisions, {"CNN.us", "ESPN.us"}, known, no_guide, carried, "2026-09-26")
    assert known == {"US| OLD": "Old.us", "US| NEW NAME": "ESPN.us", "US| CNN": "CNN.us", "US| X": "ESPN.us"}
    assert no_guide == {"US| PPV 1": "2026-09-26"}
    assert rejected == {"US| BAD": "NotReal.us"}
    assert applied == {"matched": 2, "no_guide": 1, "carried": 1, "skipped": 1}


def test_pending_hides_decided_channels():
    queue_doc = {"queue": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
    assert [e["name"] for e in ms.pending(queue_doc, {"A": "x"}, {"B": "d"})] == ["C"]


def test_prepass_draft():
    queue_doc = {"queue": [{"name": "US| CNN"}, {"name": "SPORTS| PPV EVENT 3"}, {"name": "US| NBC"},
                           {"name": "US| REPLAY CHANNEL"}]}
    suggestions = {"US| CNN": "CNN.us", "US| NBC": "Invented.us", "US| NOT QUEUED": "ESPN.us"}
    assert ms.build_prepass(queue_doc, suggestions, {"CNN.us", "ESPN.us"}) == {
        "US| CNN": "CNN.us", "SPORTS| PPV EVENT 3": "NO_GUIDE", "US| REPLAY CHANNEL": "NO_GUIDE"}


def test_no_guide_pattern_uses_whole_words():
    for name in ("US| PPV 1", "SPORTS| EVENT 12", "US| 24/7 SIMPSONS", "US| NFL REPLAY", "SPORTS| EVENTS 3"):
        assert ms.NO_GUIDE_PATTERN.search(name), name
    for name in ("US| PREVENT TV", "US| DIRECTV", "US| FLOOP"):
        assert not ms.NO_GUIDE_PATTERN.search(name), name


def test_load_published_from_folder(tmp_path):
    (tmp_path / "match_queue.json").write_text(json.dumps({"queue": [{"name": "A"}]}), encoding="utf-8")
    with gzip.open(tmp_path / "guide_index.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"CNN.us": ["CNN"]}, f)
    assert ms.load_published("match_queue.json", str(tmp_path)) == {"queue": [{"name": "A"}]}
    assert ms.load_published("guide_index.json.gz", str(tmp_path)) == {"CNN.us": ["CNN"]}


def test_audit_sample_mixes_flagged_and_random():
    matches = {f"US| CH{i}": {"id": f"C{i}.us", "how": "saved", "flags": []} for i in range(40)}
    matches.update({f"US| BAD{i}": {"id": f"B{i}.uk", "how": "auto", "flags": ["region"]} for i in range(20)})
    sample = ms.pick_audit_sample(matches, [], size=10, rng=random.Random(1))
    kinds = [v["sample"] for v in sample.values()]
    assert len(sample) == 10 and kinds.count("flagged") == 5 and kinds.count("random") == 5
    assert all(not v["flags"] for v in sample.values() if v["sample"] == "random")


def test_audit_skips_flagged_matches_already_confirmed():
    matches = {"US| A": {"id": "A.uk", "how": "saved", "flags": ["region"]}}
    log = [{"name": "US| A", "id": "A.uk", "verdict": "correct", "sample": "flagged"}]
    assert ms.pick_audit_sample(matches, log, size=2, rng=random.Random(1)) == {}


def test_apply_verdicts():
    sample = {
        "US| A": {"id": "A.us", "how": "saved", "flags": [], "sample": "random"},
        "US| B": {"id": "B.uk", "how": "auto", "flags": ["region"], "sample": "flagged"},
        "US| C": {"id": "C.us", "how": "saved", "flags": [], "sample": "random"},
        "US| D": {"id": "D.us", "how": "renamed", "flags": [], "sample": "random"},
        "US| E": {"id": "E.us", "how": "saved", "flags": [], "sample": "random"},
    }
    known = {"US| A": "A.us", "US| C": "C.us", "US| E": "E.us"}
    no_guide, rejected, log = {}, {}, []
    verdicts = {"US| A": "correct", "US| B": "B.us", "US| C": "wrong", "US| D": "NO_GUIDE", "US| E": "Fake.us",
                "US| Z": "correct"}
    counts, problems = ms.apply_verdicts(verdicts, sample, {"A.us", "B.us", "C.us", "D.us", "E.us"},
                                         known, no_guide, rejected, log, "2026-09-26")
    assert known == {"US| A": "A.us", "US| E": "E.us", "US| B": "B.us"}
    assert no_guide == {"US| D": "2026-09-26"}
    assert rejected == {"US| B": ["B.uk"], "US| C": ["C.us"], "US| D": ["D.us"]}
    assert [(e["name"], e["verdict"], e["sample"]) for e in log] == [
        ("US| A", "correct", "random"), ("US| B", "wrong", "flagged"), ("US| C", "wrong", "random"),
        ("US| D", "wrong", "random")]
    assert counts == {"correct": 1, "fixed": 1, "no_guide": 1, "wrong": 1}
    assert problems == {"US| E": "Fake.us is not a real guide ID", "US| Z": "not in the current audit sample"}


def test_apply_command_end_to_end(tmp_path, monkeypatch):
    published = tmp_path / "publish"
    published.mkdir()
    (published / "match_queue.json").write_text(json.dumps({"queue": [], "carried": {}}), encoding="utf-8")
    with gzip.open(published / "guide_index.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"CNN.us": ["CNN"]}, f)
    monkeypatch.setattr(ms, "KNOWN_FILE", str(tmp_path / "known.json"))
    monkeypatch.setattr(ms, "NO_GUIDE_FILE", str(tmp_path / "no_guide.json"))
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({"US| CNN": "CNN.us"}), encoding="utf-8")
    assert ms.main(["--source", str(published), "apply", str(decisions)]) == 0
    assert json.loads((tmp_path / "known.json").read_text(encoding="utf-8")) == {"US| CNN": "CNN.us"}
