"""SP recent form loader using pybaseball.pitching_stats_range() with caching.

Provides 30-day rolling ERA window for starting pitchers. Each call fetches
FanGraphs pitcher stats for a specific date range and caches to Parquet.

Per CONTEXT.md locked decision: SP recent form uses pitching_stats_range()
for a 30-day ERA window, not season-level ERA.
"""

import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from pybaseball import pitching_stats_range as pybaseball_pitching_stats_range
from src.data.cache import is_cached, save_to_cache, read_cached

logger = logging.getLogger(__name__)
RATE_LIMIT_DELAY = 2.0  # seconds between FanGraphs requests


def fetch_sp_recent_form(game_date: str, season: int) -> pd.DataFrame:
    """Fetch 30-day rolling pitcher stats ending the day before game_date.

    Temporal safety: the window is [game_date - 31 days, game_date - 1 day],
    so the game day itself is never included.

    Cache key: sp_form_{game_date} (one entry per game date, shared across
    all games on that date).
    Parquet path: pybaseball/sp_form_{game_date}.parquet

    Args:
        game_date: Game date in YYYY-MM-DD format.
        season: Season year (used for clamping start_dt to season opening).

    Returns:
        DataFrame of pitcher stats for the 30-day window. May be empty
        if the date range is too early in the season or fetch fails.
    """
    key = f"sp_form_{game_date}"
    parquet_path = f"pybaseball/sp_form_{game_date}.parquet"

    if is_cached(key):
        return read_cached(key)

    # Compute window: [game_date - 31 days, game_date - 1 day]
    game_dt = datetime.strptime(game_date, "%Y-%m-%d")
    end_dt = (game_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    start_dt = (game_dt - timedelta(days=31)).strftime("%Y-%m-%d")

    # Clamp start_dt to approximate season opening day
    season_earliest = f"{season}-03-20"
    if start_dt < season_earliest:
        start_dt = season_earliest

    try:
        result = pybaseball_pitching_stats_range(start_dt, end_dt)
        # Add game_date column for join purposes
        result["game_date"] = game_date
    except Exception as e:
        logger.error(f"Failed to fetch SP recent form for {game_date}: {e}")
        result = pd.DataFrame()

    # Always cache, even empty DataFrames, to avoid re-hitting API on reruns
    save_to_cache(result, key, parquet_path, season)
    return result


def fetch_sp_recent_form_bulk(
    game_dates: list[str], season: int
) -> dict[str, pd.DataFrame]:
    """Batch fetch 30-day pitcher stats for all unique game dates in a season.

    Deduplicates dates first (many games share the same date). Checks cache
    for each date and only calls pybaseball for uncached dates.

    Args:
        game_dates: List of game dates in YYYY-MM-DD format.
        season: Season year.

    Returns:
        Dict mapping game_date -> DataFrame of pitcher stats for that
        30-day window.
    """
    unique_dates = sorted(set(game_dates))
    results: dict[str, pd.DataFrame] = {}

    # Separate cached from uncached
    uncached_dates = []
    for date in unique_dates:
        key = f"sp_form_{date}"
        if is_cached(key):
            results[date] = read_cached(key)
        else:
            uncached_dates.append(date)

    total_uncached = len(uncached_dates)
    for i, date in enumerate(uncached_dates, 1):
        results[date] = fetch_sp_recent_form(date, season)
        logger.info(f"Fetched SP form for {date} ({i}/{total_uncached})")
        if i < total_uncached:
            time.sleep(RATE_LIMIT_DELAY)

    return results
