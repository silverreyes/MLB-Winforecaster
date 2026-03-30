"""APScheduler configuration for the three daily pipeline runs.

Schedule (US/Eastern timezone):
  10:00 AM ET - pre_lineup   (TEAM_ONLY predictions)
  01:00 PM ET - post_lineup  (SP_ENHANCED predictions)
  05:00 PM ET - confirmation (full re-run, SP change detection)

Uses APScheduler 3.x BlockingScheduler with CronTrigger.
Timezone handled via zoneinfo (Python 3.9+ stdlib).
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)

ET = ZoneInfo("US/Eastern")


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
        run_pipeline,
        CronTrigger(hour=10, minute=0, timezone="US/Eastern"),
        args=["pre_lineup", artifacts, pool],
        id="pre_lineup",
        name="Pre-lineup pipeline (10am ET)",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        run_pipeline,
        CronTrigger(hour=13, minute=0, timezone="US/Eastern"),
        args=["post_lineup", artifacts, pool],
        id="post_lineup",
        name="Post-lineup pipeline (1pm ET)",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        run_pipeline,
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
