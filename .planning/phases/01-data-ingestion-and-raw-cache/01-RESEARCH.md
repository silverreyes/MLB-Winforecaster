# Phase 1: Data Ingestion and Raw Cache - Research

**Researched:** 2026-03-28
**Domain:** Python data ingestion (pybaseball, MLB Stats API, Kalshi API, Parquet caching)
**Confidence:** HIGH

## Summary

Phase 1 requires building five data ingestion pipelines: MLB game schedules with starting pitchers (MLB Stats API), team batting stats (pybaseball/FanGraphs), starting pitcher stats (pybaseball/FanGraphs), Statcast metrics (pybaseball/Baseball Savant), and Kalshi settled game-winner markets (Kalshi REST API). All data must be cached as local Parquet files with a JSON manifest to prevent re-scraping.

The Python ecosystem for this is mature and well-documented. `pybaseball` (v2.2.7) is the standard library for FanGraphs and Baseball Savant data, providing team-level and individual-level stat functions with built-in rate limiting and query chunking. `MLB-StatsAPI` (v1.9.0) wraps the official MLB Stats API with schedule and probable pitcher support. The Kalshi API is REST-based with cursor pagination and requires awareness of the new historical/live data partition (added February 2026). A critical constraint is pinning pandas to 2.2.3 to avoid pybaseball incompatibility with pandas 3.0's PyArrow-backed string defaults.

