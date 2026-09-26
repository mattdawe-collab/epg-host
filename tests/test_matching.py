import matching

REFERENCE = {
    "CNN": "CNN.us",
    "CNN International": "CNNInternational.uk",
    "BBC One": "BBCOne.uk",
    "CBC Toronto": "CBLT.ca",
    "ESPN": "ESPN.us",
    "ESPN 2": "ESPN2.us",
}
VALID = set(REFERENCE.values())


def test_priority_prefixes():
    assert matching.is_priority_channel("US| CNN HD")
    assert matching.is_priority_channel("SLING| AMC")
    assert not matching.is_priority_channel("FR| TF1")
    assert not matching.is_priority_channel("USA NETWORK")


def test_core_name_skips_every_prefix_and_quality_tag():
    assert matching.extract_core_name("SLING| AMC") == "AMC"
    assert matching.extract_core_name("PLAY+| DISCOVERY") == "DISCOVERY"
    assert matching.extract_core_name("US| CNN HD") == "CNN"
    assert matching.extract_core_name("US| ABC 7 (WABC) NEW YORK") == "WABC"


def test_normalize_ignores_quality_tags_and_punctuation():
    assert matching.normalize_name("US| CNN HD") == matching.normalize_name("US| CNN FHD")
    assert matching.normalize_name("US| CNN ᴴᴰ") == matching.normalize_name("US| CNN")
    assert matching.normalize_name("US| A&E HD") == matching.normalize_name("US| A E")


def test_normalize_keeps_prefix_and_numbers():
    assert matching.normalize_name("UK| BBC ONE HD") != matching.normalize_name("US| BBC ONE HD")
    assert matching.normalize_name("US| ESPN 2 HD") != matching.normalize_name("US| ESPN HD")


def test_carry_over_simple_rename():
    known = {"US| CNN HD": "CNN.us", "US| FOX NEWS": "FoxNews.us"}
    assert matching.carry_over_renames(["US| CNN FHD", "US| FOX NEWS"], known) == {
        "US| CNN FHD": {"from": "US| CNN HD", "id": "CNN.us"}}


def test_carry_over_gives_every_quality_copy_the_same_match():
    renames = matching.carry_over_renames(["US| CNN FHD", "US| CNN 4K"], {"US| CNN HD": "CNN.us"})
    assert {n: r["id"] for n, r in renames.items()} == {"US| CNN FHD": "CNN.us", "US| CNN 4K": "CNN.us"}


def test_carry_over_skips_when_old_matches_disagree():
    assert matching.carry_over_renames(["US| CNN FHD"], {"US| CNN HD": "CNN.us", "US| CNN SD": "CNNsd.us"}) == {}


def test_new_colon_naming_is_recognised():
    assert matching.is_priority_channel("US: CNN HD")
    assert matching.is_priority_channel("AT&T: AMC ᴿᴬᵂ")
    assert matching.is_priority_channel("CA EN: CTV TORONTO")
    assert not matching.is_priority_channel("FR: TF1")
    assert matching.extract_core_name("US: CNN HD") == "CNN"
    assert matching.extract_core_name("AT&T: AMC") == "AMC"
    assert matching.extract_core_name("CA EN: CTV (CFTO) TORONTO") == "CFTO"
    assert matching.normalize_name("US: CNN HD") == matching.normalize_name("US| CNN FHD")
    assert [matching.region_of(n) for n in ("US: CNN", "AT&T: AMC", "TV: FOX", "CA FR: TVA", "NOW: SKY", "PRIME: X")] == \
        ["US", "US", "ALL", "CA", "UK", "ALL"]


def test_carry_over_follows_regrouped_channels():
    known = {"SLING| AMC": "AMC.us", "GO| FOX 5": "WNYW.us", "UK-NOWTV| SKY ATLANTIC": "SkyAtlantic.uk",
             "CA| CTV TORONTO": "CFTO.ca", "US| CNN HD": "CNN.us"}
    current = ["AT&T: AMC", "TV: FOX 5", "NOW: SKY ATLANTIC", "CA EN: CTV TORONTO", "US: CNN HD", "US: CNN 4K"]
    renames = matching.carry_over_renames(current, known)
    assert {n: r["id"] for n, r in renames.items()} == {
        "AT&T: AMC": "AMC.us", "TV: FOX 5": "WNYW.us", "NOW: SKY ATLANTIC": "SkyAtlantic.uk",
        "CA EN: CTV TORONTO": "CFTO.ca", "US: CNN HD": "CNN.us", "US: CNN 4K": "CNN.us"}


