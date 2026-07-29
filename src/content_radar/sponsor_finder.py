"""Module 3: sponsor/advertiser research.

Scans stored video titles/descriptions for a given niche and flags
brand-like mentions using two heuristics:

1. Exact (case-insensitive) matches against a seed list of known
   sponsor brands (``data/brand_seed_list.json``).
2. A regex for common "sponsored by X" / "thanks to X for sponsoring"
   phrasing, which can surface brands not in the seed list.

This is a lightweight data-aggregation + NLP-heuristic feature, not a
fully automated sponsor outreach pipeline.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from content_radar.db import get_connection

DEFAULT_BRAND_SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "brand_seed_list.json"

# Matches "sponsored by NordVPN", "thanks to Squarespace for sponsoring",
# "brought to you by Audible", etc. Captures the brand name (a short run
# of capitalized/alphanumeric words) following the trigger phrase.
SPONSOR_PHRASE_RE = re.compile(
    r"""
    (?i:
        sponsored\ by |
        thanks\ to |
        brought\ to\ you\ by |
        thank\ you\ to
    )
    \s+
    (?P<brand>[A-Z][A-Za-z0-9&+.\-]*(?:\s+[A-Z][A-Za-z0-9&+.\-]*){0,2})
    """,
    re.VERBOSE,
)


def load_brand_seed_list(path: Path | str = DEFAULT_BRAND_SEED_PATH) -> list[str]:
    with open(path) as f:
        return json.load(f)


@dataclass
class SponsorMention:
    brand_name: str
    video_id: str
    video_url: str


def find_brand_mentions(
    text: str,
    video_id: str,
    brand_seed_list: list[str],
) -> list[SponsorMention]:
    """Find brand mentions in a single piece of text (title + description)."""
    if not text:
        return []

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    mentions: list[SponsorMention] = []
    lower_text = text.lower()

    for brand in brand_seed_list:
        if brand.lower() in lower_text:
            mentions.append(SponsorMention(brand_name=brand, video_id=video_id, video_url=video_url))

    for match in SPONSOR_PHRASE_RE.finditer(text):
        brand = match.group("brand").strip()
        # Skip if this brand is already covered by an exact seed-list hit
        # (case-insensitive) to avoid double counting the same mention.
        if not any(m.brand_name.lower() == brand.lower() for m in mentions):
            mentions.append(SponsorMention(brand_name=brand, video_id=video_id, video_url=video_url))

    return mentions


def aggregate_sponsor_candidates(
    mentions: list[SponsorMention],
) -> list[tuple[str, int, SponsorMention]]:
    """Aggregate mentions by brand, returning (brand, count, example_mention) sorted by count desc."""
    grouped: dict[str, list[SponsorMention]] = defaultdict(list)
    for mention in mentions:
        grouped[mention.brand_name].append(mention)

    aggregated = [
        (brand, len(group), group[0]) for brand, group in grouped.items()
    ]
    aggregated.sort(key=lambda row: row[1], reverse=True)
    return aggregated


def scan_niche_for_sponsors(
    niche_id: int,
    db_path=None,
    brand_seed_list: list[str] | None = None,
) -> list[tuple[str, int, SponsorMention]]:
    """Scan all stored niche_snapshots for a niche and aggregate sponsor candidates."""
    brand_seed_list = brand_seed_list if brand_seed_list is not None else load_brand_seed_list()
    conn = get_connection(db_path) if db_path else get_connection()
    try:
        rows = conn.execute(
            "SELECT video_id, title FROM niche_snapshots WHERE niche_id = ?",
            (niche_id,),
        ).fetchall()

        all_mentions: list[SponsorMention] = []
        for row in rows:
            all_mentions.extend(
                find_brand_mentions(row["title"], row["video_id"], brand_seed_list)
            )

        aggregated = aggregate_sponsor_candidates(all_mentions)

        now_iso = datetime.now(timezone.utc).isoformat()
        for brand, count, example in aggregated:
            conn.execute(
                """
                INSERT INTO sponsor_candidates (
                    niche_id, brand_name, mention_count, example_video_id, example_url, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (niche_id, brand, count, example.video_id, example.video_url, now_iso),
            )
        conn.commit()
        return aggregated
    finally:
        conn.close()
