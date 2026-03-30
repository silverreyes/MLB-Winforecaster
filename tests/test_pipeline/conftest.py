"""Shared fixtures for pipeline tests.

Uses a real Postgres instance (Docker or local) for integration tests.
Set TEST_DATABASE_URL env var to override default.
Falls back to monkeypatched mock pool for unit tests.
"""
import os
import pytest
import psycopg
from psycopg_pool import ConnectionPool
from unittest.mock import patch

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:test@localhost:5433/mlb_test"
)


@pytest.fixture(scope="session")
def pg_pool():
    """Create a connection pool to test Postgres.

    Skips all tests using this fixture if Postgres is not available.
    Start test Postgres via:
      docker run -d --name mlb-test-pg -e POSTGRES_DB=mlb_test \
        -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16
    """
    try:
        pool = ConnectionPool(conninfo=TEST_DATABASE_URL, min_size=1, max_size=3)
        # Verify connection works
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        yield pool
        pool.close()
    except (psycopg.OperationalError, Exception):
        pytest.skip("Test Postgres not available (start with: docker run -d --name mlb-test-pg -e POSTGRES_DB=mlb_test -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16)")


@pytest.fixture
def clean_tables(pg_pool):
    """Drop and recreate schema before each test for isolation.

    Not autouse -- must be explicitly requested by tests that need DB isolation.
    This prevents Postgres connection attempts in unit tests (test_inference.py,
    test_live_features.py) that don't touch the database.
    """
    with pg_pool.connection() as conn:
        conn.execute("DROP TABLE IF EXISTS pipeline_runs CASCADE")
        conn.execute("DROP TABLE IF EXISTS predictions CASCADE")
        conn.execute("DROP TABLE IF EXISTS games CASCADE")
        conn.execute("DROP TYPE IF EXISTS prediction_version CASCADE")
        conn.execute("DROP TYPE IF EXISTS prediction_status CASCADE")
        conn.commit()
    # Apply fresh schema
    from src.pipeline.db import apply_schema
    with patch("src.pipeline.db.DATABASE_URL", TEST_DATABASE_URL):
        apply_schema(pg_pool)
    yield
    # Cleanup handled by next test's DROP


@pytest.fixture
def sample_prediction_data():
    """Sample prediction data dict for insert_prediction tests."""
    return {
        "game_date": "2025-07-15",
        "home_team": "NYY",
        "away_team": "BOS",
        "prediction_version": "pre_lineup",
        "prediction_status": "tbd",
        "lr_prob": 0.58,
        "rf_prob": 0.55,
        "xgb_prob": 0.57,
        "feature_set": "team_only",
        "home_sp": None,
        "away_sp": None,
        "sp_uncertainty": True,
        "sp_may_have_changed": False,
        "kalshi_yes_price": 0.52,
        "edge_signal": "BUY_YES",
        "is_latest": True,
    }
