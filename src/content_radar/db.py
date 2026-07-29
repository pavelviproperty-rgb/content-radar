"""SQLite schema and connection helper for content-radar.

All persistent state lives in a single SQLite database file (default:
``data/content_radar.db``). Call :func:`init_db` once (or via the
``content-radar init-db`` CLI command) to create the schema.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "content_radar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS niches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS niche_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche_id INTEGER NOT NULL REFERENCES niches(id),
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    channel_title TEXT NOT NULL,
    view_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS own_channels (
    channel_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    label TEXT,
    PRIMARY KEY (channel_id, platform)
);

CREATE TABLE IF NOT EXISTS channel_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    subscriber_count INTEGER NOT NULL DEFAULT 0,
    view_count INTEGER NOT NULL DEFAULT 0,
    video_count INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS video_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    text TEXT NOT NULL,
    like_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT NOT NULL,
    sentiment REAL
);

CREATE TABLE IF NOT EXISTS breakout_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche_id INTEGER NOT NULL REFERENCES niches(id),
    channel_id TEXT NOT NULL,
    channel_title TEXT NOT NULL,
    channel_age_days REAL NOT NULL,
    subscriber_count INTEGER NOT NULL DEFAULT 0,
    view_count INTEGER NOT NULL DEFAULT 0,
    view_to_sub_ratio REAL NOT NULL,
    example_video_id TEXT,
    example_video_title TEXT,
    category_id TEXT,
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sponsor_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche_id INTEGER NOT NULL REFERENCES niches(id),
    brand_name TEXT NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 0,
    example_video_id TEXT,
    example_url TEXT,
    detected_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection, creating the parent directory if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
