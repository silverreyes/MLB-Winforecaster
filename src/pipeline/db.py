"""Database access layer for the live prediction pipeline.

Provides connection pool management and CRUD helpers for the games,
predictions, and pipeline_runs tables. All functions accept a
ConnectionPool and use parameterized queries.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/mlb_forecaster"
)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_MIGRATION_DIR = Path(__file__).parent


def get_pool(min_size: int = 2, max_size: int = 10) -> ConnectionPool:
    """Create and return a psycopg3 connection pool."""
    return ConnectionPool(conninfo=DATABASE_URL, min_size=min_size, max_size=max_size)


def apply_schema(pool: ConnectionPool) -> None:
    """Read schema.sql and execute it against the database.

    Handles 'already exists' errors for ENUM types gracefully so the
    function is idempotent.
    """
    raw_sql = _SCHEMA_PATH.read_text()

    with pool.connection() as conn:
        # Handle ENUM creation separately to allow idempotent re-runs.
        # Extract CREATE TYPE statements and wrap in exception-safe blocks.
        lines = raw_sql.split("\n")
        enum_statements = []
        other_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip().upper().startswith("CREATE TYPE"):
                # Collect the full statement (may span multiple lines)
                stmt = line
                while not stmt.rstrip().endswith(";"):
                    i += 1
                    stmt += "\n" + lines[i]
                enum_statements.append(stmt)
            else:
                other_lines.append(line)
            i += 1

        # Execute ENUM creations, ignoring duplicates
        for stmt in enum_statements:
            try:
                conn.execute(stmt)
            except psycopg.errors.DuplicateObject:
                conn.rollback()
                continue

        # Execute the rest of the schema
        remaining_sql = "\n".join(other_lines)
        conn.execute(remaining_sql)
        conn.commit()

    # Apply migrations (idempotent, safe to re-run)
    migration_path = _MIGRATION_DIR / "migration_001.sql"
    if migration_path.exists():
        migration_sql = migration_path.read_text()
        with pool.connection() as conn:
            conn.execute(migration_sql)
            conn.commit()
        logger.info("Applied migration_001.sql")
    else:
        logger.warning(
            "migration_001.sql not found at %s — skipping migration "
            "(check pyproject.toml package-data if running from pip install)",
            migration_path,
        )

    migration_002_path = _MIGRATION_DIR / "migration_002.sql"
    if migration_002_path.exists():
        migration_sql = migration_002_path.read_text()
        with pool.connection() as conn:
            conn.execute(migration_sql)
            conn.commit()
        logger.info("Applied migration_002.sql")


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

# Columns for INSERT (excluding id, created_at which are auto-generated)
_PREDICTION_COLS = [
    "game_date", "home_team", "away_team", "prediction_version",
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal", "is_latest",
    "game_id",  # Phase 13 SCHM-01
]

# Columns to update on conflict (everything except the unique key columns)
_PREDICTION_UPDATE_COLS = [
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal",
]
# NOTE: actual_winner, prediction_correct, reconciled_at deliberately excluded.
# These columns are written only by the reconciliation process (Phase 16).
# Including them here would cause pipeline UPSERT to overwrite reconciliation data.


def insert_prediction(pool: ConnectionPool, data: dict) -> None:
    """Insert or upsert a prediction row.

    Uses ON CONFLICT on uq_prediction to safely handle re-runs.
    """
    col_names = ", ".join(_PREDICTION_COLS)
    placeholders = ", ".join(f"%({c})s" for c in _PREDICTION_COLS)
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in _PREDICTION_UPDATE_COLS)

    sql = f"""
        INSERT INTO predictions ({col_names})
        VALUES ({placeholders})
        ON CONFLICT ON CONSTRAINT uq_prediction
        DO UPDATE SET {update_set}, created_at = NOW()
    """

    with pool.connection() as conn:
        conn.execute(sql, data)
        conn.commit()


def mark_not_latest(
    pool: ConnectionPool,
    game_date: str,
    home_team: str,
    away_team: str,
    prediction_version: str,
) -> None:
    """Set is_latest = FALSE for matching prediction rows."""
    sql = """
        UPDATE predictions
        SET is_latest = FALSE
        WHERE game_date = %(game_date)s
          AND home_team = %(home_team)s
          AND away_team = %(away_team)s
          AND prediction_version = %(prediction_version)s
    """
    with pool.connection() as conn:
        conn.execute(sql, {
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "prediction_version": prediction_version,
        })
        conn.commit()


def write_game_outcome(pool: ConnectionPool, game_id: int, home_team: str,
                       away_team: str, home_score: int, away_score: int) -> int:
    """Write actual_winner and prediction_correct for all predictions of a game.

    Targets ALL prediction rows matching game_id (not just is_latest=TRUE)
    per STATE.md carry-forward decision.

    prediction_correct is computed by comparing the ensemble probability
    ((lr_prob + rf_prob + xgb_prob) / 3.0) against 0.5 to determine if the
    model predicted the home team, then checking if actual_winner matches.

    Returns number of rows updated. Skips rows already reconciled
    (WHERE actual_winner IS NULL).
    """
    actual_winner = home_team if home_score > away_score else away_team

    sql = """
        UPDATE predictions
        SET actual_winner = %(actual_winner)s,
            prediction_correct = (
                CASE
                    WHEN (lr_prob + rf_prob + xgb_prob) / 3.0 >= 0.5
                    THEN %(actual_winner)s = home_team
                    ELSE %(actual_winner)s = away_team
                END
            ),
            reconciled_at = %(reconciled_at)s
        WHERE game_id = %(game_id)s
          AND actual_winner IS NULL
    """
    with pool.connection() as conn:
        cur = conn.execute(sql, {
            'game_id': game_id,
            'actual_winner': actual_winner,
            'reconciled_at': datetime.now(timezone.utc),
        })
        count = cur.rowcount
        conn.commit()
    return count


def get_post_lineup_prediction(
    pool: ConnectionPool,
    game_date: str,
    home_team: str,
    away_team: str,
) -> dict | None:
    """Fetch the most recent post_lineup prediction for a game.

    Returns a dict of column values or None if not found.
    """
    sql = """
        SELECT *
        FROM predictions
        WHERE game_date = %(game_date)s
          AND home_team = %(home_team)s
          AND away_team = %(away_team)s
          AND prediction_version = 'post_lineup'
          AND is_latest = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
            })
            return cur.fetchone()


