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


def test_carry_over_skips_ambiguous_pairs():
    assert matching.carry_over_renames(["US| CNN FHD", "US| CNN 4K"], {"US| CNN HD": "CNN.us"}) == {}
    assert matching.carry_over_renames(["US| CNN FHD"], {"US| CNN HD": "CNN.us", "US| CNN SD": "CNNsd.us"}) == {}


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
