"""Module 1: niche trend radar.

Given seed keywords, search recent YouTube videos, pull their stats,
score them by view velocity ("heat"), persist a snapshot, and return a
ranked list. This is the only module that discovers third-party/
niche content — TikTok and Instagram do not expose comparable public
discovery APIs for arbitrary content, so this module is YouTube-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from content_radar.db import get_connection
from content_radar.youtube_client import YouTubeClient

ISO_FORMAT_VARIANTS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ")


def parse_youtube_timestamp(value: str) -> datetime:
    """Parse a YouTube API RFC3339 timestamp into an aware UTC datetime."""
    for fmt in ISO_FORMAT_VARIANTS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {value!r}")


def compute_heat_score(
    view_count: int,
    published_at: datetime,
    now: datetime | None = None,
    min_age_hours: float = 1.0,
) -> float:
    """Compute a simple "heat" score: views per day since publication.

    A video published less than ``min_age_hours`` ago is clamped to that
    age so brand-new videos with a handful of views don't produce a
    misleadingly explosive rate. Score is views / days-since-published.
    """
    now = now or datetime.now(timezone.utc)
    age_hours = max((now - published_at).total_seconds() / 3600, min_age_hours)
    age_days = age_hours / 24
    return view_count / age_days


@dataclass
class TrendingVideo:
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    view_count: int
    like_count: int
    comment_count: int
    published_at: str
    heat_score: float


def find_trending_videos(
    client: YouTubeClient,
    keywords: list[str],
    days: int = 7,
    max_results_per_keyword: int = 25,
    now: datetime | None = None,
) -> list[TrendingVideo]:
    """Search each keyword, pull stats, and rank all results by heat score."""
    now = now or datetime.now(timezone.utc)
    published_after = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    video_ids: list[str] = []
    for keyword in keywords:
        results = client.search_videos(
            keyword, max_results=max_results_per_keyword, published_after=published_after
        )
        video_ids.extend(item["id"]["videoId"] for item in results if "videoId" in item.get("id", {}))

    # de-duplicate while preserving order
    video_ids = list(dict.fromkeys(video_ids))
    stats_items = client.get_video_stats(video_ids)

    videos: list[TrendingVideo] = []
    for item in stats_items:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        published_at = parse_youtube_timestamp(snippet["publishedAt"])
        view_count = int(stats.get("viewCount", 0))
        videos.append(
            TrendingVideo(
                video_id=item["id"],
                title=snippet.get("title", ""),
                channel_id=snippet.get("channelId", ""),
                channel_title=snippet.get("channelTitle", ""),
                view_count=view_count,
                like_count=int(stats.get("likeCount", 0)),
                comment_count=int(stats.get("commentCount", 0)),
                published_at=snippet["publishedAt"],
                heat_score=compute_heat_score(view_count, published_at, now=now),
            )
        )

    videos.sort(key=lambda v: v.heat_score, reverse=True)
    return videos


@dataclass
class BreakoutChannel:
    channel_id: str
    channel_title: str
    channel_age_days: float
    subscriber_count: int
    view_count: int
    view_to_sub_ratio: float
    example_video_id: str
    example_video_title: str
    video_category_id: str | None


def discover_breakout_channels(
    youtube_client: YouTubeClient,
    region_code: str = "US",
    max_channel_age_days: float = 365,
    min_view_to_sub_ratio: float = 5.0,
    max_results: int = 50,
    category_ids: list[str] | None = None,
    now: datetime | None = None,
) -> list[BreakoutChannel]:
    """Auto-discover "breakout" channels with no seed keywords required.

    Pulls currently trending videos, dedupes their channels, fetches
    channel details (creation date + lifetime stats), and filters down
    to channels that are both relatively new (<= ``max_channel_age_days``)
    and have a view-count-to-subscriber-count ratio of at least
    ``min_view_to_sub_ratio`` -- a signal that a channel's audience is
    growing faster than its subscriber count, i.e. its niche is suddenly
    taking off. Results are ranked by view_to_sub_ratio descending.
    """
    now = now or datetime.now(timezone.utc)

    trending_videos = youtube_client.list_trending_videos(
        region_code=region_code, category_id=category_ids, max_results=max_results
    )

    # First video seen per channel, preserving order, for the "example" fields.
    channel_example: dict[str, dict] = {}
    channel_ids: list[str] = []
    for video in trending_videos:
        snippet = video.get("snippet", {})
        channel_id = snippet.get("channelId")
        if not channel_id:
            continue
        if channel_id not in channel_example:
            channel_example[channel_id] = video
            channel_ids.append(channel_id)

    channel_details = youtube_client.get_channel_details(channel_ids)

    breakouts: list[BreakoutChannel] = []
    for channel in channel_details:
        channel_id = channel.get("id")
        snippet = channel.get("snippet", {})
        stats = channel.get("statistics", {})

        published_at_raw = snippet.get("publishedAt")
        if not published_at_raw:
            continue
        published_at = parse_youtube_timestamp(published_at_raw)
        channel_age_days = (now - published_at).total_seconds() / 86400

        subscriber_count = int(stats.get("subscriberCount", 0))
        view_count = int(stats.get("viewCount", 0))
        view_to_sub_ratio = view_count / max(subscriber_count, 1)

        if channel_age_days > max_channel_age_days:
            continue
        if view_to_sub_ratio < min_view_to_sub_ratio:
            continue

        example = channel_example.get(channel_id, {})
        example_snippet = example.get("snippet", {})

        breakouts.append(
            BreakoutChannel(
                channel_id=channel_id,
                channel_title=snippet.get("title", ""),
                channel_age_days=channel_age_days,
                subscriber_count=subscriber_count,
                view_count=view_count,
                view_to_sub_ratio=view_to_sub_ratio,
                example_video_id=example.get("id", ""),
                example_video_title=example_snippet.get("title", ""),
                video_category_id=example_snippet.get("categoryId"),
            )
        )

    breakouts.sort(key=lambda b: b.view_to_sub_ratio, reverse=True)
    return breakouts


def store_breakout_channels(
    query: str, channels: list[BreakoutChannel], db_path=None
) -> int:
    """Persist a discovery-run niche + its ranked breakout channels, returning the niche id."""
    conn = get_connection(db_path) if db_path else get_connection()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO niches (query, created_at) VALUES (?, ?)", (query, now_iso)
        )
        niche_id = cur.lastrowid
        for channel in channels:
            conn.execute(
                """
                INSERT INTO breakout_channels (
                    niche_id, channel_id, channel_title, channel_age_days,
                    subscriber_count, view_count, view_to_sub_ratio,
                    example_video_id, example_video_title, category_id, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    niche_id,
                    channel.channel_id,
                    channel.channel_title,
                    channel.channel_age_days,
                    channel.subscriber_count,
                    channel.view_count,
                    channel.view_to_sub_ratio,
                    channel.example_video_id,
                    channel.example_video_title,
                    channel.video_category_id,
                    now_iso,
                ),
            )
        conn.commit()
        return niche_id
    finally:
        conn.close()


def store_niche_snapshot(query: str, videos: list[TrendingVideo], db_path=None) -> int:
    """Persist a niche + its ranked video snapshot, returning the niche id."""
    conn = get_connection(db_path) if db_path else get_connection()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO niches (query, created_at) VALUES (?, ?)", (query, now_iso)
        )
        niche_id = cur.lastrowid
        for video in videos:
            conn.execute(
                """
                INSERT INTO niche_snapshots (
                    niche_id, video_id, title, channel_id, channel_title,
                    view_count, like_count, comment_count, published_at, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    niche_id,
                    video.video_id,
                    video.title,
                    video.channel_id,
                    video.channel_title,
                    video.view_count,
                    video.like_count,
                    video.comment_count,
                    video.published_at,
                    now_iso,
                ),
            )
        conn.commit()
        return niche_id
    finally:
        conn.close()
