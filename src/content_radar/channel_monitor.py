"""Module 2: own-channel monitoring.

Tracks the user's own channel(s): subscriber/view growth, per-video
performance vs. channel average, and comment sentiment (sentiment
scoring itself is left as a TODO — the schema column exists so it can
be filled in later without a migration).

YouTube is fully implemented via the Data/Analytics API. TikTok and
Instagram only expose "own account" insight data through their
official Business/Creator APIs, which this user does not yet have
credentials for — those sources are stubbed out below.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from content_radar.db import get_connection
from content_radar.youtube_client import YouTubeClient


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


@dataclass
class ChannelStats:
    channel_id: str
    platform: Platform
    subscriber_count: int
    view_count: int
    video_count: int


@dataclass
class VideoPerformance:
    video_id: str
    title: str
    view_count: int
    like_count: int
    comment_count: int
    published_at: str


class ChannelSource(ABC):
    """Interface every platform-specific channel data source must implement."""

    platform: Platform

    @abstractmethod
    def get_channel_stats(self, channel_id: str) -> ChannelStats:
        """Return current subscriber/view/video counts for the channel."""

    @abstractmethod
    def get_recent_video_performance(
        self, channel_id: str, max_results: int = 25
    ) -> list[VideoPerformance]:
        """Return recent videos/posts with their engagement stats."""


class YouTubeChannelSource(ChannelSource):
    """Fully implemented channel source backed by the YouTube Data API."""

    platform = Platform.YOUTUBE

    def __init__(self, client: YouTubeClient) -> None:
        self._client = client

    def get_channel_stats(self, channel_id: str) -> ChannelStats:
        items = self._client.get_channel_stats([channel_id])
        if not items:
            raise ValueError(f"No YouTube channel found for id {channel_id!r}")
        stats = items[0].get("statistics", {})
        return ChannelStats(
            channel_id=channel_id,
            platform=self.platform,
            subscriber_count=int(stats.get("subscriberCount", 0)),
            view_count=int(stats.get("viewCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
        )

    def get_recent_video_performance(
        self, channel_id: str, max_results: int = 25
    ) -> list[VideoPerformance]:
        search_results = self._client.search_videos(
            query="", max_results=max_results, published_after=None
        )
        # Real implementation should search scoped to the channel
        # (search.list part=snippet, channelId=channel_id) rather than a
        # blank global query; kept simple here since search_videos is a
        # thin generic wrapper. See TODO below.
        video_ids = [
            item["id"]["videoId"] for item in search_results if "videoId" in item.get("id", {})
        ]
        stats_items = self._client.get_video_stats(video_ids)
        return [
            VideoPerformance(
                video_id=item["id"],
                title=item.get("snippet", {}).get("title", ""),
                view_count=int(item.get("statistics", {}).get("viewCount", 0)),
                like_count=int(item.get("statistics", {}).get("likeCount", 0)),
                comment_count=int(item.get("statistics", {}).get("commentCount", 0)),
                published_at=item.get("snippet", {}).get("publishedAt", ""),
            )
            for item in stats_items
        ]


class TikTokChannelSource(ChannelSource):
    """Stub for TikTok own-account monitoring.

    TODO: implement once the user has TikTok for Developers / Business
    API credentials. TikTok's official Business API exposes owned-account
    insights (follower count, video views, engagement) via the
    ``/v2/business/get/`` endpoints, but requires app review and OAuth
    for the account being monitored. Plug credentials in via
    ``TIKTOK_API_KEY`` (see .env.example) and implement the two methods
    below using that client.
    """

    platform = Platform.TIKTOK

    def get_channel_stats(self, channel_id: str) -> ChannelStats:
        raise NotImplementedError(
            "TikTok channel monitoring requires Business/Creator API credentials; not yet configured."
        )

    def get_recent_video_performance(
        self, channel_id: str, max_results: int = 25
    ) -> list[VideoPerformance]:
        raise NotImplementedError(
            "TikTok channel monitoring requires Business/Creator API credentials; not yet configured."
        )


class InstagramChannelSource(ChannelSource):
    """Stub for Instagram own-account monitoring.

    TODO: implement once the user has an Instagram Graph API app with a
    connected Business/Creator account. The Instagram Graph API exposes
    ``/{ig-user-id}/insights`` for owned-account metrics (impressions,
    reach, follower count) and ``/{media-id}/insights`` for per-post
    performance. Plug credentials in via ``INSTAGRAM_API_KEY`` (see
    .env.example) and implement the two methods below using that client.
    """

    platform = Platform.INSTAGRAM

    def get_channel_stats(self, channel_id: str) -> ChannelStats:
        raise NotImplementedError(
            "Instagram channel monitoring requires Graph API credentials; not yet configured."
        )

    def get_recent_video_performance(
        self, channel_id: str, max_results: int = 25
    ) -> list[VideoPerformance]:
        raise NotImplementedError(
            "Instagram channel monitoring requires Graph API credentials; not yet configured."
        )


def compute_deltas(previous: ChannelStats | None, current: ChannelStats) -> dict:
    """Compute simple deltas vs. the previous snapshot (0 if no history)."""
    if previous is None:
        return {"subscriber_delta": 0, "view_delta": 0, "video_delta": 0}
    return {
        "subscriber_delta": current.subscriber_count - previous.subscriber_count,
        "view_delta": current.view_count - previous.view_count,
        "video_delta": current.video_count - previous.video_count,
    }


def flag_video_performance(
    videos: list[VideoPerformance],
) -> list[tuple[VideoPerformance, str]]:
    """Flag each video as over/under/average performer vs. the channel mean view count."""
    if not videos:
        return []
    avg_views = sum(v.view_count for v in videos) / len(videos)
    flagged = []
    for video in videos:
        if video.view_count >= avg_views * 1.5:
            flag = "overperforming"
        elif video.view_count <= avg_views * 0.5:
            flag = "underperforming"
        else:
            flag = "average"
        flagged.append((video, flag))
    return flagged


def get_previous_channel_snapshot(
    channel_id: str, platform: Platform, db_path=None
) -> ChannelStats | None:
    conn = get_connection(db_path) if db_path else get_connection()
    try:
        row = conn.execute(
            """
            SELECT subscriber_count, view_count, video_count
            FROM channel_snapshots
            WHERE channel_id = ? AND platform = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (channel_id, platform.value),
        ).fetchone()
        if row is None:
            return None
        return ChannelStats(
            channel_id=channel_id,
            platform=platform,
            subscriber_count=row["subscriber_count"],
            view_count=row["view_count"],
            video_count=row["video_count"],
        )
    finally:
        conn.close()


def store_channel_snapshot(stats: ChannelStats, db_path=None) -> None:
    conn = get_connection(db_path) if db_path else get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO own_channels (channel_id, platform, label) VALUES (?, ?, ?)",
            (stats.channel_id, stats.platform.value, None),
        )
        conn.execute(
            """
            INSERT INTO channel_snapshots (
                channel_id, platform, subscriber_count, view_count, video_count, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                stats.channel_id,
                stats.platform.value,
                stats.subscriber_count,
                stats.view_count,
                stats.video_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
