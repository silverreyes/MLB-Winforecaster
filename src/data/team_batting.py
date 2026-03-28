"""FanGraphs team batting statistics loader with Parquet caching."""

import pandas as pd
from pybaseball import team_batting as pybaseball_team_batting
from src.data.cache import is_cached, save_to_cache, read_cached


def fetch_team_batting(season: int) -> pd.DataFrame:
    """Fetch team batting stats for a single season. Returns from cache if available.

    Columns include: Team, G, PA, HR, R, RBI, SB, BB%, K%, ISO,
                     BABIP, AVG, OBP, SLG, wOBA, wRC+, WAR
    Plus: is_shortened_season, season_games, season

    Note: Team column uses FanGraphs canonical abbreviations as-is.
    These are generally consistent with MLB canonical codes but are NOT
    passed through normalize_team (unlike mlb_schedule.py which normalizes
    from full team names).
    """
    key = f"team_batting_{season}"
    parquet_path = f"pybaseball/team_batting_{season}.parquet"

    if is_cached(key):
        return read_cached(key)

    df = pybaseball_team_batting(season)

    # Add 2020 short-season flags (per user decision)
    df["is_shortened_season"] = season == 2020
    df["season_games"] = 60 if season == 2020 else 162
    df["season"] = season

    save_to_cache(df, key, parquet_path, season)
    return df
