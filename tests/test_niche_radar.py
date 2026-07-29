from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from content_radar.niche_radar import (
    compute_heat_score,
    discover_breakout_channels,
    find_trending_videos,
    parse_youtube_timestamp,
)


def test_compute_heat_score_one_day_old():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    published = now - timedelta(days=1)
    score = compute_heat_score(1000, published, now=now)
    assert score == 1000.0


def test_compute_heat_score_half_day_old():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    published = now - timedelta(hours=12)
    score = compute_heat_score(1000, published, now=now)
    assert score == 2000.0


def test_compute_heat_score_clamps_min_age():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    published = now - timedelta(minutes=1)
    score = compute_heat_score(100, published, now=now, min_age_hours=1.0)
    assert score == 2400.0


def test_compute_heat_score_zero_views():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    published = now - timedelta(days=2)
    assert compute_heat_score(0, published, now=now) == 0.0


def test_parse_youtube_timestamp():
    dt = parse_youtube_timestamp("2026-07-28T10:00:00Z")
    assert dt == datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)


def test_find_trending_videos_ranks_by_heat_and_dedupes(monkeypatch):
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)

    client = MagicMock()
    client.search_videos.side_effect = [
        [{"id": {"videoId": "vid_low"}}, {"id": {"videoId": "vid_high"}}],
        [{"id": {"videoId": "vid_high"}}],  # duplicate across keywords
    ]
    client.get_video_stats.return_value = [
        {
            "id": "vid_low",
            "snippet": {
                "title": "Low heat video",
                "channelId": "chan1",
                "channelTitle": "Channel One",
                "publishedAt": "2026-07-22T00:00:00Z",  # 7 days old
            },
            "statistics": {"viewCount": "700", "likeCount": "10", "commentCount": "1"},
        },
        {
            "id": "vid_high",
            "snippet": {
                "title": "High heat video",
                "channelId": "chan2",
                "channelTitle": "Channel Two",
                "publishedAt": "2026-07-28T00:00:00Z",  # 1 day old
            },
            "statistics": {"viewCount": "5000", "likeCount": "200", "commentCount": "20"},
        },
    ]

    videos = find_trending_videos(client, ["ai coding", "productivity"], days=7, now=now)

    assert [v.video_id for v in videos] == ["vid_high", "vid_low"]
    assert client.get_video_stats.call_count == 1
    called_ids = client.get_video_stats.call_args[0][0]
    assert called_ids == ["vid_low", "vid_high"]


def _trending_video(video_id, channel_id, channel_title, category_id="20"):
    return {
        "id": video_id,
        "snippet": {
            "title": f"Title for {video_id}",
            "channelId": channel_id,
            "channelTitle": channel_title,
            "publishedAt": "2026-07-28T00:00:00Z",
            "categoryId": category_id,
        },
        "statistics": {"viewCount": "1000", "likeCount": "10", "commentCount": "1"},
    }


def _channel_detail(channel_id, title, published_at, subscriber_count, view_count):
    return {
        "id": channel_id,
        "snippet": {"title": title, "publishedAt": published_at},
        "statistics": {
            "subscriberCount": str(subscriber_count),
            "viewCount": str(view_count),
            "videoCount": "10",
        },
    }


def test_discover_breakout_channels_filters_by_age_and_ratio():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)

    client = MagicMock()
    client.list_trending_videos.return_value = [
        _trending_video("vid_new_hot", "chan_new_hot", "New Hot Channel"),
        _trending_video("vid_old", "chan_old", "Old Established Channel"),
        _trending_video("vid_new_low_ratio", "chan_new_low_ratio", "New Low Ratio Channel"),
        # duplicate channel appears twice in trending videos; should dedupe
        _trending_video("vid_new_hot_2", "chan_new_hot", "New Hot Channel"),
    ]
    client.get_channel_details.return_value = [
        # New channel (30 days old), view/sub ratio = 1,000,000/10,000 = 100 -> breakout
        _channel_detail(
            "chan_new_hot", "New Hot Channel", "2026-06-29T00:00:00Z", 10_000, 1_000_000
        ),
        # Old channel (5 years old), high ratio but too old -> excluded
        _channel_detail(
            "chan_old", "Old Established Channel", "2021-01-01T00:00:00Z", 500_000, 50_000_000
        ),
        # New channel but low ratio (2,000/10,000 = 0.2) -> excluded
        _channel_detail(
            "chan_new_low_ratio",
            "New Low Ratio Channel",
            "2026-07-01T00:00:00Z",
            10_000,
            2_000,
        ),
    ]

    results = discover_breakout_channels(
        client,
        region_code="US",
        max_channel_age_days=365,
        min_view_to_sub_ratio=5.0,
        now=now,
    )

    assert [c.channel_id for c in results] == ["chan_new_hot"]
    assert client.get_channel_details.call_args[0][0] == [
        "chan_new_hot",
        "chan_old",
        "chan_new_low_ratio",
    ]
    breakout = results[0]
    assert breakout.view_to_sub_ratio == 100.0
    assert breakout.subscriber_count == 10_000
    assert breakout.view_count == 1_000_000
    assert breakout.example_video_id == "vid_new_hot"
    assert round(breakout.channel_age_days) == 30


def test_discover_breakout_channels_ranks_by_ratio_desc():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)

    client = MagicMock()
    client.list_trending_videos.return_value = [
        _trending_video("vid_a", "chan_a", "Channel A"),
        _trending_video("vid_b", "chan_b", "Channel B"),
    ]
    client.get_channel_details.return_value = [
        _channel_detail("chan_a", "Channel A", "2026-06-01T00:00:00Z", 1_000, 10_000),  # ratio 10
        _channel_detail("chan_b", "Channel B", "2026-06-01T00:00:00Z", 1_000, 100_000),  # ratio 100
    ]

    results = discover_breakout_channels(client, min_view_to_sub_ratio=5.0, now=now)

    assert [c.channel_id for c in results] == ["chan_b", "chan_a"]


def test_discover_breakout_channels_no_matches_returns_empty_list():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)

    client = MagicMock()
    client.list_trending_videos.return_value = [
        _trending_video("vid_a", "chan_a", "Channel A"),
    ]
    client.get_channel_details.return_value = [
        _channel_detail("chan_a", "Channel A", "2020-01-01T00:00:00Z", 1_000, 10_000),
    ]

    results = discover_breakout_channels(
        client, max_channel_age_days=365, min_view_to_sub_ratio=5.0, now=now
    )

    assert results == []
