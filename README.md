# content-radar

A small pipeline to help run a YouTube/TikTok/Instagram content operation:
finding rising niches, monitoring your own channels, and scouting sponsors.

## Modules

### 1. Niche trend radar (`niche_radar.py`)
Default mode requires **no manual keywords**: it auto-discovers currently
trending "breakout" channels. It pulls YouTube's currently-trending videos,
dedupes their channels, and flags channels that are both relatively new and
whose lifetime view count is dramatically higher than their subscriber count
(`view_to_sub_ratio = view_count / subscriber_count`) — a strong signal that a
niche is suddenly taking off. Results are ranked by that ratio and stored in
SQLite (`breakout_channels` table) under a new niche row
(`auto-discovery:<region>:<date>`).

CLI flags for discovery mode (all optional):
- `--region` (default `US`) — YouTube region code for trending videos.
- `--max-age-days` (default `365`) — max channel age to qualify as "new".
- `--min-ratio` (default `5.0`) — minimum view-to-subscriber ratio to qualify
  as a breakout.
- `--discover` / `--no-discover` — force discovery mode on/off explicitly.
  Discovery runs automatically whenever `--keywords` is omitted.

A secondary, targeted **keyword-search mode** still exists for when you want
to look at a specific topic instead of auto-discovery: pass `--keywords
"ai coding,productivity"` (with optional `--days`, default 7) to search
recent YouTube videos matching your seed keywords, pull their stats, and rank
them by a "heat score" (views per day since publication). Results are stored
as a niche snapshot (`niche_snapshots` table), same as before.

**YouTube-only.** TikTok's and Instagram's official public APIs do not expose
discovery data for arbitrary third-party content, so trend discovery across
those platforms isn't currently possible without scraping (out of scope here).

### 2. Own-channel monitoring (`channel_monitor.py`)
Tracks your own channel(s): subscriber/view/video counts, deltas vs. the
previous snapshot, and per-video over/under-performance vs. your channel
average. Comment fetching is wired up (`YouTubeClient.get_comments`) and the
`video_comments` table has a `sentiment` column ready for scoring, but
sentiment analysis itself is not yet implemented (TODO).

Built around a `Platform` enum and a `ChannelSource` interface so more
platforms can be added later:
- `YouTubeChannelSource` — fully implemented via the YouTube Data API.
- `TikTokChannelSource` / `InstagramChannelSource` — stubs that raise
  `NotImplementedError`. TikTok and Instagram *do* offer official
  Business/Creator APIs for reading your own account's insights (unlike
  third-party discovery), but this project doesn't have credentials for them
  yet. See the docstrings in `channel_monitor.py` for where to plug them in.

### 3. Sponsor/advertiser research (`sponsor_finder.py`)
Given a niche id from module 1, scans the stored video titles for that niche
for brand mentions using two heuristics:
- Exact matches against a starter list of ~15 well-known sponsor brands
  (`data/brand_seed_list.json`).
- A regex for "sponsored by X" / "thanks to X for sponsoring" phrasing, which
  can surface brands not in the seed list.

Aggregates mention counts per brand and stores them as sponsor candidates
(brand name, frequency, example video link).

## Setup

```bash
uv sync
cp .env.example .env
# edit .env and add your YouTube Data API v3 key: YOUTUBE_API_KEY=...
uv run content-radar init-db
```

## Usage

```bash
# Module 1: auto-discover breakout niches/channels (default mode, no keywords needed)
uv run content-radar niches --discover --region US

# Module 1 (targeted mode): find rising videos for specific seed keywords
uv run content-radar niches --keywords "ai coding,productivity" --days 7

# Module 2: monitor your own YouTube channel
uv run content-radar monitor --channel-id UCxxxxxxxxxxxxxxxxxxxxxx

# Module 3: find sponsor candidates for a niche discovered in module 1
uv run content-radar sponsors --niche-id 1
```

## Current limitations

- **TikTok / Instagram**: only the *own-account* monitoring interface exists,
  and only as a stub (`TikTokChannelSource`, `InstagramChannelSource`) —
  there are no API keys configured yet and no discovery/niche-radar support
  for these platforms at all (their public APIs don't support third-party
  content discovery).
- **Sentiment analysis**: the `video_comments.sentiment` column exists but is
  not populated by any code yet.
- **Sponsor detection** is heuristic (keyword list + regex), not a
  full NLP/NER pipeline — expect some false positives/negatives, especially
  from the "sponsored by X" regex on unusual phrasing.

## Development

```bash
uv run pytest
```

Tests mock the YouTube client — no live API calls are made during testing.
