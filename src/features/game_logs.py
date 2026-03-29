"""Per-game team batting log loader using the MLB Stats API.

Replaces the original pybaseball.team_game_logs() implementation, which
scraped Baseball Reference. BRef is now behind Cloudflare JS-challenge
and returns HTTP 403 for all programmatic requests.

This module calls the official MLB Stats API via the `statsapi` library:
    statsapi.get('team_stats', {'teamId': id, 'stats': 'gameLog',
                                'group': 'hitting', 'season': year})

One API call returns all 162 rows for a team-season — the same granularity
as the old BRef game logs. No rate-limiting is required (official API,
not a scraper), but we retain a small courtesy delay to avoid hammering
the MLB endpoint during bulk backfill.

Functions:
    fetch_team_game_log: Fetch/cache one team-season game log
    fetch_all_team_game_logs: Batch fetch with optional delay
"""

import time
import logging
import pandas as pd
import statsapi
from src.data.cache import is_cached, save_to_cache, read_cached

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 0.3  # seconds between MLB Stats API requests (courtesy delay)

# Canonical 3-letter codes (MLB.com / BRef standard) → MLB Stats API numeric team IDs.
# IDs are stable across seasons — the Athletics stayed id=133 even after relocating.
CANONICAL_TO_STATSAPI_ID: dict[str, int] = {
    "ARI": 109,
    "ATL": 144,
    "BAL": 110,
    "BOS": 111,
    "CHC": 112,
    "CHW": 145,
    "CIN": 113,
    "CLE": 114,
    "COL": 115,
    "DET": 116,
    "HOU": 117,
    "KCR": 118,
    "LAA": 108,
    "LAD": 119,
    "MIA": 146,
    "MIL": 158,
    "MIN": 142,
    "NYM": 121,
    "NYY": 147,
    "OAK": 133,
    "PHI": 143,
    "PIT": 134,
    "SDP": 135,
    "SEA": 136,
    "SFG": 137,
    "STL": 138,
    "TBR": 139,
    "TEX": 140,
    "TOR": 141,
    "WSN": 120,
}

# All 30 canonical team codes for bulk iteration
ALL_TEAMS: list[str] = sorted(CANONICAL_TO_STATSAPI_ID.keys())

# Stat columns returned by the MLB API gameLog endpoint.
# These map cleanly to the old BRef column names used by FeatureBuilder.
_STAT_COLS = [
    "runs", "hits", "atBats", "doubles", "triples", "homeRuns",
    "strikeOuts", "baseOnBalls", "hitByPitch", "stolenBases",
    "rbi", "leftOnBase", "plateAppearances", "totalBases",
    "avg", "obp", "slg", "ops",
]