def test_carry_over_ignores_section_headers_and_other_prefixes():
    assert matching.carry_over_renames(["FR| TF1 FHD"], {"##### NEWS #####": "x", "FR| TF1 HD": "TF1.fr"}) == {}


def test_carry_over_handles_duplicate_names_in_list():
    assert matching.carry_over_renames(["US| CNN FHD", "US| CNN FHD"], {"US| CNN HD": "CNN.us"}) == {
        "US| CNN FHD": {"from": "US| CNN HD", "id": "CNN.us"}}


def test_carry_over_works_again_after_an_earlier_rename():
    known = {"US| CNN HD": "CNN.us", "US| CNN FHD": "CNN.us"}
    renames = matching.carry_over_renames(["US| CNN ᴴᴰ"], known)
    assert renames["US| CNN ᴴᴰ"]["id"] == "CNN.us"
    assert renames["US| CNN ᴴᴰ"]["from"] in known


def test_resolve_order():
    known = {"US| CNN HD": "CNN.us", "US| OLD NAME HD": "ESPN.us", "US| GONE": "Missing.us"}
    no_guide = {"US| PPV EVENT 1": "2026-09-26"}
    names = ["US| CNN HD", "US| PPV EVENT 1", "US| OLD NAME FHD", "UK| BBC ONE", "US| TOTALLY UNKNOWN XYZ", "US| GONE"]
    res = matching.resolve(names, known, no_guide, REFERENCE, VALID)
    assert res.matches == {"US| CNN HD": "CNN.us", "US| OLD NAME FHD": "ESPN.us", "UK| BBC ONE": "BBCOne.uk"}
    assert res.how == {"US| CNN HD": "saved", "US| OLD NAME FHD": "renamed", "UK| BBC ONE": "auto"}
    assert res.carried == {"US| OLD NAME FHD": {"from": "US| OLD NAME HD", "id": "ESPN.us"}}
    queued = {e["name"]: e for e in res.queue}
    assert set(queued) == {"US| TOTALLY UNKNOWN XYZ", "US| GONE"}
    assert queued["US| GONE"]["reason"] == "vanished_id" and queued["US| GONE"]["previous_id"] == "Missing.us"
    assert queued["US| TOTALLY UNKNOWN XYZ"]["reason"] == "new"
    assert dict(res.counts) == {"known": 1, "no_guide": 1, "carried": 1, "auto": 1, "queued": 2}


def test_resolve_lists_each_channel_once():
    res = matching.resolve(["US| CNN HD", "US| CNN HD"], {"US| CNN HD": "CNN.us"}, {}, REFERENCE, VALID)
    assert res.matches == {"US| CNN HD": "CNN.us"}
    assert res.counts["known"] == 1


def test_rejected_pairs_are_never_auto_matched():
    res = matching.resolve(["UK| BBC ONE"], {}, {}, REFERENCE, VALID, rejected={"UK| BBC ONE": ["BBCOne.uk"]})
    assert res.matches == {}
    assert [e["name"] for e in res.queue] == ["UK| BBC ONE"]


def test_rejected_pairs_are_never_carried_over():
    res = matching.resolve(["US| CNN FHD"], {"US| CNN HD": "CNN.us"}, {}, {"Other": "Other.us"}, VALID | {"Other.us"},
                           rejected={"US| CNN FHD": ["CNN.us"]})
    assert "US| CNN FHD" not in res.matches


def test_queue_entry_has_candidates_and_only_valid_provider_hints():
    name = "US| TOTALLY UNKNOWN XYZ"
    entry = matching.resolve([name], {}, {}, REFERENCE, VALID, provider_ids={name: "ESPN2.us"}).queue[0]
    assert entry["provider_id"] == "ESPN2.us"
    assert 0 < len(entry["candidates"]) <= 10
    assert all(c["id"] in VALID for c in entry["candidates"])
    entry = matching.resolve([name], {}, {}, REFERENCE, VALID, provider_ids={name: "Nope.us"}).queue[0]
    assert "provider_id" not in entry


