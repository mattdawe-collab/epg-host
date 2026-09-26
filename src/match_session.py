"""Tools for Claude matching and audit sessions - see CLAUDE.md.

There are no AI API calls here: Claude reads the output and decides in-session.
"""
import argparse
import gzip
import json
import os
import random
import subprocess
import sys
from datetime import date

from matching import NO_GUIDE_PATTERN

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN_FILE = os.path.join(ROOT, "data", "known_matches.json")
NO_GUIDE_FILE = os.path.join(ROOT, "data", "no_guide.json")
REJECTED_FILE = os.path.join(ROOT, "data", "rejected_matches.json")
AUDIT_LOG_FILE = os.path.join(ROOT, "data", "audit_log.json")
AUDIT_SAMPLE_FILE = os.path.join(ROOT, "audit_sample.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def load_published(name, source):
    """Read a file the nightly job published, from a local folder or a git ref such as origin/main."""
    if os.path.isdir(source):
        with open(os.path.join(source, name), "rb") as f:
            raw = f.read()
    else:
        raw = subprocess.run(["git", "show", f"{source}:{name}"], cwd=ROOT, capture_output=True, check=True).stdout
    if name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def pending(queue_doc, known, no_guide):
    return [e for e in queue_doc.get("queue", []) if e["name"] not in known and e["name"] not in no_guide]


def apply_decisions(decisions, index_ids, known, no_guide, today, channel_names):
    applied = {"matched": 0, "no_guide": 0, "skipped": 0}
    problems = {}
    for name, decision in decisions.items():
        if name not in channel_names:
            problems[name] = "not a channel in tonight's list"
        elif decision == "SKIP":
            applied["skipped"] += 1
        elif decision == "NO_GUIDE":
            no_guide[name] = today
            known.pop(name, None)
            applied["no_guide"] += 1
        elif decision in index_ids:
            known[name] = decision
            no_guide.pop(name, None)
            applied["matched"] += 1
        else:
            problems[name] = f"{decision} is not a real guide ID"
    return applied, problems


def build_prepass(queue_doc, suggestions, index_ids):
    draft = {}
    for entry in queue_doc.get("queue", []):
        name = entry["name"]
        if NO_GUIDE_PATTERN.search(name):
            draft[name] = "NO_GUIDE"
        elif suggestions.get(name) in index_ids:
            draft[name] = suggestions[name]
    return draft


def pick_audit_sample(matches_doc, audit_log, size=25, rng=None):
    """Up to half flagged matches (not already confirmed); the rest a random sample of ALL other matches,
    so the random audits - which drive Accuracy - represent flagged and unflagged matches alike."""
    rng = rng or random.Random()
    confirmed = {(e["name"], e["id"]) for e in audit_log if e["verdict"] == "correct"}
    flagged = [(n, m) for n, m in sorted(matches_doc.items()) if m.get("flags") and (n, m["id"]) not in confirmed]
    flagged = flagged[: size // 2]
    chosen = {n for n, _ in flagged}
    others = [(n, m) for n, m in sorted(matches_doc.items()) if n not in chosen]
    randoms = rng.sample(others, min(size - len(flagged), len(others)))
    sample = {n: {"id": m["id"], "how": m["how"], "flags": m["flags"], "sample": "flagged"} for n, m in flagged}
    sample.update({n: {"id": m["id"], "how": m["how"], "flags": m.get("flags", []), "sample": "random"}
                   for n, m in randoms})
    return sample


def apply_verdicts(verdicts, sample, index_ids, known, no_guide, rejected, audit_log, today):
    counts = {"correct": 0, "fixed": 0, "no_guide": 0, "wrong": 0}
    problems = {}
    for name, verdict in verdicts.items():
        info = sample.get(name)
        if info is None:
            problems[name] = "not in the current audit sample"
            continue
        if verdict not in ("correct", "wrong", "NO_GUIDE") and verdict not in index_ids:
            problems[name] = f"{verdict} is not a real guide ID"
            continue
        audit_log.append({"date": today, "name": name, "id": info["id"], "how": info["how"],
                          "sample": info["sample"], "verdict": "correct" if verdict == "correct" else "wrong"})
        if verdict == "correct":
            known[name] = info["id"]  # a confirmed match becomes a trusted session decision
            counts["correct"] += 1
            continue
        refused = rejected.setdefault(name, [])
        if info["id"] not in refused:
            refused.append(info["id"])
        if verdict == "NO_GUIDE":
            known.pop(name, None)
            no_guide[name] = today
            counts["no_guide"] += 1
        elif verdict == "wrong":
            known.pop(name, None)
            counts["wrong"] += 1
        else:
            known[name] = verdict
            no_guide.pop(name, None)
            counts["fixed"] += 1
    return counts, problems


def refresh(source):
    if not os.path.isdir(source) and source.startswith("origin/"):
        subprocess.run(["git", "fetch", "-q", "origin", source.split("/", 1)[1]], cwd=ROOT, check=True)


def cmd_show(args):
    queue_doc = load_published("match_queue.json", args.source)
    todo = pending(queue_doc, load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {}))
    print(f"{len(todo):,} channels waiting (queue built {queue_doc.get('generated_at')})")
    failed = [k for k, v in queue_doc.get("sources", {}).items() if v == "failed"]
    if failed:
        print(f"Sources that failed that night: {', '.join(failed)} - leave their vanished_id entries alone")
    for entry in todo[args.offset:args.offset + args.batch]:
        extra = "".join(f" {k}={entry[k]}" for k in ("previous_id", "provider_id") if k in entry)
        print(f"\n## {entry['name']}  [{entry['reason']}{extra}]")
        for c in entry["candidates"]:
            print(f"   {c['id']}  --  {c['name']}")


def cmd_search(args):
    index = load_published("guide_index.json.gz", args.source)
    needle = args.text.lower()
    hits = [(i, n) for i, n in index.items() if needle in i.lower() or any(needle in x.lower() for x in n)]
    for i, n in hits[:args.limit]:
        print(f"{i}  --  {' | '.join(n[:4])}")
    print(f"({len(hits):,} matches)")


def cmd_apply(args):
    index_ids = set(load_published("guide_index.json.gz", args.source))
    queue_doc = load_published("match_queue.json", args.source)
    channel_names = set(load_published("channels.json", args.source)) | {e["name"] for e in queue_doc.get("queue", [])}
    known, no_guide = load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {})
    applied, problems = apply_decisions(load_json(args.decisions, {}), index_ids, known, no_guide,
                                        date.today().isoformat(), channel_names)
    save_json(KNOWN_FILE, known)
    save_json(NO_GUIDE_FILE, no_guide)
    print("Applied:", applied)
    for name, problem in problems.items():
        print(f"REJECTED: {name}: {problem}")
    return 1 if problems else 0


