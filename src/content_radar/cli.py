"""Click CLI for content-radar."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import click
from dotenv import load_dotenv

from content_radar.channel_monitor import (
    Platform,
    YouTubeChannelSource,
    compute_deltas,
    flag_video_performance,
    get_previous_channel_snapshot,
    store_channel_snapshot,
)
from content_radar.db import init_db
from content_radar.niche_radar import (
    discover_breakout_channels,
    find_trending_videos,
    store_breakout_channels,
    store_niche_snapshot,
)
from content_radar.sponsor_finder import scan_niche_for_sponsors
from content_radar.youtube_client import YouTubeClient

load_dotenv()


def _require_youtube_client() -> YouTubeClient:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise click.ClickException(
            "YOUTUBE_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return YouTubeClient(api_key)


@click.group()
def cli() -> None:
    """content-radar: niche trend radar, channel monitor, and sponsor finder."""


@cli.command("init-db")
def init_db_command() -> None:
    """Create the SQLite schema (idempotent)."""
    init_db()
    click.echo("Database initialized.")


@cli.command("niches")
@click.option(
    "--keywords",
    default=None,
    help="Comma-separated seed keywords, e.g. 'ai coding,productivity'. "
    "If omitted, runs auto-discovery mode instead (see --discover).",
)
@click.option("--days", default=7, show_default=True, help="Look back this many days for recent videos (keyword mode).")
@click.option(
    "--discover/--no-discover",
    default=None,
    help="Auto-discover breakout channels instead of a keyword search. "
    "This is the default when --keywords is not given.",
)
@click.option("--region", default="US", show_default=True, help="YouTube region code for trending videos (discovery mode).")
@click.option("--max-age-days", default=365, show_default=True, help="Max channel age in days to count as a breakout candidate (discovery mode).")
@click.option("--min-ratio", default=5.0, show_default=True, help="Minimum view-count/subscriber-count ratio to count as a breakout candidate (discovery mode).")
def niches_command(
    keywords: str | None,
    days: int,
    discover: bool | None,
    region: str,
    max_age_days: float,
    min_ratio: float,
) -> None:
    """Find currently rising niches on YouTube.

    Default mode auto-discovers "breakout" channels (new + suddenly
    high view-to-subscriber ratio) from currently trending videos, with
    no keywords required. Pass --keywords for the original targeted
    keyword-search mode instead.
    """
    client = _require_youtube_client()

    # Discovery is the default mode; keyword search is opt-in via --keywords.
    run_discover = discover if discover is not None else not keywords

    if run_discover:
        channels = discover_breakout_channels(
            client,
            region_code=region,
            max_channel_age_days=max_age_days,
            min_view_to_sub_ratio=min_ratio,
        )
        today = datetime.now(timezone.utc).date().isoformat()
        query = f"auto-discovery:{region}:{today}"
        niche_id = store_breakout_channels(query, channels)

        click.echo(f"Niche id: {niche_id}")
        click.echo(
            f"{'Channel':<30}{'Age(d)':>8}{'Subs':>12}{'Views':>14}{'Ratio':>10}  Example"
        )
        for ch in channels:
            click.echo(
                f"{ch.channel_title:<30.30}{ch.channel_age_days:8.0f}{ch.subscriber_count:12d}"
                f"{ch.view_count:14d}{ch.view_to_sub_ratio:10.1f}  "
                f"https://youtube.com/watch?v={ch.example_video_id}"
            )
        if not channels:
            click.echo("No breakout channels found matching the given thresholds.")
        return

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    videos = find_trending_videos(client, keyword_list, days=days)
    niche_id = store_niche_snapshot(",".join(keyword_list), videos)

    click.echo(f"Niche id: {niche_id}")
    click.echo(f"{'Heat':>10}  {'Views':>10}  Title (channel)")
    for video in videos[:25]:
        click.echo(
            f"{video.heat_score:10.1f}  {video.view_count:10d}  {video.title} ({video.channel_title})"
        )


@cli.command("monitor")
@click.option("--channel-id", required=True, help="YouTube channel ID to monitor.")
def monitor_command(channel_id: str) -> None:
    """Pull channel + video stats for one of your own YouTube channels."""
    client = _require_youtube_client()
    source = YouTubeChannelSource(client)

    previous = get_previous_channel_snapshot(channel_id, Platform.YOUTUBE)
    current = source.get_channel_stats(channel_id)
    store_channel_snapshot(current)
    deltas = compute_deltas(previous, current)

    click.echo(
        f"Subscribers: {current.subscriber_count} ({deltas['subscriber_delta']:+d})"
    )
    click.echo(f"Total views: {current.view_count} ({deltas['view_delta']:+d})")
    click.echo(f"Video count: {current.video_count} ({deltas['video_delta']:+d})")

    videos = source.get_recent_video_performance(channel_id)
    for video, flag in flag_video_performance(videos):
        click.echo(f"[{flag:>14}] {video.view_count:>10d} views  {video.title}")


@cli.command("sponsors")
@click.option("--niche-id", required=True, type=int, help="Niche id from a previous `niches` run.")
def sponsors_command(niche_id: int) -> None:
    """Identify potential sponsor brands mentioned in a niche's videos."""
    candidates = scan_niche_for_sponsors(niche_id)

    if not candidates:
        click.echo("No sponsor candidates found for this niche.")
        return

    click.echo(f"{'Brand':<24}{'Mentions':>10}  Example")
    for brand, count, example in candidates:
        click.echo(f"{brand:<24}{count:>10d}  {example.video_url}")


if __name__ == "__main__":
    cli()
