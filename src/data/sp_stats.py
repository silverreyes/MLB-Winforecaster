"""FanGraphs starting pitcher statistics loader with Parquet caching."""

import pandas as pd
from pybaseball import pitching_stats as pybaseball_pitching_stats
from src.data.cache import is_cached, save_to_cache, read_cached


def fetch_sp_stats(season: int, min_gs: int = 1) -> pd.DataFrame:
    """Fetch starting pitcher stats for a single season. Returns from cache if available.

    Filters to pitchers with GS >= min_gs (default 1 = any start).
    Columns include: Name, Team, W, L, ERA, GS, IP, FIP, xFIP, SIERA, K%, BB%, WHIP, WAR
    Plus: is_shortened_season, season_games, season

    Note: min_gs IS included in the cache key, so different min_gs values produce
    separate Parquet files. A call with min_gs=5 will NOT return stale data cached
    from a prior call with min_gs=1.

    Note: Team column uses FanGraphs canonical abbreviations as-is.
    """
    key = f"sp_stats_{season}_mings{min_gs}"
    parquet_path = f"pybaseball/sp_stats_{season}_mings{min_gs}.parquet"

    if is_cached(key):
        return read_cached(key)

    # qual=0 gets ALL pitchers (not just qualified); filter to starters after
    df = pybaseball_pitching_stats(season, qual=0)

    # Filter to starting pitchers only
    df = df[df["GS"] >= min_gs].copy()

    # Add 2020 short-season flags
    df["is_shortened_season"] = season == 2020
    df["season_games"] = 60 if season == 2020 else 162
    df["season"] = season

    save_to_cache(df, key, parquet_path, season)
    return df
