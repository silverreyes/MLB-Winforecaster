"""Tests for game_logs table: migration, CRUD, sync, and immutability.

Covers CACHE-01 (schema), CACHE-02 (seed/batch insert), CACHE-03 (sync),
CACHE-04 (FeatureBuilder reads from DB -- stub), CACHE-05 (immutability).
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock


SAMPLE_GAME = {
    "game_id": "718520",
    "game_date": "2026-04-10",
    "home_team": "NYY",
    "away_team": "BOS",
    "home_score": 5,
    "away_score": 3,
    "winning_team": "NYY",
    "losing_team": "BOS",
    "home_probable_pitcher": "Gerrit Cole",
    "away_probable_pitcher": "Brayan Bello",
    "season": 2026,
}

SAMPLE_GAME_2 = {
    "game_id": "718521",
    "game_date": "2026-04-10",
    "home_team": "LAD",
    "away_team": "SF",
    "home_score": 3,
    "away_score": 1,
    "winning_team": "LAD",
    "losing_team": "SF",
    "home_probable_pitcher": "Clayton Kershaw",
    "away_probable_pitcher": "Logan Webb",
    "season": 2026,
}

EXPECTED_COLUMNS = [
    "game_id", "game_date", "home_team", "away_team",
    "home_score", "away_score", "winning_team", "losing_team",
    "home_probable_pitcher", "away_probable_pitcher", "season",
]


class TestMigrationCreatesGameLogsTable:
    """CACHE-01: game_logs table exists with required columns after migration."""

    def test_migration_creates_game_logs_table(self, pg_pool, clean_tables):
        """After apply_schema(), game_logs table has all 11 expected columns."""
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'game_logs' "
                    "ORDER BY ordinal_position"
                )
                columns = [row[0] for row in cur.fetchall()]

        assert len(columns) == 11, f"Expected 11 columns, got {len(columns)}: {columns}"
        for col in EXPECTED_COLUMNS:
            assert col in columns, f"Missing column: {col}"


class TestBatchInsertGameLogs:
    """CACHE-02 / CACHE-05: Batch insert and immutability."""

    def test_batch_insert_returns_count(self, pg_pool, clean_tables):
        """batch_insert_game_logs(pool, [game1, game2]) returns 2."""
        from src.pipeline.db import batch_insert_game_logs

        count = batch_insert_game_logs(pg_pool, [SAMPLE_GAME, SAMPLE_GAME_2])
        assert count == 2

    def test_immutability_duplicate_insert(self, pg_pool, clean_tables):
        """Insert game_id=718520, then re-insert with different score.

        Second insert returns 0 and original row is unchanged.
        """
        from src.pipeline.db import batch_insert_game_logs

        # First insert
        count1 = batch_insert_game_logs(pg_pool, [SAMPLE_GAME])
        assert count1 == 1

        # Re-insert same game_id with different score
        modified_game = {**SAMPLE_GAME, "home_score": 99, "away_score": 88}
        count2 = batch_insert_game_logs(pg_pool, [modified_game])
        assert count2 == 0

        # Verify original row unchanged
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT home_score, away_score FROM game_logs WHERE game_id = %s",
                    ("718520",),
                )
                row = cur.fetchone()
        assert row[0] == 5, f"home_score changed to {row[0]}"
        assert row[1] == 3, f"away_score changed to {row[1]}"


class TestSyncGameLogs:
    """CACHE-03: Incremental sync from MAX(game_date) - 1 day forward."""

    def test_sync_empty_table_returns_zero(self, pg_pool, clean_tables):
        """When game_logs is empty, sync_game_logs returns 0."""
        from src.pipeline.db import sync_game_logs

        with patch("src.pipeline.db.statsapi") as mock_api:
            count = sync_game_logs(pg_pool)

        assert count == 0
        mock_api.schedule.assert_not_called()

    def test_sync_fetches_from_max_date(self, pg_pool, clean_tables):
        """After inserting games through April 10, sync fetches from April 9."""
        from src.pipeline.db import batch_insert_game_logs, sync_game_logs

        # Seed some games through April 10
        batch_insert_game_logs(pg_pool, [SAMPLE_GAME, SAMPLE_GAME_2])

        # Mock statsapi to return a "new" game from April 11
        new_api_game = {
            "game_id": 718600,
            "game_date": "2026-04-11",
            "home_name": "New York Yankees",
            "away_name": "Boston Red Sox",
            "home_score": 4,
            "away_score": 2,
            "winning_team": "New York Yankees",
            "losing_team": "Boston Red Sox",
            "home_probable_pitcher": "Gerrit Cole",
            "away_probable_pitcher": "Brayan Bello",
            "game_type": "R",
            "status": "Final",
        }

        with patch("src.pipeline.db.statsapi") as mock_api:
            mock_api.schedule.return_value = [new_api_game]
            # Freeze "today" so end_date is deterministic
            with patch("src.pipeline.db.date_cls") as mock_date_cls:
                mock_date_cls.today.return_value = date(2026, 4, 12)
                mock_date_cls.side_effect = lambda *a, **kw: date(*a, **kw)
                count = sync_game_logs(pg_pool)

        # Verify API was called with start_date = April 9 (max_date - 1 day)
        call_args = mock_api.schedule.call_args
        assert call_args is not None, "statsapi.schedule was not called"
        assert call_args[1]["start_date"] == "04/09/2026"
        assert call_args[1]["end_date"] == "04/11/2026"

        # Verify the new game was inserted
        assert count == 1


class TestFeatureBuilderReadsGameLogs:
    """CACHE-04: FeatureBuilder with pool reads from game_logs, not fetch_schedule."""

    def test_feature_builder_reads_game_logs(self, pg_pool, clean_tables):
        """CACHE-04: FeatureBuilder with pool reads from game_logs, not fetch_schedule."""
        from src.pipeline.db import batch_insert_game_logs
        from src.features.feature_builder import FeatureBuilder
        from unittest.mock import patch

        # Insert sample games into game_logs
        games = [
            {
                "game_id": "100001",
                "game_date": "2026-04-01",
                "home_team": "NYY",
                "away_team": "BOS",
                "home_score": 5,
                "away_score": 3,
                "winning_team": "NYY",
                "losing_team": "BOS",
                "home_probable_pitcher": "Gerrit Cole",
                "away_probable_pitcher": "Brayan Bello",
                "season": 2026,
            },
            {
                "game_id": "100002",
                "game_date": "2026-04-02",
                "home_team": "LAD",
                "away_team": "SFG",
                "home_score": 4,
                "away_score": 2,
                "winning_team": "LAD",
                "losing_team": "SFG",
                "home_probable_pitcher": "Clayton Kershaw",
                "away_probable_pitcher": "Logan Webb",
                "season": 2026,
            },
        ]
        batch_insert_game_logs(pg_pool, games)

        # Create FeatureBuilder with pool -- should NOT call fetch_schedule
        fb = FeatureBuilder(seasons=[2026], as_of_date="2026-04-15", pool=pg_pool)

        with patch("src.features.feature_builder.fetch_schedule") as mock_fetch:
            df = fb._load_schedule()
            mock_fetch.assert_not_called()  # Must NOT call API

        # Verify DataFrame has expected columns and data
        assert len(df) == 2
        assert "game_id" in df.columns
        assert "home_team" in df.columns
        assert "is_shortened_season" in df.columns
        assert "season_games" in df.columns
        assert "status" in df.columns
        assert df["status"].iloc[0] == "Final"
        assert set(df["home_team"]) == {"NYY", "LAD"}
