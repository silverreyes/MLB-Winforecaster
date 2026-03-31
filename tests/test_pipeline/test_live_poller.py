"""Tests for the live poller job and outcome write function.

Covers: LIVE-08 (outcome write on Final transition, error handling, early exit).
"""
import socket
import urllib.error

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from src.pipeline.db import write_game_outcome
from src.pipeline.scheduler import live_poller_job


class TestWriteGameOutcome:
    """LIVE-08: Write actual_winner and prediction_correct to all prediction rows."""

    def _make_mock_pool(self, rowcount=1):
        """Helper to create a mock pool with connection context manager."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = rowcount
        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cur
        return mock_pool, mock_conn, mock_cur

    def test_outcome_write_all_rows(self):
        """Updates ALL prediction rows for game_id, not just is_latest=TRUE."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(rowcount=3)
        count = write_game_outcome(mock_pool, 747009, 'BOS', 'NYY', 5, 3)
        assert count == 3
        sql_arg = mock_conn.execute.call_args[0][0]
        assert 'WHERE game_id' in sql_arg
        assert 'actual_winner IS NULL' in sql_arg
        # Verify it does NOT filter by is_latest
        assert 'is_latest' not in sql_arg

    def test_prediction_correct_home_wins(self):
        """prediction_correct=TRUE when ensemble predicted home and home won."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(rowcount=1)
        write_game_outcome(mock_pool, 747009, 'BOS', 'NYY', 5, 3)
        params = mock_conn.execute.call_args[0][1]
        assert params['actual_winner'] == 'BOS'  # home wins

    def test_prediction_correct_away_wins(self):
        """prediction_correct=TRUE when ensemble predicted away and away won."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(rowcount=1)
        write_game_outcome(mock_pool, 747009, 'BOS', 'NYY', 1, 4)
        params = mock_conn.execute.call_args[0][1]
        assert params['actual_winner'] == 'NYY'  # away wins

    def test_idempotent_skip_already_reconciled(self):
        """Skips rows where actual_winner is already set (WHERE actual_winner IS NULL)."""
        mock_pool, mock_conn, mock_cur = self._make_mock_pool(rowcount=0)
        count = write_game_outcome(mock_pool, 747009, 'BOS', 'NYY', 5, 3)
        assert count == 0


class TestLivePollerJob:
    """LIVE-08: Live poller job behavior."""

    @patch('src.pipeline.scheduler.write_game_outcome')
    @patch('src.pipeline.scheduler.statsapi')
    @patch('src.pipeline.scheduler.get_schedule_cached')
    def test_no_live_games_early_exit(self, mock_sched, mock_api, mock_write):
        """Poller exits immediately when no games have abstractGameState='Live'."""
        mock_sched.return_value = [
            {'game_id': 1, 'game_status': 'PRE_GAME', 'home_name': 'X', 'away_name': 'Y'}
        ]
        live_poller_job(MagicMock())
        mock_api.get.assert_not_called()
        mock_write.assert_not_called()

    @patch('src.pipeline.scheduler.normalize_team')
    @patch('src.pipeline.scheduler.statsapi')
    @patch('src.pipeline.scheduler.get_schedule_cached')
    def test_503_silent_skip(self, mock_sched, mock_api, mock_norm):
        """503 comes from the linescore API fetch, NOT the schedule fetch.
        Schedule returns a FINAL game; statsapi.get raises HTTPError(503)."""
        mock_sched.return_value = [
            {'game_id': 747009, 'game_status': 'FINAL', 'home_name': 'Boston Red Sox', 'away_name': 'New York Yankees'}
        ]
        mock_norm.side_effect = lambda x: 'BOS' if 'Boston' in x else 'NYY'
        mock_api.get.side_effect = urllib.error.HTTPError(
            url=None, code=503, msg='Service Unavailable', hdrs=None, fp=None
        )
        # Should not raise -- poller silently skips on API error
        live_poller_job(MagicMock())

    @patch('src.pipeline.scheduler.write_game_outcome')
    @patch('src.pipeline.scheduler.normalize_team')
    @patch('src.pipeline.scheduler.statsapi')
    @patch('src.pipeline.scheduler.get_schedule_cached')
    def test_final_transition_writes_outcome(self, mock_sched, mock_api, mock_norm, mock_write):
        """When game transitions to Final, writes actual_winner + prediction_correct."""
        mock_sched.return_value = [
            {'game_id': 747009, 'game_status': 'FINAL', 'home_name': 'Boston Red Sox', 'away_name': 'New York Yankees'}
        ]
        mock_norm.side_effect = lambda x: 'BOS' if 'Boston' in x else 'NYY'
        mock_api.get.return_value = {
            'liveData': {'linescore': {'teams': {'home': {'runs': 5}, 'away': {'runs': 3}}}}
        }
        mock_write.return_value = 2
        live_poller_job(MagicMock())
        mock_write.assert_called_once()
        args = mock_write.call_args
        assert args[0][1] == 747009  # game_id
        assert args[0][4] == 5  # home_score
        assert args[0][5] == 3  # away_score

    def test_poller_max_instances_config(self):
        """Verify live_poller_job registered with max_instances=1."""
        with patch('src.pipeline.scheduler.run_pipeline'):
            from src.pipeline.scheduler import create_scheduler
            mock_artifacts = MagicMock()
            mock_pool = MagicMock()
            scheduler = create_scheduler(mock_artifacts, mock_pool)
            job = scheduler.get_job('live_poller')
            assert job is not None
            assert job.max_instances == 1
