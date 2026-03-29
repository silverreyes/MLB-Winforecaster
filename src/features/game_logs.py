"""Per-game team batting log loader with rate-limited caching.

Fetches per-game batting data from Baseball Reference via pybaseball's
team_game_logs() function. Caches results as Parquet files using the
shared cache infrastructure from Phase 1.

Rate limiting is mandatory: Baseball Reference has anti-scraping protections.
300 rapid requests (30 teams x 10 seasons) will trigger rate limiting or
IP bans without explicit delays.

Functions:
    fetch_team_game_log: Fetch/cache one team-season game log
    fetch_all_team_game_logs: Batch fetch with rate limiting and error handling
"""

import time
import logging
import pandas as pd
from pybaseball import team_game_logs as pybaseball_team_game_logs
from src.data.cache import is_cached, save_to_cache, read_cached

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 2.0  # seconds between Baseball Reference requests

# All 30 canonical MLB teams for iteration
ALL_TEAMS = [
    "ARI", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE", "COL", "DET",
    "HOU", "KCR", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "OAK",
    "PHI", "PIT", "SDP", "SEA", "SFG", "STL", "TBR", "TEX", "TOR", "WSN",
]


def fetch_team_game_log(season: int, team: str) -> pd.DataFrame:
    """Fetch per-game batting log for one team-season. Cache-aware.

    Cache key: team_game_log_{season}_{team} (e.g., team_game_log_2023_NYY)
    Parquet path: pybaseball/team_game_log_{season}_{team}.parquet

    Callers always pass canonical team codes from ALL_TEAMS. pybaseball's
    team_game_logs() accepts these codes directly (verified in RESEARCH.md).
    No normalize_team() call is needed here -- normalization is handled
    upstream by callers who source team codes from schedule data.

    Args:
        season: MLB season year (e.g., 2023).
        team: Canonical 3-letter team code (e.g., 'NYY').

    Returns:
        DataFrame with per-game batting stats plus metadata columns:
        team, season, is_shortened_season.

    Raises:
        Exception: Re-raises any error from pybaseball (not silently swallowed).
    """
    key = f"team_game_log_{season}_{team}"
    parquet_path = f"pybaseball/team_game_log_{season}_{team}.parquet"

    if is_cached(key):
        return read_cached(key)

    try:
        df = pybaseball_team_game_logs(season, team)

        # Add metadata columns
        df["team"] = team
        df["season"] = season
        df["is_shortened_season"] = season == 2020

        save_to_cache(df, key, parquet_path, season)
        return df
    except Exception:
        logger.error(f"Failed to fetch game log for {team} {season}")
        raise


def fetch_all_team_game_logs(
    seasons: list[int], teams: list[str]
) -> list[tuple[int, str]]:
    """Fetch and cache per-game batting logs for all team-seasons.

    Iterates all season x team combinations with rate limiting.
    Cached entries are skipped instantly (no delay).
    Uncached fetches sleep RATE_LIMIT_DELAY (2.0s) between calls.
    On error: logs, appends to failures list, sleeps 2x delay, continues.

    300 calls (30 teams x 10 seasons) at 2-second intervals = ~10 minutes.
    Cached calls skip the delay (instant return from Parquet).

    Args:
        seasons: List of season years (e.g., [2015, 2016, ..., 2024]).
        teams: List of canonical 3-letter team codes.

    Returns:
        List of (season, team) tuples that failed. Empty list on full success.
        Callers can surface failures without log inspection.
    """
    total = len(seasons) * len(teams)
    fetched = 0
    failures: list[tuple[int, str]] = []

    for season in seasons:
        for team in teams:
            if is_cached(f"team_game_log_{season}_{team}"):
                continue  # Already cached, no delay needed

            try:
                fetch_team_game_log(season, team)
                fetched += 1
                logger.info(f"Fetched {team} {season} ({fetched}/{total})")
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error(f"Failed {team} {season}: {e}")
                failures.append((season, team))
                time.sleep(RATE_LIMIT_DELAY * 2)  # Exponential backoff on error

    return failures