# ---------------------------------------------------------------------------
# Pipeline run helpers
# ---------------------------------------------------------------------------


def insert_pipeline_run(
    pool: ConnectionPool,
    prediction_version: str,
    run_date: str,
) -> int:
    """Insert a new pipeline_runs row with status='running'.

    Returns the auto-generated row id.
    """
    sql = """
        INSERT INTO pipeline_runs (prediction_version, run_date, run_started_at, status)
        VALUES (%(prediction_version)s, %(run_date)s, %(run_started_at)s, 'running')
        RETURNING id
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "prediction_version": prediction_version,
                "run_date": run_date,
                "run_started_at": datetime.now(timezone.utc),
            })
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def update_pipeline_run(
    pool: ConnectionPool,
    run_id: int,
    status: str,
    games_processed: int,
    error_message: str | None = None,
) -> None:
    """Update a pipeline_runs row with completion info."""
    sql = """
        UPDATE pipeline_runs
        SET run_finished_at = %(run_finished_at)s,
            status = %(status)s,
            games_processed = %(games_processed)s,
            error_message = %(error_message)s
        WHERE id = %(run_id)s
    """
    with pool.connection() as conn:
        conn.execute(sql, {
            "run_id": run_id,
            "run_finished_at": datetime.now(timezone.utc),
            "status": status,
            "games_processed": games_processed,
            "error_message": error_message,
        })
        conn.commit()


def mark_stale_runs_failed(pool: ConnectionPool) -> int:
    """Mark any pipeline_runs still in 'running' state as failed.

    Called at process startup to clean up rows left open by OOM-killed
    processes that never got a chance to write their final status.
    Returns the number of rows updated.
    """
    sql = """
        UPDATE pipeline_runs
        SET status = 'failed',
            run_finished_at = NOW(),
            error_message = 'process killed (OOM/crash)'
        WHERE status = 'running'
    """
    with pool.connection() as conn:
        cur = conn.execute(sql)
        count = cur.rowcount
        conn.commit()
    return count


def get_latest_pipeline_runs(pool: ConnectionPool) -> list[dict]:
    """Return the most recent pipeline_run for each prediction_version.

    Useful for health/status endpoints.
    """
    sql = """
        SELECT DISTINCT ON (prediction_version)
            id, prediction_version, run_date, run_started_at,
            run_finished_at, status, games_processed, error_message
        FROM pipeline_runs
        ORDER BY prediction_version, run_started_at DESC
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Game log helpers (Phase 16: historical game cache)
# ---------------------------------------------------------------------------

