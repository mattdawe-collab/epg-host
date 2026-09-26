import score
from guide import GuideStats


def test_region_flag():
    assert "region" in score.flag_reasons("US| CNN", "CNN.uk")
    assert score.flag_reasons("US| CNN", "CNN.us") == []
    assert score.flag_reasons("US| ABC 7 (WABC)", "WABC.us_locals1") == []
    assert score.flag_reasons("CA| CBC TORONTO", "CBLT.ca") == []
    assert score.flag_reasons("SPORTS| NBA 1", "NBA.uk") == []


def test_platform_guide_ids_are_not_a_region_problem():
    assert score.flag_reasons("US| REAL AMERICA'S VOICE", "RealAmericasVoice.plex") == []
    assert score.flag_reasons("UK| BBC ONE", "BBCOne.gb") == []
    assert "region" in score.flag_reasons("CA| A&E HD", "A&E.co")
    assert "region" in score.flag_reasons("US| NEWS", "News.ca2")


def test_callsign_flag():
    assert "callsign" in score.flag_reasons("US| ABC 7 (WABC)", "KABC.us")
    assert "callsign" not in score.flag_reasons("US| ABC 7 (WABC)", "ABC.(WABC).New.York,.NY.us")


def test_network_flag():
    assert "network" in score.flag_reasons("US| FOX 5 NEW YORK", "CBSNewYork.us")
    assert "network" not in score.flag_reasons("US| FOX 5 NEW YORK", "WNYW.us")
    assert "network" not in score.flag_reasons("US| MSNBC", "MSNBC.us")


def test_audited_accuracy_counts_random_samples_only():
    log = [{"sample": "random", "verdict": "correct"}] * 3 + [{"sample": "random", "verdict": "wrong"}] + \
          [{"sample": "flagged", "verdict": "wrong"}] * 5
    assert score.audited_accuracy(log) == (0.75, 4)
    assert score.audited_accuracy([]) == (None, 0)


def test_scorecard_numbers():
    stats = GuideStats(channels=3, programmes=10, channels_with_upcoming=3, skipped_duplicates=0, skipped_out_of_window=0)
    matches = {"US| A": "A.us", "US| B": "B.uk", "US| C": "C.us"}
    card = score.scorecard(4, matches, stats, [])
    assert card["coverage"] == 0.75 and card["fresh"] == 1.0
    assert card["accuracy"] is None and card["headline_basis"] == "unaudited"
    assert card["headline"] == 0.75
    assert card["flagged"] == 1 and card["flags"] == {"US| B": ["region"]}
    card = score.scorecard(4, matches, stats, [{"sample": "random", "verdict": "correct"},
                                               {"sample": "random", "verdict": "wrong"}])
    assert card["accuracy"] == 0.5 and card["headline"] == 0.375


def test_update_history_replaces_same_day_and_caps_length():
    card = {"coverage": 0.5, "fresh": 1.0, "accuracy": None, "flagged": 2, "headline": 0.5}
    history = [{"date": f"2025-01-{d:02d}"} for d in range(1, 31)] * 13
    updated = score.update_history(history + [{"date": "2026-09-26", "headline": 0.1}], "2026-09-26", card)
    assert len(updated) == score.HISTORY_DAYS
    assert updated[-1] == {"date": "2026-09-26", **card}
