#!/usr/bin/env python
"""Entry point for the MLB prediction pipeline.

Loads model artifacts, connects to Postgres, applies schema,
and starts the APScheduler with 3 daily cron jobs.

Usage:
    python scripts/run_pipeline.py           # Start scheduler (blocks)
    python scripts/run_pipeline.py --once pre_lineup   # Run once, then exit

Environment variables:
    DATABASE_URL  - Postgres connection string (default: postgresql://localhost:5432/mlb_forecaster)
    KALSHI_API_KEY - Optional Kalshi API key for authenticated requests
"""
import argparse
import logging
import sys
import time

from src.pipeline.inference import load_all_artifacts
from src.pipeline.db import get_pool, apply_schema, mark_stale_runs_failed, sync_game_logs
from src.pipeline.scheduler import create_scheduler, start_scheduler
from src.pipeline.runner import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mlb_pipeline")


MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


def _run_once(version: str) -> None:
    """Load artifacts, connect to DB, run a single pipeline version, and exit."""
    logger.info("Loading model artifacts...")
    artifacts = load_all_artifacts()
    logger.info(f"Loaded {len(artifacts)} model artifacts")

    logger.info("Connecting to Postgres...")
    pool = get_pool()
    apply_schema(pool)
    logger.info("Database schema applied")

    cleaned = mark_stale_runs_failed(pool)
    if cleaned:
        logger.warning(f"Marked {cleaned} stale 'running' run(s) as failed (OOM/crash from previous session)")

    # Sync game_logs: fetch newly completed games since last known date
    try:
        synced = sync_game_logs(pool)
        if synced > 0:
            logger.info(f"Synced {synced} new game(s) to game_logs")
    except Exception as e:
        logger.warning(f"game_logs sync failed (non-fatal): {e}")

    logger.info(f"Running single pipeline: {version}")
    run_pipeline(version, artifacts, pool)
    pool.close()
    logger.info("Done")


def _run_scheduler() -> None:
    """Load artifacts, connect to DB, and start the blocking scheduler."""
    logger.info("Loading model artifacts...")
    artifacts = load_all_artifacts()
    logger.info(f"Loaded {len(artifacts)} model artifacts")

    logger.info("Connecting to Postgres...")
    pool = get_pool()
    apply_schema(pool)
    logger.info("Database schema applied")

    cleaned = mark_stale_runs_failed(pool)
    if cleaned:
        logger.warning(f"Marked {cleaned} stale 'running' run(s) as failed (OOM/crash from previous session)")

    # Sync game_logs: fetch newly completed games since last known date
    try:
        synced = sync_game_logs(pool)
        if synced > 0:
            logger.info(f"Synced {synced} new game(s) to game_logs")
    except Exception as e:
        logger.warning(f"game_logs sync failed (non-fatal): {e}")

    scheduler = create_scheduler(artifacts, pool)
    logger.info("Pipeline ready. Waiting for scheduled runs...")
    try:
        start_scheduler(scheduler)
    finally:
        pool.close()


def main():
    parser = argparse.ArgumentParser(description="MLB Win Forecaster Pipeline")
    parser.add_argument(
        "--once",
        choices=["pre_lineup", "post_lineup", "confirmation"],
        help="Run a single pipeline version and exit (no scheduling)",
    )
    args = parser.parse_args()

    # The first run after a container start fetches pybaseball data cold
    # (team batting, SP stats, Chadwick register) which can spike memory
    # and crash before caches are written. Subsequent runs hit local cache
    # and succeed. Retry up to MAX_RETRIES times with a short delay.
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if args.once:
                _run_once(args.once)
            else:
                _run_scheduler()
            return
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"Pipeline attempt {attempt}/{MAX_RETRIES} failed: {e} — "
                    f"retrying in {RETRY_DELAY_SECONDS}s (caches will be warm)"
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Pipeline failed after {MAX_RETRIES} attempts: {e}")
                sys.exit(1)


if __name__ == "__main__":
    main()