# Imported at module level for testability (allows patch("src.pipeline.db.date_cls"))
from datetime import date as date_cls
from datetime import timedelta

import statsapi


def batch_insert_game_logs(pool: ConnectionPool, games: list[dict]) -> int:
    """Batch insert completed games into game_logs. Returns count of newly inserted rows.

    Uses INSERT ... ON CONFLICT (game_id) DO NOTHING for idempotency.
    Completed games are immutable -- never overwritten.
    """
    sql = """
        INSERT INTO game_logs (
            game_id, game_date, home_team, away_team,
            home_score, away_score, winning_team, losing_team,
            home_probable_pitcher, away_probable_pitcher, season
        ) VALUES (
            %(game_id)s, %(game_date)s, %(home_team)s, %(away_team)s,
            %(home_score)s, %(away_score)s, %(winning_team)s, %(losing_team)s,
            %(home_probable_pitcher)s, %(away_probable_pitcher)s, %(season)s
        )
        ON CONFLICT (game_id) DO NOTHING
    """
    inserted = 0
    with pool.connection() as conn:
        for game in games:
            cur = conn.execute(sql, game)
            inserted += cur.rowcount
        conn.commit()
    return inserted


def sync_game_logs(pool: ConnectionPool) -> int:
    """Fetch newly completed games since last known date in game_logs.

    Queries MAX(game_date), fetches from (MAX - 1 day) to yesterday,
    filters to Final regular-season games, normalizes team names,
    and batch inserts. Returns count of new rows inserted.

    If table is empty, logs warning and returns 0 (run seed script first).
    """
    from src.data.team_mappings import normalize_team

    # Get last known date
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(game_date) FROM game_logs")
            row = cur.fetchone()
            last_date = row[0] if row else None

    if last_date is None:
        logger.warning("game_logs table is empty -- run scripts/seed_game_logs.py first")
        return 0

    # Overlap by 1 day to catch late West Coast games
    start = (last_date - timedelta(days=1))
    end = date_cls.today() - timedelta(days=1)

    if start > end:
        logger.info("sync_game_logs: no new dates to sync (last_date=%s)", last_date)
        return 0

    start_str = start.strftime("%m/%d/%Y")
    end_str = end.strftime("%m/%d/%Y")

    logger.info("Fetching game_logs from %s to %s", start_str, end_str)
    games = statsapi.schedule(start_date=start_str, end_date=end_str, sportId=1)

    # Filter: Final + regular season only
    _SKIP_NORMALIZE = {"", "Tie"}
    final_games = []
    for g in games:
        if g.get("game_type") != "R" or g.get("status") != "Final":
            continue
        try:
            final_games.append({
                "game_id": str(g["game_id"]),
                "game_date": g["game_date"],
                "home_team": normalize_team(g["home_name"]),
                "away_team": normalize_team(g["away_name"]),
                "home_score": g["home_score"],
                "away_score": g["away_score"],
                "winning_team": (normalize_team(g["winning_team"])
                                 if g.get("winning_team") not in _SKIP_NORMALIZE
                                 else g.get("winning_team", "")),
                "losing_team": (normalize_team(g["losing_team"])
                                if g.get("losing_team") not in _SKIP_NORMALIZE
                                else g.get("losing_team", "")),
                "home_probable_pitcher": g.get("home_probable_pitcher") or None,
                "away_probable_pitcher": g.get("away_probable_pitcher") or None,
                "season": int(g["game_date"][:4]),  # extract from game date, NOT start.year
            })
        except (ValueError, KeyError) as exc:
            logger.warning("sync_game_logs: skipping game %s: %s", g.get("game_id"), exc)
            continue

    if not final_games:
        logger.info("sync_game_logs: no new Final games found")
        return 0

    inserted = batch_insert_game_logs(pool, final_games)
    logger.info("sync_game_logs: %d new games inserted (%d total fetched)", inserted, len(final_games))
    return inserted