def _splits_to_dataframe(splits: list[dict], team: str, season: int) -> pd.DataFrame:
    """Convert raw API splits list to a clean DataFrame.

    Each split has shape:
        {season, stat: {runs, hits, ...}, team: {...}, opponent: {...},
         date, isHome, isWin, game: {gamePk, ...}}

    Returns a DataFrame with one row per game, columns:
        game_date, is_home, is_win, game_pk, opp_team_id,
        runs, hits, at_bats, doubles, triples, home_runs,
        strike_outs, base_on_balls, hit_by_pitch, stolen_bases,
        rbi, left_on_base, plate_appearances, total_bases,
        avg, obp, slg, ops,
        team, season, is_shortened_season
    """
    rows = []
    for s in splits:
        stat = s.get("stat", {})
        row = {
            "game_date": s.get("date"),
            "is_home": s.get("isHome", False),
            "is_win": s.get("isWin", False),
            "game_pk": s.get("game", {}).get("gamePk"),
            "opp_team_id": s.get("opponent", {}).get("id"),
            # Batting stat columns — use snake_case for consistency
            "runs": stat.get("runs"),
            "hits": stat.get("hits"),
            "at_bats": stat.get("atBats"),
            "doubles": stat.get("doubles"),
            "triples": stat.get("triples"),
            "home_runs": stat.get("homeRuns"),
            "strike_outs": stat.get("strikeOuts"),
            "base_on_balls": stat.get("baseOnBalls"),
            "hit_by_pitch": stat.get("hitByPitch"),
            "stolen_bases": stat.get("stolenBases"),
            "rbi": stat.get("rbi"),
            "left_on_base": stat.get("leftOnBase"),
            "plate_appearances": stat.get("plateAppearances"),
            "total_bases": stat.get("totalBases"),
            "avg": stat.get("avg"),
            "obp": stat.get("obp"),
            "slg": stat.get("slg"),
            "ops": stat.get("ops"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Parse dates and numeric-string columns
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    for col in ["avg", "obp", "slg", "ops"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["team"] = team
    df["season"] = season
    df["is_shortened_season"] = season == 2020

    return df.sort_values("game_date").reset_index(drop=True)


def fetch_team_game_log(season: int, team: str) -> pd.DataFrame:
    """Fetch per-game batting log for one team-season via the MLB Stats API.

    Cache key: team_game_log_{season}_{team}  (e.g., team_game_log_2023_NYY)
    Parquet path: mlb_api/team_game_log_{season}_{team}.parquet

    One API call returns all games for the team-season (~162 rows for a
    full season, ~60 rows for the 2020 shortened season).

    Args:
        season: MLB season year (e.g., 2023).
        team: Canonical 3-letter team code (e.g., 'NYY').

    Returns:
        DataFrame with per-game batting stats plus metadata columns:
        team, season, is_shortened_season.

    Raises:
        ValueError: If team is not in CANONICAL_TO_STATSAPI_ID.
        Exception: Re-raises any error from the statsapi call.
    """
    if team not in CANONICAL_TO_STATSAPI_ID:
        raise ValueError(
            f"Unknown team code '{team}'. "
            f"Must be one of: {sorted(CANONICAL_TO_STATSAPI_ID)}"
        )

    key = f"team_game_log_{season}_{team}"
    parquet_path = f"mlb_api/team_game_log_{season}_{team}.parquet"

    if is_cached(key):
        return read_cached(key)

    team_id = CANONICAL_TO_STATSAPI_ID[team]
    try:
        result = statsapi.get(
            "team_stats",
            {"teamId": team_id, "stats": "gameLog", "group": "hitting", "season": season},
        )
        splits = result["stats"][0]["splits"]
        df = _splits_to_dataframe(splits, team, season)

        save_to_cache(df, key, parquet_path, season)
        logger.info("Fetched %s %d via MLB Stats API (%d games)", team, season, len(df))
        return df

    except (KeyError, IndexError) as exc:
        logger.error("Unexpected API response structure for %s %d: %s", team, season, exc)
        raise
    except Exception:
        logger.error("Failed to fetch game log for %s %d", team, season)
        raise


def fetch_all_team_game_logs(
    seasons: list[int], teams: list[str]
) -> list[tuple[int, str]]:
    """Fetch and cache per-game batting logs for all team-seasons.

    Iterates all season × team combinations with a small courtesy delay.
    Cached entries are skipped instantly (no delay).

    300 calls (30 teams × 10 seasons) at 0.3-second intervals ≈ 90 seconds.
    This is much faster than the old BRef scraper (~10 minutes at 2s/call).

    Args:
        seasons: List of season years (e.g., [2015, 2016, ..., 2024]).
        teams: List of canonical 3-letter team codes.

    Returns:
        List of (season, team) tuples that failed. Empty list on full success.
    """
    failures: list[tuple[int, str]] = []
    fetched = 0
    total = len(seasons) * len(teams)

    for season in seasons:
        for team in teams:
            if is_cached(f"team_game_log_{season}_{team}"):
                continue  # Already cached — no delay needed

            try:
                fetch_team_game_log(season, team)
                fetched += 1
                logger.info("Fetched %s %d (%d/%d)", team, season, fetched, total)
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error("Failed %s %d: %s", team, season, e)
                failures.append((season, team))
                time.sleep(RATE_LIMIT_DELAY * 3)  # Longer back-off on error

    return failures
