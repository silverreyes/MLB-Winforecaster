"""MLB Stats API game schedule and probable pitcher loader with Parquet caching."""

import pandas as pd
import statsapi
from statsapi import schedule as statsapi_schedule
from src.data.cache import is_cached, save_to_cache, read_cached
from src.data.team_mappings import normalize_team

# MLB regular season date ranges (approximate -- covers full regular season)
SEASON_DATES = {
    2015: ("03/31/2015", "10/04/2015"),
    2016: ("04/03/2016", "10/02/2016"),
    2017: ("04/02/2017", "10/01/2017"),
    2018: ("03/29/2018", "10/01/2018"),
    2019: ("03/28/2019", "09/29/2019"),
    2020: ("07/23/2020", "09/27/2020"),  # COVID shortened season
    2021: ("04/01/2021", "10/03/2021"),
    2022: ("04/07/2022", "10/05/2022"),  # Lockout delayed start
    2023: ("03/30/2023", "10/01/2023"),
    2024: ("03/28/2024", "09/29/2024"),
    2025: ("03/27/2025", "09/28/2025"),  # 2025 regular season (needed for Phase 4 Kalshi join)
}


def fetch_schedule(season: int) -> pd.DataFrame:
    """Fetch MLB game schedule with probable pitchers for a full season.

    Returns DataFrame with columns:
    game_id, game_date, home_team, away_team,
    home_probable_pitcher, away_probable_pitcher,
    home_score, away_score, winning_team, losing_team, status
    Plus: is_shortened_season, season_games, season
    """
    key = f"schedule_{season}"
    parquet_path = f"mlb_api/schedule_{season}.parquet"

    if is_cached(key):
        return read_cached(key)

    if season not in SEASON_DATES:
        raise ValueError(
            f"Season {season} not in known date range. "
            f"Known: {sorted(SEASON_DATES.keys())}"
        )

    start_date, end_date = SEASON_DATES[season]
    games = statsapi_schedule(start_date=start_date, end_date=end_date, sportId=1)
    # Filter to regular season only (game_type="R").
    # The date ranges may overlap spring training or include exhibition
    # games (type "E") where minor league affiliates face MLB teams —
    # those team names are not in team_mappings and cause ValueError.
    games = [g for g in games if g.get("game_type") == "R"]

    # Convert list of dicts to DataFrame
    df = pd.DataFrame(games)

    # Handle empty schedule (e.g., future season with no final games)
    if df.empty:
        save_to_cache(df, key, parquet_path, season)
        return df

    # Normalize team names to canonical 3-letter codes
    # statsapi returns full team names like "New York Yankees"
    if "home_name" in df.columns:
        df["home_team"] = df["home_name"].apply(normalize_team)
    if "away_name" in df.columns:
        df["away_team"] = df["away_name"].apply(normalize_team)
    # Non-team sentinel values statsapi returns in winning_team/losing_team:
    # "Tie" — game ended tied (weather/darkness, rare but real in 2016 etc.)
    _SKIP_NORMALIZE = {"", "Tie"}
    if "winning_team" in df.columns:
        df["winning_team"] = df["winning_team"].apply(
            lambda x: normalize_team(x) if pd.notna(x) and x not in _SKIP_NORMALIZE else x
        )
    if "losing_team" in df.columns:
        df["losing_team"] = df["losing_team"].apply(
            lambda x: normalize_team(x) if pd.notna(x) and x not in _SKIP_NORMALIZE else x
        )

    # Rename for consistent column naming
    rename_map = {}
    if "game_id" not in df.columns and "gamePk" in df.columns:
        rename_map["gamePk"] = "game_id"
    df = df.rename(columns=rename_map)

    # Standardize empty probable pitcher values to None.
    # statsapi returns "" or "TBD" for unknown starters. Normalizing to None
    # prevents silent join failures in Phase 2 FeatureBuilder where mixed null
    # representations ("", None, NaN) would cause missed matches on pitcher name.
    for col in ["home_probable_pitcher", "away_probable_pitcher"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: None if (pd.isna(x) or str(x).strip() in ("", "TBD")) else x
            )

    # Add 2020 short-season flags
    df["is_shortened_season"] = season == 2020
    df["season_games"] = 60 if season == 2020 else 162
    df["season"] = season

    # Filter to regular season final games only (status "Final")
    if "status" in df.columns:
        df = df[df["status"] == "Final"].copy()

    save_to_cache(df, key, parquet_path, season)
    return df


def fetch_today_schedule() -> list[dict]:
    """Fetch today's MLB regular-season games with probable pitchers.

    Unlike fetch_schedule() which returns historical Final games as a DataFrame,
    this returns raw game dicts for today's date regardless of game status
    (Scheduled, Pre-Game, Warmup, In Progress, etc.).

    Returns:
        List of game dicts from statsapi.schedule(), each containing:
        game_id, game_date, home_name, away_name, home_probable_pitcher,
        away_probable_pitcher, game_type, status, etc.
        Filtered to game_type == "R" (regular season only).
        Team names are NOT normalized here (pipeline does that).
    """
    from datetime import date
    today = date.today().strftime("%m/%d/%Y")
    games = statsapi_schedule(start_date=today, end_date=today, sportId=1)
    # Filter to regular season only (exclude spring training, exhibitions, postseason)
    return [g for g in games if g.get("game_type") == "R"]