def cmd_prepass(args):
    queue_doc = load_published("match_queue.json", args.source)
    index_ids = set(load_published("guide_index.json.gz", args.source))
    draft = build_prepass(queue_doc, load_json(args.suggestions, {}), index_ids)
    save_json(args.out, draft)
    no_guide = sum(1 for v in draft.values() if v == "NO_GUIDE")
    print(f"Draft written to {args.out}: {len(draft) - no_guide:,} suggested matches, {no_guide:,} NO_GUIDE "
          f"by name. Review it, then run apply on it.")


def cmd_audit(args):
    matches_doc = load_published("matches.json", args.source)
    index = load_published("guide_index.json.gz", args.source)
    sample = pick_audit_sample(matches_doc, load_json(AUDIT_LOG_FILE, []), args.size)
    save_json(AUDIT_SAMPLE_FILE, sample)
    print(f"Audit sample of {len(sample)} saved to {AUDIT_SAMPLE_FILE}. Verdicts: correct | wrong | NO_GUIDE | <right ID>")
    for name, info in sample.items():
        flags = f" FLAGS={','.join(info['flags'])}" if info["flags"] else ""
        display = index.get(info["id"]) or ["(not in tonight's sources)"]
        print(f"\n## {name}  [{info['sample']}, {info['how']}{flags}]")
        print(f"   {info['id']}  --  {' | '.join(display[:4])}")


def cmd_audit_apply(args):
    sample = load_json(AUDIT_SAMPLE_FILE, {})
    index_ids = set(load_published("guide_index.json.gz", args.source))
    known, no_guide = load_json(KNOWN_FILE, {}), load_json(NO_GUIDE_FILE, {})
    rejected, audit_log = load_json(REJECTED_FILE, {}), load_json(AUDIT_LOG_FILE, [])
    counts, problems = apply_verdicts(load_json(args.verdicts, {}), sample, index_ids, known, no_guide, rejected,
                                      audit_log, date.today().isoformat())
    for path, data in ((KNOWN_FILE, known), (NO_GUIDE_FILE, no_guide), (REJECTED_FILE, rejected),
                       (AUDIT_LOG_FILE, audit_log)):
        save_json(path, data)
    print("Recorded:", counts)
    for name, problem in problems.items():
        print(f"NOT RECORDED: {name}: {problem}")
    if not problems:
        os.remove(AUDIT_SAMPLE_FILE)
    return 1 if problems else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="origin/main", help="git ref or local publish folder to read from")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("show", help="next channels waiting to be matched")
    s.add_argument("--batch", type=int, default=50)
    s.add_argument("--offset", type=int, default=0)
    s.set_defaults(func=cmd_show)
    s = sub.add_parser("search", help="search every guide channel")
    s.add_argument("text")
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(func=cmd_search)
    s = sub.add_parser("apply", help="save match decisions")
    s.add_argument("decisions")
    s.set_defaults(func=cmd_apply)
    s = sub.add_parser("prepass", help="first session: draft decisions from March suggestions and name patterns")
    s.add_argument("--suggestions", default=os.path.join(ROOT, "suggested_matches.json"))
    s.add_argument("--out", default=os.path.join(ROOT, "decisions_prepass.json"))
    s.set_defaults(func=cmd_prepass)
    s = sub.add_parser("audit", help="sample tonight's matches for checking")
    s.add_argument("--size", type=int, default=25)
    s.set_defaults(func=cmd_audit)
    s = sub.add_parser("audit-apply", help="record audit verdicts and fix wrong matches")
    s.add_argument("verdicts")
    s.set_defaults(func=cmd_audit_apply)
    args = p.parse_args(argv)
    refresh(args.source)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
