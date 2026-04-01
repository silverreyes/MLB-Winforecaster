"""Tests for FINAL game card data: scores, prediction display, outcome marker.

Covers: FINL-01 (final score), FINL-02 (model probability), FINL-03 (outcome marker).
"""
from datetime import datetime, timezone, date
from unittest.mock import MagicMock, patch

import pytest

from api.models import GameResponse
from api.routes.games import build_games_response


def _make_schedule_game(game_id=718520, home="New York Yankees",
                        away="Boston Red Sox", status="PRE_GAME"):
    return {
        "game_id": game_id,
        "home_name": home,
        "away_name": away,
        "game_datetime": "2025-07-15T23:05:00Z",
        "game_status": status,
        "doubleheader": "N",
        "game_num": 1,
    }


def _make_prediction_row(game_id=718520, home="NYY", away="BOS",
                         version="pre_lineup",
                         actual_winner=None, prediction_correct=None):
    return {
        "game_id": game_id,
        "game_date": date(2025, 7, 15),
        "home_team": home,
        "away_team": away,
        "prediction_version": version,
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
        "created_at": datetime(2025, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
        "actual_winner": actual_winner,
        "prediction_correct": prediction_correct,
    }


class TestFinalScoreDisplay:
    """FINL-01: FINAL game cards display final score from game_logs."""

    def test_final_game_has_scores(self):
        """build_games_response with FINAL game + game_logs data produces
        GameResponse with home_final_score=5, away_final_score=3."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row()]
        final_scores = {
            718520: {"home_score": 5, "away_score": 3, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert len(result) == 1
        assert result[0].home_final_score == 5
        assert result[0].away_final_score == 3

    def test_pregame_no_final_scores(self):
        """build_games_response with PRE_GAME game produces GameResponse
        with home_final_score=None, away_final_score=None."""
        schedule = [_make_schedule_game(status="PRE_GAME")]
        predictions = [_make_prediction_row()]
        final_scores = {}
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert len(result) == 1
        assert result[0].home_final_score is None
        assert result[0].away_final_score is None

    def test_final_game_no_game_logs_entry(self):
        """FINAL game without matching game_logs row (postponed then rescheduled)
        has home_final_score=None."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row()]
        final_scores = {}  # No game_logs entry for this game
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert len(result) == 1
        assert result[0].home_final_score is None
        assert result[0].away_final_score is None

    def test_game_id_type_cast_in_fetch(self):
        """_fetch_final_scores SQL casts game_id for proper join.
        Verify the SQL contains the INTEGER cast."""
        from api.routes.games import _fetch_final_scores
        # The function should exist and its SQL should contain the cast
        import inspect
        source = inspect.getsource(_fetch_final_scores)
        assert "game_id::INTEGER" in source or "CAST" in source


class TestFinalPredictionDisplay:
    """FINL-02: FINAL game cards display the model's ensemble probability."""

    def test_final_game_shows_ensemble_prob(self):
        """FINAL game with prediction shows ensemble_prob in prediction group."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row()]
        final_scores = {
            718520: {"home_score": 5, "away_score": 3, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert result[0].prediction is not None
        primary = result[0].prediction.pre_lineup
        assert primary is not None
        assert primary.ensemble_prob is not None
        # ensemble = (0.58 + 0.55 + 0.57) / 3 = 0.5667
        assert abs(primary.ensemble_prob - 0.5667) < 0.001

    def test_final_game_shows_prediction_correct(self):
        """FINAL game with prediction_correct=True has prediction_correct=True
        in response."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row(actual_winner="NYY", prediction_correct=True)]
        final_scores = {
            718520: {"home_score": 5, "away_score": 3, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert result[0].prediction is not None
        primary = result[0].prediction.pre_lineup
        assert primary is not None
        assert primary.prediction_correct is True


class TestOutcomeMarker:
    """FINL-03: Outcome marker (check or X) on FINAL game cards."""

    def test_prediction_correct_true_in_response(self):
        """build_games_response with prediction row containing prediction_correct=True
        produces PredictionResponse with prediction_correct=True."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row(actual_winner="NYY", prediction_correct=True)]
        final_scores = {
            718520: {"home_score": 5, "away_score": 3, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert result[0].prediction.pre_lineup.prediction_correct is True
        assert result[0].prediction_correct is True

    def test_prediction_correct_false_in_response(self):
        """Same but prediction_correct=False."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row(actual_winner="BOS", prediction_correct=False)]
        final_scores = {
            718520: {"home_score": 3, "away_score": 5, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert result[0].prediction.pre_lineup.prediction_correct is False
        assert result[0].prediction_correct is False

    def test_prediction_correct_null_no_reconciliation(self):
        """prediction_correct=None when game not yet reconciled."""
        schedule = [_make_schedule_game(status="FINAL")]
        predictions = [_make_prediction_row(actual_winner=None, prediction_correct=None)]
        final_scores = {
            718520: {"home_score": 5, "away_score": 3, "home_team": "NYY", "away_team": "BOS"}
        }
        result = build_games_response(schedule, predictions, final_scores=final_scores)
        assert result[0].prediction.pre_lineup.prediction_correct is None
        assert result[0].prediction_correct is None
