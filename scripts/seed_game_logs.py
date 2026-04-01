#!/usr/bin/env python
"""One-time seed script: backfill game_logs from MLB Stats API.

Fetches all Final regular-season games for the specified seasons and inserts
them into the game_logs Postgres table. Idempotent via ON CONFLICT DO NOTHING.

Usage:
    python scripts/seed_game_logs.py                    # Default: 2025 2026
    python scripts/seed_game_logs.py --seasons 2025     # Only 2025
    docker compose exec worker python scripts/seed_game_logs.py
"""

import argparse
import logging

import statsapi

from src.data.mlb_schedule import SEASON_DATES
from src.data.team_mappings import normalize_team
from src.pipeline.db import apply_schema, batch_insert_game_logs, get_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("seed_game_logs")

# Non-team sentinel values statsapi returns in winning_team/losing_team
_SKIP_NORMALIZE = {"", "Tie"}


def _normalize_game(g: dict, season: int) -> dict:
    """Convert a raw statsapi.schedule() game dict to a game_logs insert dict.

    Raises ValueError if team name normalization fails (caller should skip).
    """
    return {
        "game_id": str(g["game_id"]),
        "game_date": g["game_date"],
        "home_team": normalize_team(g["home_name"]),
        "away_team": normalize_team(g["away_name"]),
        "home_score": g["home_score"],
        "away_score": g["away_score"],
        "winning_team": (
            normalize_team(g["winning_team"])
            if g.get("winning_team") not in _SKIP_NORMALIZE
            else g.get("winning_team", "")
        ),
        "losing_team": (
            normalize_team(g["losing_team"])
            if g.get("losing_team") not in _SKIP_NORMALIZE
            else g.get("losing_team", "")
        ),
        "home_probable_pitcher": g.get("home_probable_pitcher") or None,
        "away_probable_pitcher": g.get("away_probable_pitcher") or None,
        "season": season,
    }


def seed(seasons: list[int]) -> int:
    """Fetch and insert Final regular-season games for the given seasons.

    Returns total number of newly inserted rows across all seasons.
    """
    pool = get_pool()
    apply_schema(pool)
    logger.info("Database schema applied (migration_002 ensures game_logs exists)")

    total_inserted = 0

    for season in seasons:
        if season not in SEASON_DATES:
            logger.warning(
                "Season %d not in SEASON_DATES -- skipping. Known: %s",
                season,
                sorted(SEASON_DATES.keys()),
            )
            continue

        start_date, end_date = SEASON_DATES[season]
        logger.info("Fetching season %d: %s to %s ...", season, start_date, end_date)

        games = statsapi.schedule(
            start_date=start_date, end_date=end_date, sportId=1
        )

        # Filter: Final + regular season only
        final_games = []
        skipped = 0
        for g in games:
            if g.get("game_type") != "R" or g.get("status") != "Final":
                continue
            try:
                final_games.append(_normalize_game(g, season))
            except (ValueError, KeyError) as exc:
                logger.warning(
                    "Skipping game %s: %s", g.get("game_id"), exc
                )
                skipped += 1

        if not final_games:
            logger.info("Season %d: no Final games found", season)
            continue

        inserted = batch_insert_game_logs(pool, final_games)
        total_inserted += inserted
        logger.info(
            "Season %d: fetched %d Final games, inserted %d new rows, "
            "skipped %d duplicates%s",
            season,
            len(final_games),
            inserted,
            len(final_games) - inserted,
            f", {skipped} normalization errors" if skipped else "",
        )

    logger.info(
        "Seed complete: %d total new rows across %d season(s)",
        total_inserted,
        len(seasons),
    )

    pool.close()
    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill game_logs from MLB Stats API"
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2025, 2026],
        help="Seasons to backfill (default: 2025 2026)",
    )
    args = parser.parse_args()
    seed(args.seasons)


if __name__ == "__main__":
    main()