def test_candidates_are_capped():
    pools = matching.Pools({f"CNN {i}": f"CNN{i}.us" for i in range(30)})
    assert len(pools.candidates("US", "US| CNN", limit=10)) == 10


def test_plus_services_are_not_quality_copies():
    renames = matching.carry_over_renames(["UK: AMC FHD", "UK: AMC + 4K"], {"UK| AMC HD": "AMC.uk"})
    assert {n: r["id"] for n, r in renames.items()} == {"UK: AMC FHD": "AMC.uk"}


def test_decorations_are_ignored():
    assert matching.normalize_name("US: AMC ᴿᴬᵂ") == matching.normalize_name("US| AMC")
    assert matching.extract_core_name("US: AMC ᴿᴬᵂ") == "AMC"
    assert matching.extract_core_name("4K: V SPORT ᵁᴴᴰ ³⁸⁴⁰ᴾ") == "V SPORT"
    assert matching.extract_core_name("UK: DISCOVERY 4K ◉") == "DISCOVERY"


def test_feed_words_are_not_callsigns():
    assert matching.extract_core_name("US: NBC SYFY (WEST)") == "NBC SYFY"


def auto(name, by_name, index=None, expected_country=None):
    return matching.quick_match(name, matching.Pools(by_name, index), expected_country)


def test_auto_match_stays_in_the_channel_country():
    assert auto("UK: DISNEY JUNIOR 4K", {"DISNEY JUNIOR": "DISNEY.JUNIOR.co"}) is None
    assert auto("UK: DISNEY JUNIOR 4K", {"DISNEY JUNIOR": "DISNEY.JUNIOR.co", "Disney Junior": "DisneyJunior.uk"}) == "DisneyJunior.uk"


def test_auto_match_needs_near_identical_names():
    assert auto("US: LUCIFER ᴿᴬᵂ", {"WLUC-DT": "WLUC-DT.us_locals1"}) is None
    assert auto("US: NBC SYFY (WEST)", {"WEST": "WEST.gr", "KWES": "KWES.us"}) is None


def test_auto_match_never_uses_a_timeshift_feed():
    assert auto("UK: DISCOVERY 4K", {"Discovery+1": "Discovery+1.uk"}) is None
    assert auto("UK: DISCOVERY 4K", {"Discovery+1": "Discovery+1.uk", "Discovery": "Discovery.uk"}) == "Discovery.uk"


def test_event_and_loop_channels_get_no_guide_automatically():
    res = matching.resolve(["CA: DAZN 16 PPV", "US: 24/7 SIMPSONS"], {}, {}, {"PPV": "PPV.ca2"}, {"PPV.ca2"})
    assert res.matches == {} and res.queue == []
    assert res.counts["no_guide_auto"] == 2


def test_flagged_legacy_matches_are_not_trusted():
    legacy = {"US| HGTV HD": "HGTV.za", "US| CNN HD": "CNN.us"}
    res = matching.resolve(["US: HGTV HD", "US: CNN HD"], {}, {}, {"Other": "Other.us"}, {"HGTV.za", "CNN.us", "Other.us"},
                           legacy=legacy)
    assert res.matches == {"US: CNN HD": "CNN.us"}
    assert res.how == {"US: CNN HD": "renamed"}
    assert res.queue[0]["name"] == "US: HGTV HD" and res.queue[0]["previous_id"] == "HGTV.za"


def test_session_decisions_are_trusted_even_when_flagged():
    res = matching.resolve(["US: HGTV HD"], {"US: HGTV HD": "HGTV.za"}, {}, {}, {"HGTV.za"})
    assert res.matches == {"US: HGTV HD": "HGTV.za"} and res.how == {"US: HGTV HD": "saved"}


def test_flag_reasons_live_in_matching():
    assert matching.flag_reasons("US| CNN", "CNN.uk") == ["region"]


