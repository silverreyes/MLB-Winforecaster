"""Tests for the live poller job and outcome write function.

Covers: LIVE-08 (outcome write on Final transition, error handling, early exit).
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


class TestWriteGameOutcome:
    """LIVE-08: Write actual_winner and prediction_correct to all prediction rows."""

    def test_outcome_write_all_rows(self):
        """Updates ALL prediction rows for game_id, not just is_latest=TRUE."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_prediction_correct_home_wins(self):
        """prediction_correct=TRUE when ensemble predicted home and home won."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_prediction_correct_away_wins(self):
        """prediction_correct=TRUE when ensemble predicted away and away won."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_idempotent_skip_already_reconciled(self):
        """Skips rows where actual_winner is already set (WHERE actual_winner IS NULL)."""
        pytest.skip("Stub -- implementation in Plan 02")


class TestLivePollerJob:
    """LIVE-08: Live poller job behavior."""

    def test_no_live_games_early_exit(self):
        """Poller exits immediately when no games have abstractGameState='Live'."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_503_silent_skip(self):
        """On 503/timeout, poller logs and silently skips (no 15-min retry)."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_final_transition_writes_outcome(self):
        """When game transitions to Final, writes actual_winner + prediction_correct."""
        pytest.skip("Stub -- implementation in Plan 02")

    def test_poller_max_instances_config(self):
        """Live poller registered with max_instances=1 to prevent overlap."""
        pytest.skip("Stub -- implementation in Plan 02")
