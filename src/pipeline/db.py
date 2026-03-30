"""Database access layer for the live prediction pipeline.

Provides connection pool management and CRUD helpers for the games,
predictions, and pipeline_runs tables. All functions accept a
ConnectionPool and use parameterized queries.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/mlb_forecaster"
)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


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


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

# Columns for INSERT (excluding id, created_at which are auto-generated)
_PREDICTION_COLS = [
    "game_date", "home_team", "away_team", "prediction_version",
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal", "is_latest",
]

# Columns to update on conflict (everything except the unique key columns)
_PREDICTION_UPDATE_COLS = [
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal",
]


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
        DO UPDATE SET {update_set}
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