def test_mixed_groups_only_take_home_countries_unless_the_country_is_known():
    assert matching.flag_reasons("TV: NOVA", "Nova.cz") == ["foreign"]
    assert matching.flag_reasons("TV: NOVA", "Nova.es", expected_country="es") == []
    assert matching.flag_reasons("TV: NOVA", "Nova.cz", expected_country="es") == ["region"]
    assert matching.flag_reasons("TV: SNL VAULT", "plex.tv.SNL.Vault.plex") == []
    assert matching.flag_reasons("PRIME: AMC", "AMC.us") == []
    assert matching.flag_reasons("CA: CNN", "CNN.us", expected_country="us") == []


def test_placeholder_guides_are_flagged():
    assert "placeholder" in matching.flag_reasons("US: PEACOCK ORIGINAL 5", "Peacock.Dummy.us")


def test_expected_country_comes_from_the_channel_or_its_playlist_section():
    channels = [
        {"name": "#### CABEL TV ####", "epg_id": None},
        {"name": "TV: NOVA", "epg_id": "nova.es"},
        {"name": "TV: EUROSPORT 1", "epg_id": "eurosport1.es"},
        {"name": "TV: WARNER TV", "epg_id": None},
        {"name": "#### ISRAEL ####", "epg_id": None},
        {"name": "TV: YES CINEMA", "epg_id": "yescinema.il"},
        {"name": "TV: ONE HINT ONLY", "epg_id": None},
        {"name": "#### MIXED ####", "epg_id": None},
        {"name": "TV: A", "epg_id": "a.es"},
        {"name": "TV: B", "epg_id": "b.il"},
        {"name": "TV: C", "epg_id": None},
    ]
    assert matching.expected_countries(channels) == {
        "TV: NOVA": "es", "TV: EUROSPORT 1": "es", "TV: WARNER TV": "es", "TV: YES CINEMA": "il",
        "TV: A": "es", "TV: B": "il"}


def test_auto_match_finds_the_expected_country_among_same_named_guides():
    by_name = {"Nova": "Nova.cz"}
    index = {"Nova.cz": ["Nova"], "Nova.es": ["Nova"]}
    assert auto("TV: NOVA", by_name, index, expected_country="es") == "Nova.es"
    assert auto("TV: NOVA", by_name, index) is None


def test_legacy_matches_must_resemble_the_guide():
    index = {"HBO.East.us2": ["HBO East"], "CNN.us": ["CNN"], "WITI-DT.us_locals1": ["WITI-DT"]}
    legacy = {"US| GAME OF THRONES FHD": "HBO.East.us2", "US| CNN HD": "CNN.us", "US| FOX 6 MILWAUKEE (WITI)": "WITI-DT.us_locals1"}
    names = ["US: GAME OF THRONES 4K", "US: CNN HD", "US: FOX 6 MILWAUKEE (WITI)"]
    res = matching.resolve(names, {}, {}, {}, set(index), legacy=legacy, index=index)
    assert res.matches == {"US: CNN HD": "CNN.us", "US: FOX 6 MILWAUKEE (WITI)": "WITI-DT.us_locals1"}
    assert [e["name"] for e in res.queue] == ["US: GAME OF THRONES 4K"]


def test_resemblance_ignores_spacing_and_accents_but_not_different_numbers():
    def ok(name, xml_id, display):
        return matching.resembles(name, xml_id, {xml_id: [display]})
    assert ok("CA: RDS 2", "RDS2.HD.ca2", "RDS2 HD")
    assert ok("UK: CHANNEL 4 HEVC 4K", "Channel.4.HD.uk", "Channel 4 HD")
    assert ok("US: C-SPAN 1 HD", "CSPAN.us2", "CSPAN")
    assert ok("CA: EVASION", "Évasion.HD.ca2", "Évasion HD")
    assert ok("UK: E4 +1", "E4+1.uk", "E4+1")
    assert not ok("CA: RDS", "RDS2.HD.ca2", "RDS2 HD")
    assert not ok("UK: REALITY SHOW 6", "TNT.Sports.6.HD.uk", "TNT Sports 6 HD")
    assert not ok("US: WHERE ARE YOU 4K", "WYOU-DT.us_locals1", "WYOU-DT")
    assert matching.normalize_name("CA: ÉVASION") == matching.normalize_name("CA| EVASION")


