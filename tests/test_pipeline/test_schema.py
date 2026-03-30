"""Tests for Postgres schema creation, constraints, and DB helper functions.

Requires a running test Postgres instance. Tests are skipped gracefully
when Postgres is unavailable (via the pg_pool fixture in conftest.py).

Start test Postgres:
    docker run -d --name mlb-test-pg -e POSTGRES_DB=mlb_test \
        -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16
"""

import pytest
import psycopg.errors

from src.pipeline.db import (
    insert_prediction,
    mark_not_latest,
    get_post_lineup_prediction,
    insert_pipeline_run,
    update_pipeline_run,
    get_latest_pipeline_runs,
)


class TestSchemaCreation:
    """Verify schema DDL creates expected tables and columns."""

    def test_schema_creates_tables(self, pg_pool, clean_tables):
        """All three tables (games, predictions, pipeline_runs) exist."""
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cur.fetchall()]

        assert "games" in tables
        assert "predictions" in tables
        assert "pipeline_runs" in tables

    def test_predictions_has_expected_columns(self, pg_pool, clean_tables):
        """Predictions table has all required columns."""
        expected_columns = {
            "id", "game_date", "home_team", "away_team",
            "prediction_version", "prediction_status",
            "lr_prob", "rf_prob", "xgb_prob", "feature_set",
            "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
            "kalshi_yes_price", "edge_signal", "is_latest", "created_at",
        }

        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'predictions'
                """)
                actual_columns = {row[0] for row in cur.fetchall()}

        assert expected_columns.issubset(actual_columns), (
            f"Missing columns: {expected_columns - actual_columns}"
        )


class TestConstraints:
    """Verify CHECK and UNIQUE constraints enforce business rules."""

    def test_post_lineup_requires_confirmed_status(self, pg_pool, clean_tables):
        """post_lineup with status != 'confirmed' raises CheckViolation."""
        with pytest.raises(psycopg.errors.CheckViolation):
            with pg_pool.connection() as conn:
                conn.execute("""
                    INSERT INTO predictions (
                        game_date, home_team, away_team,
                        prediction_version, prediction_status, feature_set
                    ) VALUES (
                        '2025-07-15', 'NYY', 'BOS',
                        'post_lineup', 'tbd', 'sp_enhanced'
                    )
                """)
                conn.commit()

        # Confirmed status should succeed
        with pg_pool.connection() as conn:
            conn.execute("""
                INSERT INTO predictions (
                    game_date, home_team, away_team,
                    prediction_version, prediction_status, feature_set
                ) VALUES (
                    '2025-07-15', 'NYY', 'BOS',
                    'post_lineup', 'confirmed', 'sp_enhanced'
                )
            """)
            conn.commit()

    def test_unique_constraint_prevents_duplicate(
        self, pg_pool, clean_tables, sample_prediction_data
    ):
        """UPSERT via insert_prediction handles duplicates without error."""
        # Insert twice -- should not raise
        insert_prediction(pg_pool, sample_prediction_data)
        insert_prediction(pg_pool, sample_prediction_data)

        # Verify only one row exists
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM predictions
                    WHERE game_date = '2025-07-15'
                    AND home_team = 'NYY' AND away_team = 'BOS'
                    AND prediction_version = 'pre_lineup'
                    AND is_latest = TRUE
                """)
                count = cur.fetchone()[0]

        assert count == 1

    def test_prediction_status_enum_values(self, pg_pool, clean_tables):
        """Invalid enum value raises InvalidTextRepresentation."""
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            with pg_pool.connection() as conn:
                conn.execute("""
                    INSERT INTO predictions (
                        game_date, home_team, away_team,
                        prediction_version, prediction_status, feature_set
                    ) VALUES (
                        '2025-07-15', 'LAD', 'SFG',
                        'pre_lineup', 'invalid_value', 'team_only'
                    )
                """)
                conn.commit()


class TestCRUDHelpers:
    """Test insert, query, and update helper functions."""

    def test_insert_and_query_prediction(
        self, pg_pool, clean_tables, sample_prediction_data
    ):
        """Insert a pre_lineup prediction, then insert and query a post_lineup."""
        # Insert pre_lineup
        insert_prediction(pg_pool, sample_prediction_data)

        # Insert post_lineup (confirmed)
        post_data = sample_prediction_data.copy()
        post_data["prediction_version"] = "post_lineup"
        post_data["prediction_status"] = "confirmed"
        post_data["feature_set"] = "sp_enhanced"
        post_data["home_sp"] = "Gerrit Cole"
        post_data["away_sp"] = "Brayan Bello"
        post_data["lr_prob"] = 0.62
        insert_prediction(pg_pool, post_data)

        # Query post_lineup
        result = get_post_lineup_prediction(
            pg_pool, "2025-07-15", "NYY", "BOS"
        )

        assert result is not None
        assert result["prediction_version"] == "post_lineup"
        assert result["prediction_status"] == "confirmed"
        assert result["home_sp"] == "Gerrit Cole"
        assert result["away_sp"] == "Brayan Bello"
        assert abs(result["lr_prob"] - 0.62) < 0.01

    def test_mark_not_latest(
        self, pg_pool, clean_tables, sample_prediction_data
    ):
        """mark_not_latest sets is_latest = FALSE for matching rows."""
        insert_prediction(pg_pool, sample_prediction_data)

        # Verify is_latest starts as True
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT is_latest FROM predictions
                    WHERE game_date = '2025-07-15'
                    AND home_team = 'NYY' AND away_team = 'BOS'
                """)
                assert cur.fetchone()[0] is True

        # Mark not latest
        mark_not_latest(pg_pool, "2025-07-15", "NYY", "BOS", "pre_lineup")

        # Verify is_latest is now False
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT is_latest FROM predictions
                    WHERE game_date = '2025-07-15'
                    AND home_team = 'NYY' AND away_team = 'BOS'
                """)
                assert cur.fetchone()[0] is False

    def test_pipeline_run_lifecycle(self, pg_pool, clean_tables):
        """Full lifecycle: insert -> update -> query pipeline runs."""
        # Insert
        run_id = insert_pipeline_run(pg_pool, "pre_lineup", "2025-07-15")
        assert isinstance(run_id, int)

        # Verify initial state
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM pipeline_runs WHERE id = %s",
                    (run_id,),
                )
                assert cur.fetchone()[0] == "running"

        # Update
        update_pipeline_run(
            pg_pool, run_id, status="success", games_processed=15
        )

        # Verify updated state
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, games_processed, run_finished_at "
                    "FROM pipeline_runs WHERE id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
                assert row[0] == "success"
                assert row[1] == 15
                assert row[2] is not None  # run_finished_at set

        # Query latest runs
        latest = get_latest_pipeline_runs(pg_pool)
        assert len(latest) >= 1
        found = [r for r in latest if r["id"] == run_id]
        assert len(found) == 1
        assert found[0]["status"] == "success"
