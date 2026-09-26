"""Nightly scorecard: coverage, freshness, audited accuracy and free automatic flags. No AI."""
import re

from matching import region_of

NETWORKS = ("ABC", "CBS", "NBC", "FOX", "CW", "PBS")
CALLSIGN = re.compile(r"\(([A-Z]{4,5})\)")
HOME_COUNTRIES = {"US": {"us"}, "CA": {"ca"}, "UK": {"uk", "gb"}}
COUNTRY_SUFFIX = re.compile(r"^([a-z]{2})(?:\d+|_.*)?$")  # ".us", ".ca2", ".us_locals1"; ".plex"/".com" are not countries
AUDIT_WINDOW = 200
HISTORY_DAYS = 365


def flag_reasons(name, xml_id):
    reasons = []
    region = region_of(name)
    country = COUNTRY_SUFFIX.match(xml_id.rsplit(".", 1)[-1].lower()) if "." in xml_id else None
    if region in HOME_COUNTRIES and country and country.group(1) not in HOME_COUNTRIES[region]:
        reasons.append("region")
    callsign = CALLSIGN.search(name)
    if callsign and callsign.group(1) not in xml_id.upper():
        reasons.append("callsign")
    in_name = {n for n in NETWORKS if re.search(rf"\b{n}\b", name.upper())}
    in_id = {n for n in NETWORKS if n in xml_id.upper()}
    if in_name and in_id and not (in_name & in_id):
        reasons.append("network")
    return reasons


def audited_accuracy(audit_log):
    recent = [e for e in audit_log if e.get("sample") == "random"][-AUDIT_WINDOW:]
    if not recent:
        return None, 0
    return sum(e["verdict"] == "correct" for e in recent) / len(recent), len(recent)


def scorecard(total_channels, matches, stats, audit_log):
    flags = {}
    for name, xml_id in matches.items():
        reasons = flag_reasons(name, xml_id)
        if reasons:
            flags[name] = reasons
    coverage = len(matches) / total_channels if total_channels else 0.0
    fresh = stats.channels_with_upcoming / stats.channels if stats.channels else 0.0
    accuracy, audited = audited_accuracy(audit_log)
    headline = coverage * fresh * (1.0 if accuracy is None else accuracy)
    return {
        "coverage": round(coverage, 4),
        "fresh": round(fresh, 4),
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "audited": audited,
        "headline": round(headline, 4),
        "headline_basis": "unaudited" if accuracy is None else f"{audited} random audits",
        "flagged": len(flags),
        "flags": flags,
    }


def update_history(history, day, card):
    entry = {"date": day, **{k: card[k] for k in ("coverage", "fresh", "accuracy", "flagged", "headline")}}
    kept = [h for h in history or [] if h.get("date") != day]
    return (kept + [entry])[-HISTORY_DAYS:]
