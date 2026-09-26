"""Nightly scorecard: coverage, freshness, audited accuracy and free automatic flags. No AI."""
from matching import flag_reasons

AUDIT_WINDOW = 200
HISTORY_DAYS = 365

__all__ = ["flag_reasons", "audited_accuracy", "scorecard", "update_history"]


def audited_accuracy(audit_log):
    recent = [e for e in audit_log if e.get("sample") == "random"][-AUDIT_WINDOW:]
    if not recent:
        return None, 0
    return sum(e["verdict"] == "correct" for e in recent) / len(recent), len(recent)


def scorecard(total_channels, matches, stats, audit_log, settled_no_guide=0):
    """Coverage counts only channels that can have a guide: channels settled as 'no guide' are left out."""
    flags = {}
    for name, xml_id in matches.items():
        reasons = flag_reasons(name, xml_id)
        if reasons:
            flags[name] = reasons
    guideable = total_channels - settled_no_guide
    coverage = len(matches) / guideable if guideable > 0 else 0.0
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
