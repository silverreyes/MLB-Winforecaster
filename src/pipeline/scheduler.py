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

import statsapi
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.data.mlb_schedule import get_schedule_cached
from src.data.team_mappings import normalize_team
from src.pipeline.db import write_game_outcome
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


def live_poller_job(pool) -> None:
    """Poll for live game scores and write outcomes for newly-finished games.

    Runs every 90s via IntervalTrigger. On each cycle:
    1. Fetch today's schedule (cheap cached call)
    2. If no games have game_status == 'LIVE' or 'FINAL', exit immediately
    3. For each game with game_status == 'FINAL' that hasn't been reconciled,
       write actual_winner and prediction_correct to all prediction rows

    Error handling: On MLB API 503 or timeout, log and silently skip.
    Does NOT use the 15-minute RETRY_SLEEP_SECONDS pattern from pipeline jobs.
    """
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")

    try:
        schedule = get_schedule_cached(today_str)
    except Exception as exc:
        logger.warning("Live poller: schedule fetch failed (%s), skipping cycle", exc)
        return

    # Check if any games are currently live or final
    live_games = [g for g in schedule if g['game_status'] == 'LIVE']
    final_games = [g for g in schedule if g['game_status'] == 'FINAL']

    if not live_games and not final_games:
        logger.debug("Live poller: no live or final games, skipping cycle")
        return

    # Process newly-finished games (Final status)
    for game in final_games:
        game_id = game['game_id']
        try:
            home_name = game['home_name']
            away_name = game['away_name']
            home_team = normalize_team(home_name)
            away_team = normalize_team(away_name)
        except (ValueError, KeyError) as exc:
            logger.warning("Live poller: cannot normalize teams for game %s: %s", game_id, exc)
            continue

        # Need linescore data for final score
        try:
            raw = statsapi.get('game', {'gamePk': game_id,
                'fields': 'liveData,linescore,teams,home,away,runs'})
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, Exception) as exc:
            logger.warning("Live poller: API error for game %s (%s), skipping", game_id, exc)
            continue

        ls = raw.get('liveData', {}).get('linescore', {})
        home_score = ls.get('teams', {}).get('home', {}).get('runs')
        away_score = ls.get('teams', {}).get('away', {}).get('runs')

        if home_score is None or away_score is None:
            logger.warning("Live poller: no final score for game %s, skipping", game_id)
            continue

        try:
            count = write_game_outcome(pool, game_id, home_team, away_team, home_score, away_score)
            if count > 0:
                logger.info("Live poller: wrote outcome for game %s (%s %d - %s %d), %d rows updated",
                           game_id, away_team, away_score, home_team, home_score, count)
        except Exception as exc:
            logger.error("Live poller: DB write failed for game %s: %s", game_id, exc)


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

    scheduler.add_job(
        live_poller_job,
        IntervalTrigger(seconds=90),
        args=[pool],
        id="live_poller",
        name="Live score poller (90s)",
        max_instances=1,
        misfire_grace_time=30,
    )

    logger.info("Scheduler configured: pre_lineup@10am, post_lineup@1pm, confirmation@5pm ET, live_poller@90s")
    return scheduler


def start_scheduler(scheduler: BlockingScheduler):
    """Start the scheduler. Blocks the current thread."""
    logger.info("Starting scheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shut down gracefully")
