"""APScheduler configuration for the three daily pipeline runs.

Schedule (US/Eastern timezone):
  10:00 AM ET - pre_lineup   (TEAM_ONLY predictions)
  01:00 PM ET - post_lineup  (SP_ENHANCED predictions)
  05:00 PM ET - confirmation (full re-run, SP change detection)

Uses APScheduler 3.x BlockingScheduler with CronTrigger.
Timezone handled via zoneinfo (Python 3.9+ stdlib).
"""
import logging
import socket
import time
import urllib.error
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)

ET = ZoneInfo("US/Eastern")

RETRY_SLEEP_SECONDS = 900  # 15 minutes


def run_pipeline_with_retry(version: str, artifacts: dict, pool) -> None:
    """Run a pipeline job with one retry on transient MLB Stats API errors.

    Retries once (after RETRY_SLEEP_SECONDS) on:
    - urllib.error.HTTPError with code 503 (service unavailable)
    - urllib.error.URLError (connection timeout, DNS failure, etc.)
    - socket.timeout (raw socket timeout)

    All other exception types propagate immediately without retry.
    If the retry also fails, its exception propagates normally.

    Args:
        version: 'pre_lineup', 'post_lineup', or 'confirmation'.
        artifacts: All 6 loaded model artifacts.
        pool: psycopg ConnectionPool.
    """
    try:
        run_pipeline(version, artifacts, pool)
    except urllib.error.HTTPError as exc:
        if exc.code != 503:
            raise
        logger.warning(
            "MLB Stats API returned 503 for %s pipeline — retrying in %d minutes",
            version,
            RETRY_SLEEP_SECONDS // 60,
        )
        time.sleep(RETRY_SLEEP_SECONDS)
        run_pipeline(version, artifacts, pool)
    except (urllib.error.URLError, socket.timeout) as exc:
        logger.warning(
            "MLB Stats API connection error (%s) for %s pipeline — retrying in %d minutes",
            type(exc).__name__,
            version,
            RETRY_SLEEP_SECONDS // 60,
        )
        time.sleep(RETRY_SLEEP_SECONDS)
        run_pipeline(version, artifacts, pool)


def create_scheduler(artifacts: dict, pool) -> BlockingScheduler:
    """Create and configure the APScheduler with 3 daily pipeline jobs.

    Args:
        artifacts: All 6 loaded model artifacts.
        pool: psycopg ConnectionPool.

    Returns:
        Configured BlockingScheduler (not yet started).
    """
    scheduler = BlockingScheduler()

    scheduler.add_job(
        run_pipeline_with_retry,
        CronTrigger(hour=10, minute=0, timezone="US/Eastern"),
        args=["pre_lineup", artifacts, pool],
        id="pre_lineup",
        name="Pre-lineup pipeline (10am ET)",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        run_pipeline_with_retry,
        CronTrigger(hour=13, minute=0, timezone="US/Eastern"),
        args=["post_lineup", artifacts, pool],
        id="post_lineup",
        name="Post-lineup pipeline (1pm ET)",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        run_pipeline_with_retry,
        CronTrigger(hour=17, minute=0, timezone="US/Eastern"),
        args=["confirmation", artifacts, pool],
        id="confirmation",
        name="Confirmation pipeline (5pm ET)",
        misfire_grace_time=300,
    )

    logger.info("Scheduler configured: pre_lineup@10am, post_lineup@1pm, confirmation@5pm ET")
    return scheduler


def start_scheduler(scheduler: BlockingScheduler):
    """Start the scheduler. Blocks the current thread."""
    logger.info("Starting scheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shut down gracefully")