**Primary recommendation:** Use pybaseball 2.2.7 for all FanGraphs/Savant data, MLB-StatsAPI 1.9.0 for schedules/pitchers, raw requests for Kalshi API, pandas 2.2.3 with pyarrow for Parquet I/O. Build a thin loader module per data source in `src/data/` with cache-check-then-fetch logic keyed on the JSON manifest.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Notebooks + `src/data/` Python modules: each data source gets a loader in `src/data/`, notebooks call the loaders
- One notebook per data source: MLB Stats API, pybaseball team batting, pybaseball SP stats, Statcast, Kalshi
- `src/data/` lives at repo root (standard Python layout -- Phase 2's FeatureBuilder can import from it directly)
- `requirements.txt` at repo root for all dependencies -- no `!pip install` cells inside notebooks
- `data/` at repo root, added to `.gitignore` -- never committed
- Organized by source: `data/raw/mlb_api/`, `data/raw/pybaseball/`, `data/raw/statcast/`, `data/raw/kalshi/`
- One Parquet file per season per category: `team_batting_2015.parquet`, `sp_stats_2021.parquet`, etc.
- JSON manifest at `data/raw/cache_manifest.json` -- tracks each file with: season, fetch date, row count
- Ingest 2020 like any other season -- do NOT exclude from cache
- Add `is_shortened_season=True` (and `season_games=60`) column to ALL 2020 records
- Kalshi storage: parsed game-level table with columns `date`, `home_team`, `away_team`, `kalshi_yes_price`, `kalshi_no_price`, `result`, `market_ticker`
- Team name normalization: `src/data/team_mappings.py` maps Kalshi ticker abbreviations to canonical team names
- Kalshi auth: optional -- if `KALSHI_API_KEY` env var is set, use it; otherwise fall back to public unauthenticated API

### Claude's Discretion
- Exact pybaseball function calls and parameters for each stat category
- Pagination and rate-limiting strategy for MLB Stats API
- Parquet compression settings and schema types
- Coverage validation logic inside each notebook (what constitutes "complete" for a season)
- Cache manifest update logic

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Fetch MLB game schedules and confirmed starting pitcher assignments from MLB Stats API | MLB-StatsAPI `schedule()` returns `home_probable_pitcher` and `away_probable_pitcher` fields per game; v1.9.0 confirmed working |
| DATA-02 | Ingest historical team batting statistics (wOBA, OPS, OBP, SLG) from pybaseball/FanGraphs | `team_batting(start_season, end_season, ind=1)` returns all FanGraphs team-level batting columns including wOBA, OPS, OBP, SLG |
| DATA-03 | Ingest historical starting pitcher statistics (FIP, xFIP, K%, BB%, WHIP) from pybaseball/FanGraphs | `pitching_stats(start_season, end_season, qual, ind=1)` returns 334 FanGraphs columns including FIP, xFIP, K%, BB%, WHIP, SIERA |
| DATA-04 | Ingest Statcast metrics (xwOBA, pitch velocity, whiff rate) from pybaseball/Baseball Savant | `statcast_pitcher_expected_stats(year)` and `statcast_batter_expected_stats(year)` return xwOBA; `statcast_pitcher_arsenal_stats(year)` returns whiff%; pitch velocity via `statcast_pitcher_pitch_arsenal(year, arsenal_type="average_speed")` |
| DATA-05 | All raw data cached locally as Parquet files to prevent repeated scraping | pandas `to_parquet()` with snappy compression; JSON manifest tracks fetch date and row count per file; notebooks check manifest before fetching |
| DATA-06 | Fetch resolved Kalshi MLB game-winner market prices (partial, 2025 onward) | Kalshi REST API `GET /markets` (status=settled, series_ticker filter) and `GET /historical/markets` for archived data; cursor-based pagination; 20 req/sec rate limit on Basic tier |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pybaseball | 2.2.7 | FanGraphs batting/pitching stats, Statcast/Savant metrics | De facto Python library for baseball data; wraps FanGraphs and Baseball Savant with built-in rate limiting and query chunking |
| MLB-StatsAPI | 1.9.0 | MLB game schedules, probable pitchers, game results | Most popular Python wrapper for official MLB Stats API; 768 stars, actively maintained (last release April 2025) |
| pandas | 2.2.3 | DataFrame operations, Parquet I/O | HARD PIN: pybaseball uses object-dtype DataFrames; pandas 3.0 (Jan 2026) defaults to PyArrow-backed strings that break compatibility |
| pyarrow | >=10.0 | Parquet read/write engine, required by pybaseball | Required dependency of pybaseball (>=1.0.1); also needed for pandas Parquet I/O |
| requests | >=2.18.1 | HTTP client for Kalshi API | Already a pybaseball dependency; used directly for Kalshi REST API calls |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | >=1.13.0 | Numeric operations (pybaseball dependency) | Comes with pybaseball; no separate install needed |
| beautifulsoup4 | >=4.4.0 | HTML parsing (pybaseball dependency) | Comes with pybaseball; handles FanGraphs/Savant scraping |
| lxml | >=4.2.1 | Fast XML/HTML parser (pybaseball dependency) | Comes with pybaseball |
| tqdm | >=4.50.0 | Progress bars (pybaseball dependency) | Comes with pybaseball; useful in notebook progress display |
| jupyter | latest | Notebook interface | User-facing interaction layer per project spec |
| python-dotenv | latest | Load KALSHI_API_KEY from .env file | Only if Kalshi auth is needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pybaseball 2.2.7 | pybaseballstats 0.4.7 | More recently maintained fork (Feb 2026), but less community adoption; pybaseball 2.2.7 is proven stable for our use case |
| MLB-StatsAPI | python-mlb-statsapi | Pydantic models with type safety, but MLB-StatsAPI has simpler API and wider adoption |
| Raw requests for Kalshi | kalshi-python SDK | SDK exists but is overkill for simple GET requests on public endpoints |
| pandas 2.2.3 | pandas 2.3.3 or 3.0.1 | 2.3.x might work but untested with pybaseball; 3.0 confirmed incompatible due to PyArrow string defaults |

**Installation:**
```bash
pip install pybaseball==2.2.7 MLB-StatsAPI==1.9.0 "pandas>=2.2.3,<2.3" pyarrow>=10.0 requests jupyter python-dotenv
```

**Version verification:** pybaseball 2.2.7 released Sep 8, 2024 (latest in 2.x line). MLB-StatsAPI 1.9.0 released Apr 4, 2025. pandas 2.2.3 released Sep 20, 2024 (last 2.2.x release -- no 2.2.4 exists). pyarrow latest is 18.x but any >=10.0 works.

## Architecture Patterns

### Recommended Project Structure
```
MLB-WinForecaster/
├── requirements.txt              # All dependencies pinned
├── .gitignore                    # data/ excluded
├── .env                          # KALSHI_API_KEY (optional, gitignored)
├── src/
│   ├── __init__.py
│   └── data/
│       ├── __init__.py
│       ├── cache.py              # Shared cache manifest logic
│       ├── team_mappings.py      # Canonical team name mappings
│       ├── mlb_schedule.py       # MLB Stats API loader
│       ├── team_batting.py       # FanGraphs team batting loader
│       ├── sp_stats.py           # FanGraphs SP pitching stats loader
│       ├── statcast.py           # Baseball Savant Statcast loader
│       └── kalshi.py             # Kalshi settled markets loader
├── notebooks/
│   ├── 01_mlb_schedule.ipynb
│   ├── 02_team_batting.ipynb
│   ├── 03_sp_stats.ipynb
│   ├── 04_statcast.ipynb
│   └── 05_kalshi.ipynb
├── data/
│   └── raw/
│       ├── cache_manifest.json
│       ├── mlb_api/              # schedule_2015.parquet, etc.
│       ├── pybaseball/           # team_batting_2015.parquet, sp_stats_2015.parquet
│       ├── statcast/             # statcast_pitcher_expected_2015.parquet, etc.
│       └── kalshi/               # kalshi_game_winners.parquet
└── tests/
    ├── __init__.py
    └── test_cache.py
```

### Pattern 1: Cache-Check-Then-Fetch Loader
**What:** Each loader module checks the JSON manifest before making any API/scraping call. If the file exists and the manifest entry is valid, return the cached DataFrame. Otherwise, fetch fresh data, save as Parquet, and update the manifest.
**When to use:** Every data source loader.
**Example:**
```python
# src/data/cache.py
import json
import os
from pathlib import Path
from datetime import datetime

CACHE_DIR = Path("data/raw")
MANIFEST_PATH = CACHE_DIR / "cache_manifest.json"

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {}

def save_manifest(manifest: dict):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

def is_cached(key: str) -> bool:
    manifest = load_manifest()
    if key not in manifest:
        return False
    filepath = CACHE_DIR / manifest[key]["path"]
    return filepath.exists()

def update_manifest(key: str, path: str, season: int, row_count: int):
    manifest = load_manifest()
    manifest[key] = {
        "path": path,
        "season": season,
        "fetch_date": datetime.now().isoformat(),
        "row_count": row_count,
    }
    save_manifest(manifest)
```

### Pattern 2: Season-Loop Ingestion
**What:** Each loader takes a season range (2015-2024) and loops per-season, writing one Parquet file per season. This keeps files small, re-fetchable individually, and easy to validate.
**When to use:** All pybaseball and MLB Stats API loaders.
**Example:**
```python
# src/data/team_batting.py
import pandas as pd
from pybaseball import team_batting
from src.data.cache import is_cached, update_manifest, CACHE_DIR

def fetch_team_batting(season: int) -> pd.DataFrame:
    key = f"team_batting_{season}"
    parquet_path = f"pybaseball/team_batting_{season}.parquet"

    if is_cached(key):
        return pd.read_parquet(CACHE_DIR / parquet_path)

    df = team_batting(season)

    # Add 2020 short-season flag
    df["is_shortened_season"] = (season == 2020)
    df["season_games"] = 60 if season == 2020 else 162

    filepath = CACHE_DIR / parquet_path
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(filepath, compression="snappy")

    update_manifest(key, parquet_path, season, len(df))
    return df
```

### Pattern 3: Kalshi Dual-Endpoint Fetcher
**What:** The Kalshi ingestion must query BOTH `GET /markets` (status=settled, for recent markets) AND `GET /historical/markets` (for archived markets) to get full coverage. The historical endpoint was added Feb 2026 and markets older than the cutoff are ONLY available there.
**When to use:** Kalshi data source only.
**Example:**
```python
# Check the cutoff first
cutoff_resp = requests.get(f"{BASE_URL}/historical/cutoff")
cutoff_ts = cutoff_resp.json()["market_settled_ts"]

# Fetch from both endpoints
recent_markets = paginate_all(f"{BASE_URL}/markets", params={"status": "settled", "series_ticker": "KXMLB..."})
historical_markets = paginate_all(f"{BASE_URL}/historical/markets", params={})
# Note: historical endpoint does NOT support series_ticker filter -- must filter client-side
```

### Anti-Patterns to Avoid
- **Using pybaseball's built-in cache.enable()**: It stores in its own format at its own location. We need Parquet files in `data/raw/` per the project spec. Use our own caching layer instead.
- **Fetching all 10 seasons in a single pybaseball call**: `team_batting(2015, 2024)` returns all seasons in one DataFrame but makes one big scrape. Loop per-season for granular caching and error recovery.
- **Hardcoding team abbreviations**: Team abbreviations differ between sources (e.g., pybaseball uses "WSN"/"WSH", Kalshi uses different abbreviations, MLB API uses full names). Always normalize through `team_mappings.py`.
- **Ignoring the Kalshi historical/live partition**: Since Feb 2026, settled markets older than the cutoff are ONLY available via `GET /historical/markets`. Querying only `GET /markets` will miss data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FanGraphs scraping | Custom BeautifulSoup scraper for FanGraphs | `pybaseball.team_batting()`, `pitching_stats()` | FanGraphs changes HTML structure frequently; pybaseball handles this with maintained selectors |
| Baseball Savant data | Custom Statcast CSV downloader | `pybaseball.statcast_pitcher_expected_stats()`, `statcast_batter_expected_stats()` | Savant has 30K row limits and rate limits; pybaseball auto-chunks and retries |
| MLB schedule parsing | Custom REST calls to statsapi.mlb.com | `statsapi.schedule()` from MLB-StatsAPI | The raw API response is deeply nested JSON; the wrapper flattens it to clean dicts |
| Parquet I/O | Custom serialization | `pandas.DataFrame.to_parquet()` / `pd.read_parquet()` | Handles schema evolution, compression, and type preservation automatically |
| Player ID cross-referencing | Manual CSV lookup tables | `pybaseball.playerid_lookup()` / `playerid_reverse_lookup()` | Chadwick Bureau database covers MLBAM, FanGraphs, BBRef, and Retrosheet IDs in one call |

**Key insight:** pybaseball is doing the hard work of scraping three different web sources (FanGraphs, Baseball Savant, Baseball Reference) with different HTML structures and rate limits. Building custom scrapers would be fragile and time-consuming.

## Common Pitfalls

### Pitfall 1: pandas 3.0 PyArrow String Incompatibility
**What goes wrong:** Installing pybaseball without pinning pandas installs pandas 3.0.1 (current latest), which defaults to PyArrow-backed string dtypes. pybaseball returns object-dtype DataFrames that break with these defaults.
**Why it happens:** pandas 3.0 (released Jan 2026) changed the default string inference behavior. pybaseball 2.2.7 (released Sep 2024) was built for pandas 2.x.
**How to avoid:** Pin `pandas>=2.2.3,<2.3` in requirements.txt. This is the FIRST thing to set up.
**Warning signs:** TypeError or unexpected dtype errors when calling pybaseball functions; string columns showing ArrowDtype instead of object.

### Pitfall 2: Kalshi Historical vs Live Data Partition
**What goes wrong:** Only querying `GET /markets?status=settled` returns an incomplete dataset. Markets that settled more than ~1 year ago are moved to the historical tier and are only available via `GET /historical/markets`.
**Why it happens:** Kalshi introduced the historical/live partition in February 2026 with a rolling ~1-year cutoff.
**How to avoid:** First call `GET /historical/cutoff` to get the `market_settled_ts` boundary. Then query BOTH `GET /historical/markets` (for pre-cutoff) and `GET /markets?status=settled` (for post-cutoff). Combine results.
**Warning signs:** Fewer Kalshi markets returned than expected; missing early-season 2025 games.

### Pitfall 3: Kalshi Historical Endpoint Limited Filtering
**What goes wrong:** Trying to filter `GET /historical/markets` by `series_ticker` or `status` fails silently or returns nothing -- the historical endpoint only supports `limit`, `cursor`, `tickers`, `event_ticker`, and `mve_filter`.
**Why it happens:** The historical endpoint has a deliberately simpler parameter set than the live `GET /markets` endpoint.
**How to avoid:** Fetch all historical markets via pagination, then filter client-side by ticker prefix (e.g., "KXMLB") to isolate MLB game-winner markets.
**Warning signs:** Empty response when passing `series_ticker` to the historical endpoint.

### Pitfall 4: FanGraphs/Savant Rate Limiting and Timeouts
**What goes wrong:** Rapid successive calls to pybaseball functions result in HTTP 429 errors or query timeouts from Baseball Savant.
**Why it happens:** Baseball Savant enforces a 30,000-row limit per request and rate limits scraping. FanGraphs also rate limits.
**How to avoid:** pybaseball handles chunking automatically for `statcast()` calls. For FanGraphs functions (`team_batting`, `pitching_stats`), call per-season rather than multi-season ranges. Add a 2-3 second sleep between seasons if experiencing rate limits.
**Warning signs:** "Error: Query Timeout" from Baseball Savant; HTTP 429 responses.

### Pitfall 5: Statcast Data Not Available Before 2015
**What goes wrong:** Requesting Statcast data for 2014 or earlier returns empty DataFrames or errors. Launch angle data specifically starts in 2015.
**Why it happens:** Statcast hardware was deployed to all 30 MLB parks in 2015. Some data exists from 2008 but is incomplete and unreliable.
**How to avoid:** Only request Statcast data for 2015-2024 (matching the backtest window). Validate that returned DataFrames are non-empty.
**Warning signs:** Empty DataFrames for early years; missing xwOBA columns.

### Pitfall 6: Team Abbreviation Inconsistency Across Sources
**What goes wrong:** Joining data from different sources fails because team abbreviations don't match. For example: Washington Nationals may appear as "WSN" (pybaseball), "WSH" (other sources), "Washington Nationals" (MLB API), or a completely different abbreviation in Kalshi tickers.
**Why it happens:** Each data source uses its own naming convention. MLB API returns full team names while pybaseball uses Baseball Reference abbreviations.
**How to avoid:** Build `team_mappings.py` as the FIRST artifact in this phase. Map every source's naming convention to a single canonical abbreviation. All loaders normalize team names through this mapping before saving to Parquet.
**Warning signs:** NaN values after merge operations on team columns; mismatched row counts in joins.

### Pitfall 7: 2020 Short Season Data Anomalies
**What goes wrong:** Raw 2020 stats look abnormal (lower counting stats, smaller sample sizes) but there's no flag to identify them as 60-game season data downstream.
**Why it happens:** The 2020 MLB season was shortened to 60 games due to COVID-19, but raw stats don't carry this context.
**How to avoid:** Per user decision, add `is_shortened_season=True` and `season_games=60` columns to ALL 2020 records at ingestion time.
**Warning signs:** Phase 2/3 treating 2020 counting stats equivalently to full-season stats.

### Pitfall 8: Kalshi Dollar-String Price Fields
**What goes wrong:** Parsing Kalshi prices as integers or expecting cent-denominated values fails because the API now returns dollar-denominated string fields (e.g., "0.65" not 65).
**Why it happens:** Kalshi removed integer cent fields (Jan 2026) and integer count fields (Mar 2026). All prices are now fixed-point dollar strings with up to 6 decimal places.
**How to avoid:** Parse `yes_bid_dollars`, `no_bid_dollars`, `last_price_dollars`, and `settlement_value_dollars` as floats. Do NOT look for cent-denominated fields -- they no longer exist.
**Warning signs:** KeyError on fields like `yes_bid` or `last_price`; price values that look like 0.000065 instead of 0.65.

## Code Examples

Verified patterns from official sources:

### Fetching Team Batting Stats (DATA-02)
```python
# Source: pybaseball docs - team_batting.md
from pybaseball import team_batting

# Returns DataFrame with one row per team for the season
# Columns include: Team, G, PA, HR, R, RBI, SB, BB%, K%, ISO,
#                  BABIP, AVG, OBP, SLG, wOBA, wRC+, WAR, etc.
df = team_batting(2023)

# Multi-year with individual season rows
df = team_batting(2015, 2024, ind=1)
```

### Fetching Starting Pitcher Stats (DATA-03)
```python
# Source: pybaseball docs - pitching_stats.md
from pybaseball import pitching_stats

# Returns one row per pitcher per season
# 334 columns including: Name, Team, W, L, ERA, G, GS, IP,
#                        FIP, xFIP, SIERA, K%, BB%, WHIP, WAR, etc.
# qual=0 gets ALL pitchers (not just qualified)
df = pitching_stats(2023, qual=0)

# Filter to starters only: GS > 0 or check 'Role' column
starters = df[df["GS"] > 0]
```

### Fetching Statcast Expected Stats (DATA-04)
```python
# Source: pybaseball docs - statcast_pitcher.md, statcast_batter.md
from pybaseball import (
    statcast_pitcher_expected_stats,
    statcast_batter_expected_stats,
    statcast_pitcher_arsenal_stats,
    statcast_pitcher_pitch_arsenal,
)

# Pitcher expected stats: includes xwOBA, xBA, xSLG, xISO
pitcher_expected = statcast_pitcher_expected_stats(2023, minPA=50)

# Batter expected stats: includes xwOBA, xBA, xSLG
batter_expected = statcast_batter_expected_stats(2023, minPA=50)

# Pitcher arsenal stats: includes whiff_percent per pitch type
arsenal_stats = statcast_pitcher_arsenal_stats(2023, minPA=50)

# Pitcher pitch arsenal: average velocity per pitch type
pitch_speeds = statcast_pitcher_pitch_arsenal(2023, arsenal_type="average_speed")
```

### Fetching MLB Schedule with Starting Pitchers (DATA-01)
```python
# Source: MLB-StatsAPI wiki - Function: schedule
import statsapi

# Get all games for a date range
games = statsapi.schedule(
    start_date="04/01/2023",
    end_date="10/01/2023"
)

# Each game dict contains:
# game_id, game_date, home_name, away_name,
# home_probable_pitcher, away_probable_pitcher,
# home_score, away_score, winning_team, losing_team, status, etc.

for game in games:
    print(f"{game['game_date']}: {game['away_name']} @ {game['home_name']}")
    print(f"  SP: {game['away_probable_pitcher']} vs {game['home_probable_pitcher']}")
```

### Fetching Kalshi Settled Markets (DATA-06)
```python
# Source: Kalshi API docs - GET /markets, GET /historical/markets
# Pattern derived from existing check_kalshi_mlb.py
import requests
import time

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

def get_historical_cutoff():
    """Get the timestamp boundary between live and historical data."""
    resp = requests.get(f"{BASE_URL}/historical/cutoff", timeout=15)
    resp.raise_for_status()
    return resp.json()["market_settled_ts"]

def paginate_markets(endpoint: str, params: dict, rate_limit_delay: float = 0.1):
    """Paginate through all results from a Kalshi endpoint."""
    all_markets = []
    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        params["limit"] = 1000  # Max allowed
        resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        markets = data.get("markets", [])
        if not markets:
            break
        all_markets.extend(markets)
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(rate_limit_delay)  # Stay under 20 req/sec Basic tier limit
    return all_markets

# Fetch from BOTH endpoints
recent = paginate_markets("markets", {"status": "settled", "series_ticker": "KXMLB"})
historical = paginate_markets("historical/markets", {})
# Filter historical client-side (no series_ticker filter on historical endpoint)
historical_mlb = [m for m in historical if "KXMLB" in m.get("ticker", "").upper()
                  or "MLB" in (m.get("title", "") + m.get("subtitle", "")).upper()]

# Parse price fields as dollar strings
for m in recent + historical_mlb:
    settlement = float(m.get("settlement_value_dollars", "0"))
    last_price = float(m.get("last_price_dollars", "0"))
```

### Writing Parquet with Snappy Compression (DATA-05)
```python
# Source: pandas + pyarrow documentation
import pandas as pd
from pathlib import Path

def save_to_cache(df: pd.DataFrame, path: str):
    """Save DataFrame as Parquet with snappy compression."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(filepath, engine="pyarrow", compression="snappy", index=False)

def load_from_cache(path: str) -> pd.DataFrame:
    """Load DataFrame from cached Parquet file."""
    return pd.read_parquet(path, engine="pyarrow")
```

### Player ID Cross-Reference
```python
# Source: pybaseball docs - playerid_lookup.md
from pybaseball import playerid_lookup, playerid_reverse_lookup

# Look up by name -- returns key_mlbam, key_fangraphs, key_bbref, key_retro
player = playerid_lookup("Ohtani", "Shohei")
mlbam_id = player.iloc[0]["key_mlbam"]

# Reverse lookup from MLBAM ID
info = playerid_reverse_lookup([660271], key_type="mlbam")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `batting_stats_bref()` from Baseball Reference | `batting_stats()` from FanGraphs | pybaseball 2.x | FanGraphs provides 334 columns including advanced metrics (wOBA, wRC+, SIERA); BBRef is more limited |
| Kalshi `GET /markets` for all data | Split: `GET /markets` (recent) + `GET /historical/markets` (archived) | Feb 19, 2026 | Must query BOTH endpoints for complete coverage; historical cutoff is ~1 year rolling |
| Kalshi integer cent price fields (`yes_bid`, `last_price`) | Dollar string fields (`yes_bid_dollars`, `last_price_dollars`) | Jan 6, 2026 | Old integer fields removed; all prices now fixed-point dollar strings |
| pandas object-dtype strings | pandas 3.0 PyArrow-backed strings by default | Jan 21, 2026 | pybaseball incompatible with pandas 3.0; must pin to 2.2.x |
| Manual Statcast CSV downloads from Baseball Savant | `statcast_*_expected_stats()` functions | pybaseball 2.x | Automated scraping with rate limit handling built in |

**Deprecated/outdated:**
- Kalshi integer cent fields (`yes_bid`, `no_bid`, `last_price`, `tick_size`): removed Jan 2026
- Kalshi integer cost fields (`yes_total_cost`, `no_total_cost`): removed Mar 25, 2026
- Kalshi `category` field on Market response: removed Jan 5, 2026
- pandas 2.x `future.infer_string` opt-in: now the default in 3.0 (reason we must pin 2.2.x)

## Open Questions

1. **Exact columns returned by `statcast_pitcher_expected_stats()`**
   - What we know: Includes xwOBA, xBA, xSLG based on Baseball Savant leaderboard
   - What's unclear: Full column list; exact column names; whether whiff_percent is included or requires separate `statcast_pitcher_arsenal_stats()` call
   - Recommendation: During implementation, run a single test call (`statcast_pitcher_expected_stats(2023, minPA=50)`) and inspect `.columns`. Build the ingestion logic around actual returned schema.

2. **Kalshi historical cutoff timestamp precision**
   - What we know: Cutoff is ~1 year rolling; `GET /historical/cutoff` returns the boundary
   - What's unclear: Whether all 2025 MLB markets (settled Apr-Oct 2025) are now in the historical tier, or still split between live and historical
   - Recommendation: Call `GET /historical/cutoff` first, then decide whether to query one or both endpoints.

3. **pybaseball compatibility with pandas 2.2.3 specifically**
   - What we know: pybaseball requires `pandas>=1.0.3`; works with pandas 2.x; pandas 3.0 breaks it
   - What's unclear: Whether pandas 2.2.3 has any specific issues with pybaseball 2.2.7 (no known bugs, but untested together in our environment)
   - Recommendation: Set up requirements.txt with the pin and run a smoke test immediately.

4. **Team abbreviation mapping completeness**
   - What we know: Each source uses different conventions; need a canonical mapping
   - What's unclear: Full list of Kalshi MLB ticker abbreviations (only visible by querying actual market tickers)
   - Recommendation: Build initial mapping from known sources (pybaseball, MLB API), then extend with actual Kalshi tickers during implementation of the Kalshi loader.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest) |
| Config file | none -- see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | MLB schedule loader returns DataFrame with expected columns | unit (mock HTTP) | `pytest tests/test_mlb_schedule.py -x` | No -- Wave 0 |
| DATA-02 | Team batting loader returns DataFrame with wOBA, OPS, OBP, SLG columns | unit (mock pybaseball) | `pytest tests/test_team_batting.py -x` | No -- Wave 0 |
| DATA-03 | SP stats loader returns DataFrame with FIP, xFIP, K%, BB%, WHIP columns | unit (mock pybaseball) | `pytest tests/test_sp_stats.py -x` | No -- Wave 0 |
| DATA-04 | Statcast loader returns DataFrame with xwOBA column | unit (mock pybaseball) | `pytest tests/test_statcast.py -x` | No -- Wave 0 |
| DATA-05 | Cache saves Parquet and manifest; re-read returns identical DataFrame | unit | `pytest tests/test_cache.py -x` | No -- Wave 0 |
| DATA-06 | Kalshi loader returns DataFrame with required columns and valid prices | unit (mock HTTP) | `pytest tests/test_kalshi.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (fast fail on first error)
- **Per wave merge:** `pytest tests/ -v` (verbose full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` -- empty init
- [ ] `tests/test_cache.py` -- covers DATA-05 (manifest read/write, Parquet round-trip)
- [ ] `tests/test_team_batting.py` -- covers DATA-02 (column validation, 2020 flag)
- [ ] `tests/test_sp_stats.py` -- covers DATA-03 (column validation, starter filtering)
- [ ] `tests/test_statcast.py` -- covers DATA-04 (column validation)
- [ ] `tests/test_mlb_schedule.py` -- covers DATA-01 (probable pitcher fields)
- [ ] `tests/test_kalshi.py` -- covers DATA-06 (price parsing, team normalization)
- [ ] `pytest.ini` or `pyproject.toml` -- basic pytest configuration
- [ ] Framework install: `pip install pytest` (add to requirements.txt dev section)

## Sources

### Primary (HIGH confidence)
- [pybaseball GitHub - jldbc/pybaseball](https://github.com/jldbc/pybaseball) - README, function docs for team_batting, pitching_stats, statcast, statcast_pitcher, statcast_batter, playerid_lookup
- [pybaseball PyPI](https://pypi.org/project/pybaseball/) - version 2.2.7, release date Sep 2024, dependencies confirmed
- [MLB-StatsAPI GitHub Wiki - schedule function](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-schedule) - all parameters and return fields
- [MLB-StatsAPI PyPI](https://pypi.org/project/MLB-StatsAPI/) - version 1.9.0, release date Apr 2025
- [Kalshi API Docs - GET /markets](https://docs.kalshi.com/api-reference/market/get-markets) - query parameters, response schema, historical cutoff note
- [Kalshi API Docs - GET /historical/markets](https://docs.kalshi.com/api-reference/historical/get-historical-markets) - historical endpoint parameters, limited filtering
- [Kalshi API Changelog](https://docs.kalshi.com/changelog) - historical endpoints added Feb 19, 2026; price field removals Jan/Mar 2026
- [Kalshi Rate Limits](https://docs.kalshi.com/getting_started/rate_limits) - 20 reads/sec Basic tier, 30 Advanced, 100 Premier
- [pandas PyPI](https://pypi.org/project/pandas/) - version 3.0.1 current; 2.2.3 last in 2.2.x line (Sep 2024)

### Secondary (MEDIUM confidence)
- [pybaseball GitHub releases](https://github.com/jldbc/pybaseball/releases) - v2.2.7 release notes (Sep 2024), no 2025/2026 releases
- [pybaseball setup.py](https://github.com/jldbc/pybaseball/blob/master/setup.py) - confirmed dependencies including pandas>=1.0.3, pyarrow>=1.0.1
- [Kalshi API - Historical Cutoff Timestamps](https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps) - 1 year rolling lookback initial setting
- [Baseball Savant Expected Statistics Leaderboard](https://baseballsavant.mlb.com/leaderboard/expected_statistics) - confirms xwOBA, xBA, xSLG columns

### Tertiary (LOW confidence)
- [pybaseballstats 0.4.7 on PyPI](https://pypi.org/project/pybaseballstats/) - alternative fork, Feb 2026 release; not recommended for this project but noted as maintained alternative
- Kalshi MLB ticker format (KXMLB prefix) - confirmed via existing `check_kalshi_mlb.py` script but exact individual game ticker structure not documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages verified on PyPI with current versions and release dates; pandas pin rationale well-documented
- Architecture: HIGH - cache pattern is straightforward; all API/scraping patterns verified against official docs
- Pitfalls: HIGH - Kalshi API changes verified against official changelog with exact dates; pandas 3.0 incompatibility confirmed via release notes; pybaseball rate limiting documented in issues
- Statcast columns: MEDIUM - function signatures verified but exact column names need runtime confirmation
- Kalshi ticker structure: MEDIUM - KXMLB prefix confirmed by existing script but individual game ticker format undocumented

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (30 days -- stack is stable; Kalshi API may continue evolving)
