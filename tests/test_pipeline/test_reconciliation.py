"""Tests for nightly reconciliation logic.

Covers: FINL-04 (reconcile_outcomes, idempotency, type casting, edge cases).
"""
from unittest.mock import MagicMock, patch, call

from src.pipeline.db import reconcile_outcomes


class TestReconcileOutcomes:
    """FINL-04: Nightly reconciliation stamps Final games not written by poller."""

    def _make_mock_pool(self, fetchall_return=None):
        """Create mock pool that returns controlled fetchall results.

        Uses the same mock pool pattern as test_live_poller.py:
        pool.connection().__enter__() -> mock_conn
        conn.cursor(row_factory=...).__enter__() -> mock_cur
        """
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        mock_cur.fetchall.return_value = fetchall_return or []

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        return mock_pool, mock_conn, mock_cur

    @patch('src.pipeline.db.write_game_outcome')
    def test_reconciles_unwritten_games(self, mock_write):
        """Given game_logs has a Final game and predictions have actual_winner IS NULL,
        reconcile_outcomes calls write_game_outcome with correct args."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(
            fetchall_return=[{
                "game_id_int": 718520,
                "home_team": "NYY",
                "away_team": "BOS",
                "home_score": 5,
                "away_score": 3,
            }]
        )
        mock_write.return_value = 2

        count = reconcile_outcomes(mock_pool, "2025-07-15")

        mock_write.assert_called_once_with(
            mock_pool, 718520, "NYY", "BOS", 5, 3
        )
        assert count == 2

    @patch('src.pipeline.db.write_game_outcome')
    def test_idempotent_second_run(self, mock_write):
        """Calling reconcile_outcomes twice on same date returns 0 on second call
        (all rows already reconciled -- fetchall returns empty)."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(fetchall_return=[])
        mock_write.return_value = 0

        count = reconcile_outcomes(mock_pool, "2025-07-15")

        mock_write.assert_not_called()
        assert count == 0

    @patch('src.pipeline.db.write_game_outcome')
    def test_skips_postponed_no_game_logs(self, mock_write):
        """Predictions exist for a game_id that has no game_logs entry;
        INNER JOIN naturally excludes, so fetchall returns empty."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(fetchall_return=[])

        count = reconcile_outcomes(mock_pool, "2025-07-15")

        mock_write.assert_not_called()
        assert count == 0

    def test_skips_null_game_id_predictions(self):
        """Verify the SQL contains p.game_id IS NOT NULL to skip null game_ids."""
        # We need to inspect the SQL that reconcile_outcomes executes.
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(fetchall_return=[])

        reconcile_outcomes(mock_pool, "2025-07-15")

        # Get the SQL from the cursor execute call
        sql_arg = mock_cur.execute.call_args[0][0]
        assert "p.game_id IS NOT NULL" in sql_arg

    def test_type_cast_varchar_to_integer(self):
        """Verify the SQL casts game_logs.game_id (VARCHAR) to INTEGER for join."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(fetchall_return=[])

        reconcile_outcomes(mock_pool, "2025-07-15")

        sql_arg = mock_cur.execute.call_args[0][0]
        assert "gl.game_id::INTEGER" in sql_arg

    @patch('src.pipeline.db.write_game_outcome')
    def test_returns_total_rows_updated(self, mock_write):
        """With 3 prediction rows for same game_id, returns count of all updated rows."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(
            fetchall_return=[{
                "game_id_int": 718520,
                "home_team": "NYY",
                "away_team": "BOS",
                "home_score": 5,
                "away_score": 3,
            }]
        )
        mock_write.return_value = 3

        count = reconcile_outcomes(mock_pool, "2025-07-15")

        assert count == 3

    @patch('src.pipeline.db.write_game_outcome')
    def test_empty_date_returns_zero(self, mock_write):
        """Date with no unreconciled predictions returns 0."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(fetchall_return=[])

        count = reconcile_outcomes(mock_pool, "2025-07-15")

        mock_write.assert_not_called()
        assert count == 0
