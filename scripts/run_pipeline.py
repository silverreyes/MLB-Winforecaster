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

from src.pipeline.inference import load_all_artifacts
from src.pipeline.db import get_pool, apply_schema
from src.pipeline.scheduler import create_scheduler, start_scheduler
from src.pipeline.runner import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mlb_pipeline")


def main():
    parser = argparse.ArgumentParser(description="MLB Win Forecaster Pipeline")
    parser.add_argument(
        "--once",
        choices=["pre_lineup", "post_lineup", "confirmation"],
        help="Run a single pipeline version and exit (no scheduling)",
    )
    args = parser.parse_args()

    # Load model artifacts (fail hard if any missing)
    logger.info("Loading model artifacts...")
    artifacts = load_all_artifacts()
    logger.info(f"Loaded {len(artifacts)} model artifacts")

    # Connect to Postgres and apply schema
    logger.info("Connecting to Postgres...")
    pool = get_pool()
    apply_schema(pool)
    logger.info("Database schema applied")

    if args.once:
        # Single run mode (useful for testing and manual triggers)
        logger.info(f"Running single pipeline: {args.once}")
        run_pipeline(args.once, artifacts, pool)
        pool.close()
        logger.info("Done")
    else:
        # Scheduled mode (blocks forever)
        scheduler = create_scheduler(artifacts, pool)
        logger.info("Pipeline ready. Waiting for scheduled runs...")
        try:
            start_scheduler(scheduler)
        finally:
            pool.close()


if __name__ == "__main__":
    main()
