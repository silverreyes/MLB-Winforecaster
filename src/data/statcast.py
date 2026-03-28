"""Baseball Savant Statcast metrics loader with Parquet caching."""

import pandas as pd
from pybaseball import (
    statcast_pitcher_expected_stats as pybaseball_statcast_pitcher_expected_stats,
    statcast_batter_expected_stats as pybaseball_statcast_batter_expected_stats,
)
from src.data.cache import is_cached, save_to_cache, read_cached


def fetch_statcast_pitcher(season: int, min_pa: int = 50) -> pd.DataFrame:
    """Fetch Statcast pitcher expected stats (xwOBA, xBA, xSLG, etc.) for a season.

    Only available for 2015+ (Statcast hardware deployment year).
    Note: Player names/teams use Baseball Savant canonical form as-is.
    """
    key = f"statcast_pitcher_{season}"
    parquet_path = f"statcast/statcast_pitcher_{season}.parquet"

    if is_cached(key):
        return read_cached(key)

    if season < 2015:
        raise ValueError(f"Statcast data not available before 2015 (requested {season})")

    df = pybaseball_statcast_pitcher_expected_stats(season, minPA=min_pa)

    df["is_shortened_season"] = season == 2020
    df["season_games"] = 60 if season == 2020 else 162
    df["season"] = season

    save_to_cache(df, key, parquet_path, season)
    return df


def fetch_statcast_batter(season: int, min_pa: int = 50) -> pd.DataFrame:
    """Fetch Statcast batter expected stats (xwOBA, xBA, xSLG, etc.) for a season.

    Only available for 2015+ (Statcast hardware deployment year).
    Note: Player names/teams use Baseball Savant canonical form as-is.
    """
    key = f"statcast_batter_{season}"
    parquet_path = f"statcast/statcast_batter_{season}.parquet"

    if is_cached(key):
        return read_cached(key)

    if season < 2015:
        raise ValueError(f"Statcast data not available before 2015 (requested {season})")

    df = pybaseball_statcast_batter_expected_stats(season, minPA=min_pa)

    df["is_shortened_season"] = season == 2020
    df["season_games"] = 60 if season == 2020 else 162
    df["season"] = season

    save_to_cache(df, key, parquet_path, season)
    return df
