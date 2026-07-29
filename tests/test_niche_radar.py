from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from content_radar.niche_radar import (
    compute_heat_score,
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
