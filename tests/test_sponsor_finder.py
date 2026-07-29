from content_radar.sponsor_finder import (
    aggregate_sponsor_candidates,
    find_brand_mentions,
)

SEED_LIST = ["NordVPN", "Squarespace", "Skillshare"]


def test_find_brand_mentions_seed_list_hit():
    mentions = find_brand_mentions(
        "This video is powered by NordVPN, get 70% off today!", "vid1", SEED_LIST
    )
    assert len(mentions) == 1
    assert mentions[0].brand_name == "NordVPN"
    assert mentions[0].video_url == "https://www.youtube.com/watch?v=vid1"


def test_find_brand_mentions_case_insensitive():
    mentions = find_brand_mentions("check out nordvpn today", "vid2", SEED_LIST)
    assert [m.brand_name for m in mentions] == ["NordVPN"]


def test_find_brand_mentions_sponsored_by_phrase_new_brand():
    mentions = find_brand_mentions(
        "Big thanks, this episode is sponsored by AcmeWidgets for their support.",
        "vid3",
        SEED_LIST,
    )
    brand_names = [m.brand_name for m in mentions]
    assert "AcmeWidgets" in brand_names


def test_find_brand_mentions_thanks_to_phrase():
    mentions = find_brand_mentions(
        "Thanks to Squarespace for sponsoring this video.", "vid4", SEED_LIST
    )
    brand_names = [m.brand_name for m in mentions]
    assert "Squarespace" in brand_names
    # Should not double-count the same brand from both heuristics
    assert brand_names.count("Squarespace") == 1


def test_find_brand_mentions_no_match():
    assert find_brand_mentions("just a regular video about cats", "vid5", SEED_LIST) == []


def test_find_brand_mentions_empty_text():
    assert find_brand_mentions("", "vid6", SEED_LIST) == []


def test_aggregate_sponsor_candidates_counts_and_sorts():
    mentions = (
        find_brand_mentions("sponsored by NordVPN", "vid1", SEED_LIST)
        + find_brand_mentions("another NordVPN sponsored by NordVPN video", "vid2", SEED_LIST)
        + find_brand_mentions("Skillshare ad here", "vid3", SEED_LIST)
    )
    aggregated = aggregate_sponsor_candidates(mentions)
    brands_in_order = [row[0] for row in aggregated]
    assert brands_in_order[0] == "NordVPN"
    counts = {brand: count for brand, count, _ in aggregated}
    assert counts["NordVPN"] == 2
    assert counts["Skillshare"] == 1
