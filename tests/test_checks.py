import checks
from guide import GuideStats


def stats(channels=2000, upcoming=1800):
    return GuideStats(channels=channels, programmes=100_000, channels_with_upcoming=upcoming,
                      skipped_duplicates=0, skipped_out_of_window=0)


def test_healthy_guide_passes():
    assert checks.find_problems(stats(), 40 * 2**20, {"channels": 2100}) == []


def test_empty_guide_fails():
    assert any("no channels" in p for p in checks.find_problems(stats(0, 0), 1000, None))


def test_big_drop_from_last_night_fails():
    assert any("down from 2,000" in p for p in checks.find_problems(stats(1500, 1400), 1000, {"channels": 2000}))


def test_first_run_needs_minimum_channels():
    assert checks.find_problems(stats(999, 999), 1000, None)
    assert checks.find_problems(stats(1000, 900), 1000, None) == []


def test_few_upcoming_programmes_fails():
    assert any("next 24 hours" in p for p in checks.find_problems(stats(2000, 900), 1000, None))


def test_oversized_guide_fails():
    assert any("MB" in p for p in checks.find_problems(stats(), 96 * 2**20, None))
