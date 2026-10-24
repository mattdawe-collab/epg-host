"""The backup guide: when a matched guide channel runs out of listings, its twin in a backup source fills in."""
import gzip
from datetime import datetime, timedelta, timezone

from lxml import etree

import backup
import guide
from fixtures_xmltv import make_source

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def bridge(primary_index, backup_names, country="us"):
    return backup.build_bridge(primary_index, [(country, backup_names)])


# --- which backup channel is the same channel ---------------------------------------------------

def test_cable_channels_bridge_by_name_ignoring_quality_and_tag():
    found = bridge({"ESPN.HD.us2": ["ESPN HD"], "CNN.us": ["CNN"]},
                   {"ESPN.us": ["US - ESPN"], "ESPN2.us": ["US - ESPN 2"], "CNN.us": ["US - CNN"]})
    assert found == {"ESPN.HD.us2": "ESPN.us", "CNN.us": "CNN.us"}


def test_numbers_feeds_and_plus_must_agree():
    found = bridge({"ESPN2.us2": ["ESPN 2"], "AMC.us2": ["AMC"], "AMC.Plus.us2": ["AMC+"],
                    "HBO.West.us2": ["HBO (Pacific)"], "HBO.us2": ["HBO East"]},
                   {"ESPN.us": ["US - ESPN"], "AMCPlus.us": ["US - AMC+"], "HBOW.us": ["US - HBO West"],
                    "HBO.us": ["US - HBO"]})
    assert found == {"AMC.Plus.us2": "AMCPlus.us", "HBO.West.us2": "HBOW.us", "HBO.us2": "HBO.us"}


def test_filler_words_do_not_block_a_match():
    found = bridge({"AE.us2": ["A&E"], "Discovery.us2": ["Discovery Channel"]},
                   {"AandENetwork.us": ["US - A&E Network"], "Discovery.us": ["US - Discovery"]})
    assert found == {"AE.us2": "AandENetwork.us", "Discovery.us2": "Discovery.us"}


def test_country_must_match_and_other_tags_are_ignored():
    found = backup.build_bridge(
        {"CNN.us": ["CNN"], "Bloomberg.HD.uk": ["Bloomberg HD"], "HallmarkMovies.us2": ["Hallmark Movies"]},
        [("us", {"Bloomberg.us": ["US - Bloomberg"], "HallmarkMovies.pluto": ["PLUTO - Hallmark Movies"]}),
         ("uk", {"CNN.uk": ["UK - CNN"]})])
    assert found == {}


def test_plex_channels_bridge_to_the_backups_plex_copy():
    found = bridge({"plex.tv.Gravitas.Movies.plex": ["Gravitas Movies"]},
                   {"GravitasMovies.us": ["US - Gravitas Movies"],
                    "GravitasMovies_Plex.us": ["US - Gravitas Movies [Plex]"]})
    assert found == {"plex.tv.Gravitas.Movies.plex": "GravitasMovies_Plex.us"}


def test_local_stations_bridge_by_callsign_and_subchannel():
    found = bridge({"WCBI-DT.us_locals1": ["WCBI-DT"], "WCBI-DT2.us_locals1": ["WCBI-DT2"],
                    "KMOV-DT.us_locals1": ["KMOV-DT"], "WEAR-DT3.us_locals1": ["WEAR-DT3"]},
                   {"CBSWCBI.us": ["US - CBS WCBI Columbus MS"], "FOXWCBIDT2.us": ["US - FOX WCBI-DT2 Columbus MS"],
                    "ABCKMOVDT7.us": ["US - ABC KMOV-DT7 St. Louis MO"], "CBSKMOV.us": ["US - CBS KMOV St. Louis MO"],
                    "ABCWEAR.us": ["US - ABC WEAR Pensacola FL"]})
    assert found == {"WCBI-DT.us_locals1": "CBSWCBI.us", "WCBI-DT2.us_locals1": "FOXWCBIDT2.us",
                     "KMOV-DT.us_locals1": "CBSKMOV.us"}


def test_a_name_shared_by_two_different_backup_channels_is_not_guessed():
    found = bridge({"Fox.Sports.us2": ["Fox Sports"]},
                   {"FoxSports1.us": ["US - Fox Sports"], "FoxSportsX.us": ["US - Fox Sports"]})
    assert found == {}


# --- filling the guide ---------------------------------------------------------------------------