def test_numeric_guide_ids_get_their_source_country():
    assert matching.flag_reasons("US: NICKELODEON HD", "12084", id_country="uk") == ["region"]
    assert matching.flag_reasons("US: NICKELODEON HD", "12084") == []
    by_name = {"Nickelodeon": "12084"}
    index = {"12084": ["Nickelodeon"], "Nickelodeon.us2": ["Nickelodeon"]}
    pools = matching.Pools(by_name, index)
    assert matching.quick_match("US: NICKELODEON HD", pools, id_countries={"12084": "uk"}) == "Nickelodeon.us2"


def test_ppv_guides_are_placeholders():
    assert "placeholder" in matching.flag_reasons("CA EN: ROGERS SUPER SPORTS PACK 24", "PPV.Sports.ca2")


def test_quality_words_in_guide_names_do_not_block_a_match():
    by_name = {"CNN": "CNN.uk", "CNN HD": "CNN.HD.us2"}
    index = {"CNN.uk": ["CNN"], "CNN.HD.us2": ["CNN HD"]}
    assert matching.quick_match("US: CNN HD", matching.Pools(by_name, index)) == "CNN.HD.us2"
    assert matching.quick_match("US: CNN 4K", matching.Pools(by_name, index)) == "CNN.HD.us2"


STATION_IDS = {"WZTV-DT.us_locals1", "WZTV-DT2.us_locals1", "KIRO-LD.us_locals1", "KIRO-DT.us_locals1", "KIRO.7.ca2",
               "WWL-DT.us_locals1", "WGBC-DT.us_locals1", "WGBC-DT2.us_locals1", "KTVI-DT.us_locals1", "WEST.gr",
               "KSHB-DT.us_locals1", "CNN.us"}


def station(name):
    return matching.station_match(name, matching.Stations(STATION_IDS))


def test_callsign_in_brackets_picks_the_main_station():
    assert station("US: FOX 17 (WZTV) NASHVILLE HD") == "WZTV-DT.us_locals1"
    assert station("US: CBS 7 (KIRO) SEATTLE HD") == "KIRO-DT.us_locals1"
    assert station("US: CBS 4 (WWL) NEW ORLEANS HD") == "WWL-DT.us_locals1"
    assert station("US: NBC 30 (WGBC-DT2) MERIDIAN (H) ᴿᴬᵂ") == "WGBC-DT2.us_locals1"


def test_bare_callsign_needs_a_network_word_and_a_local_station():
    assert station("TV: ST. LOUIS, MO KTVI FOX 2 A3 HD COLUMBUS ᶜᶦᵗʸ ᴿᴬᵂ") == "KTVI-DT.us_locals1"
    assert station("US: NBC KSHB (A) ᴿᴬᵂ") == "KSHB-DT.us_locals1"
    assert station("US: KTVI SPORTS") is None
    assert station("US: DEADWOOD 4K") is None
    assert station("US: NBC SYFY (WEST)") is None


def test_station_matches_win_over_legacy_and_auto():
    names = ["US: FOX 17 (WZTV) NASHVILLE HD"]
    res = matching.resolve(names, {}, {}, {"WZTV": "WZTV-DT2.us_locals1"}, STATION_IDS,
                           legacy={"US| FOX 17 (WZTV) NASHVILLE HD": "WZTV-DT2.us_locals1"})
    assert res.matches == {"US: FOX 17 (WZTV) NASHVILLE HD": "WZTV-DT.us_locals1"}
    assert res.how == {"US: FOX 17 (WZTV) NASHVILLE HD": "station"}


def test_bare_callsign_with_a_subchannel_suffix_needs_that_subchannel():
    ids = {"KMOV-DT.us_locals1"}
    assert matching.station_match("TV: ST. LOUIS, MO KMOV-D2 ABC 30 A3 HD", matching.Stations(ids)) is None
    ids = {"KMOV-DT.us_locals1", "KMOV-DT2.us_locals1"}
    assert matching.station_match("TV: ST. LOUIS, MO KMOV-D2 ABC 30 A3 HD", matching.Stations(ids)) == "KMOV-DT2.us_locals1"
