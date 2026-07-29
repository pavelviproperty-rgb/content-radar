"""Thin wrapper around the YouTube Data API v3 client.

Keeps all googleapiclient calls in one place so higher-level modules
(niche_radar, channel_monitor, sponsor_finder) never talk to the API
directly and can be tested with a mock in place of ``YouTubeClient``.
"""

from __future__ import annotations

from googleapiclient.discovery import build


class YouTubeClient:
    """Wraps ``googleapiclient.discovery.build("youtube", "v3", ...)``."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required to build a YouTubeClient")
        self._service = build("youtube", "v3", developerKey=api_key)

    def search_videos(
        self,
        query: str,
        max_results: int = 25,
        published_after: str | None = None,
    ) -> list[dict]:
        """Search for videos matching ``query``.

        ``published_after`` must be an RFC 3339 timestamp (e.g.
        ``2026-07-01T00:00:00Z``) when provided. Returns the raw list of
        ``items`` from the YouTube ``search.list`` response.
        """
        request_kwargs = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": max_results,
        }
        if published_after:
            request_kwargs["publishedAfter"] = published_after

        request = self._service.search().list(**request_kwargs)
        response = request.execute()
        return response.get("items", [])

    def get_video_stats(self, video_ids: list[str]) -> list[dict]:
        """Fetch statistics + snippet for a batch of video IDs (max 50 per call)."""
        if not video_ids:
            return []
        items: list[dict] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            request = self._service.videos().list(
                part="snippet,statistics",
                id=",".join(batch),
            )
            response = request.execute()
            items.extend(response.get("items", []))
        return items

    def get_channel_stats(self, channel_ids: list[str]) -> list[dict]:
        """Fetch statistics for a batch of channel IDs (max 50 per call)."""
        if not channel_ids:
            return []
        items: list[dict] = []
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]
            request = self._service.channels().list(
                part="snippet,statistics",
                id=",".join(batch),
            )
            response = request.execute()
            items.extend(response.get("items", []))
        return items

    def get_channel_details(self, channel_ids: list[str]) -> list[dict]:
        """Alias for :meth:`get_channel_stats`.

        Returns ``snippet`` (including ``publishedAt``, the channel's
        creation date) plus ``statistics`` (subscriberCount, viewCount,
        videoCount) for each channel id. Kept as a separate name since
        callers reasoning about "channel details" (age + stats) may find
        it clearer than "stats" alone; both fetch the same ``part``.
        """
        return self.get_channel_stats(channel_ids)

    def list_trending_videos(
        self,
        region_code: str = "US",
        category_id: str | list[str] | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch currently trending ("mostPopular") videos.

        ``category_id`` may be ``None`` (no category filter, single call),
        a single category id string, or a list of category ids to loop
        over (results from each category call are concatenated and
        de-duplicated by video id). ``max_results`` is applied per
        category/call and capped at 50 per the API's own limit.
        """
        max_results = min(max_results, 50)

        if category_id is None:
            category_ids: list[str | None] = [None]
        elif isinstance(category_id, str):
            category_ids = [category_id]
        else:
            category_ids = list(category_id)

        items: list[dict] = []
        seen_ids: set[str] = set()
        for cat in category_ids:
            request_kwargs = {
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "regionCode": region_code,
                "maxResults": max_results,
            }
            if cat:
                request_kwargs["videoCategoryId"] = cat
            request = self._service.videos().list(**request_kwargs)
            response = request.execute()
            for item in response.get("items", []):
                video_id = item.get("id")
                if video_id in seen_ids:
                    continue
                seen_ids.add(video_id)
                items.append(item)
        return items

    def get_comments(self, video_id: str, max_results: int = 50) -> list[dict]:
        """Fetch top-level comment threads for a video."""
        request = self._service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            textFormat="plainText",
        )
        response = request.execute()
        return response.get("items", [])