def read_titles(path):
    with gzip.open(path, "rb") as f:
        root = etree.parse(f).getroot()
    return [(p.get("channel"), p.findtext("title")) for p in root.findall("programme")]


def test_stale_channel_is_filled_from_backup_after_its_own_listings_end(tmp_path):
    primary, spare, out = tmp_path / "p.xml.gz", tmp_path / "b.xml.gz", tmp_path / "g.xml.gz"
    make_source(primary, [("CNN.us2", NOW - HOUR, NOW + HOUR, "Own")])
    make_source(spare, [("CNN.us", NOW - HOUR, NOW + HOUR, "Backup overlap"),
                        ("CNN.us", NOW + HOUR, NOW + 2 * HOUR, "Backup next")])
    stats = guide.write_guide(str(out), {"US: CNN HD": "CNN.us2"}, [str(primary)], NOW,
                              backups=[(str(spare), {"CNN.us": ["CNN.us2"]})])
    assert read_titles(out) == [("US: CNN HD", "Own"), ("US: CNN HD", "Backup next")]
    assert (stats.channels_with_upcoming, stats.bridged_channels) == (1, 1)


def test_channel_with_fresh_listings_ignores_the_backup(tmp_path):
    primary, spare, out = tmp_path / "p.xml.gz", tmp_path / "b.xml.gz", tmp_path / "g.xml.gz"
    make_source(primary, [("CNN.us2", NOW + i * HOUR, NOW + (i + 1) * HOUR, f"Own {i}") for i in range(30)])
    make_source(spare, [("CNN.us", NOW + 30 * HOUR, NOW + 31 * HOUR, "Backup")])
    stats = guide.write_guide(str(out), {"US: CNN": "CNN.us2"}, [str(primary)], NOW,
                              backups=[(str(spare), {"CNN.us": ["CNN.us2"]})])
    assert ("US: CNN", "Backup") not in read_titles(out)
    assert stats.bridged_channels == 0


def test_channel_missing_from_its_source_entirely_uses_the_backup(tmp_path):
    primary, spare, out = tmp_path / "p.xml.gz", tmp_path / "b.xml.gz", tmp_path / "g.xml.gz"
    make_source(primary, [("Other.us2", NOW, NOW + HOUR, "Other")])
    make_source(spare, [("WCBI.us", NOW, NOW + HOUR, "Local news")])
    stats = guide.write_guide(str(out), {"US: CBS (WCBI)": "WCBI-DT.us_locals1"}, [str(primary)], NOW,
                              backups=[(str(spare), {"WCBI.us": ["WCBI-DT.us_locals1"]})])
    assert read_titles(out) == [("US: CBS (WCBI)", "Local news")]
    assert (stats.channels_with_upcoming, stats.bridged_channels) == (1, 1)


def test_a_backup_name_carrying_a_subchannel_is_not_the_main_feed():
    found = bridge({"WNKY-DT.us_locals1": ["WNKY-DT"], "WNKY-DT2.us_locals1": ["WNKY-DT2"]},
                   {"CBSWNKY.us": ["US - CBS WNKY WNKY-DT2 Bowling Green KY"]})
    assert found == {"WNKY-DT2.us_locals1": "CBSWNKY.us"}


def test_plan_refuses_a_twin_from_another_network(tmp_path):
    backups = [("us", str(tmp_path / "b.xml.gz"), {"NBCWXYZ.us": ["US - NBC WXYZ Detroit MI"],
                                                     "CBSKAAA.us": ["US - CBS KAAA Somewhere"]})]
    plan, count = backup.plan({"WXYZ-DT.us_locals1", "KAAA-DT.us_locals1"},
                              {"WXYZ-DT.us_locals1": ["WXYZ-DT"], "KAAA-DT.us_locals1": ["KAAA-DT"]}, backups,
                              networks={"WXYZ-DT.us_locals1": {"ABC"}, "KAAA-DT.us_locals1": {"CBS"}})
    assert plan == [(str(tmp_path / "b.xml.gz"), {"CBSKAAA.us": ["KAAA-DT.us_locals1"]})] and count == 1


def test_names_made_only_of_generic_words_are_never_bridged():
    found = bridge({"West.TV.us2": ["West TV"], "Movies.us2": ["Movies!"]},
                   {"WESTNetwork.us": ["US - WEST Network"], "Movies.us": ["US - MOVIES!"]})
    assert found == {}
