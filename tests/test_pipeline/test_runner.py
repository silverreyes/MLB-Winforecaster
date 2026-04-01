"""Tests for src/pipeline/runner.py.

All tests mock external dependencies (db.py, live_features.py, inference.py,
kalshi.py). No real DB or API calls.
"""
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from src.pipeline.runner import compute_edge_signal, run_pipeline, EDGE_THRESHOLD


# ---------------------------------------------------------------------------
# Edge signal tests
# ---------------------------------------------------------------------------


def test_compute_edge_signal_buy_yes():
    """Model avg well above Kalshi price => BUY_YES."""
    probs = {"lr": 0.65, "rf": 0.63, "xgb": 0.64}
    result = compute_edge_signal(probs, 0.52)
    assert result == "BUY_YES"  # avg 0.64 - 0.52 = 0.12 > 0.05


def test_compute_edge_signal_buy_no():
    """Model avg well below Kalshi price => BUY_NO."""
    probs = {"lr": 0.40}
    result = compute_edge_signal(probs, 0.55)
    assert result == "BUY_NO"  # 0.40 - 0.55 = -0.15 < -0.05


def test_compute_edge_signal_no_edge():
    """Model avg close to Kalshi price => NO_EDGE."""
    probs = {"lr": 0.53}
    result = compute_edge_signal(probs, 0.52)
    assert result == "NO_EDGE"  # |0.01| <= 0.05


def test_compute_edge_signal_no_kalshi():
    """No Kalshi price => NO_EDGE."""
    probs = {"lr": 0.65}
    result = compute_edge_signal(probs, None)
    assert result == "NO_EDGE"


def test_compute_edge_signal_empty_probs():
    """Empty model probs => NO_EDGE."""
    result = compute_edge_signal({}, 0.55)
    assert result == "NO_EDGE"


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_game(home="NYY", away="BOS", home_sp="Gerrit Cole", away_sp="Brayan Bello"):
    return {
        "game_id": 12345,
        "game_date": "2025-07-15",
        "home_team": home,
        "away_team": away,
        "home_probable_pitcher": home_sp,
        "away_probable_pitcher": away_sp,
        "status": "Scheduled",
    }


def _make_probs():
    return {"lr": 0.55, "rf": 0.53, "xgb": 0.54}


@pytest.fixture
def mock_feature_builder():
    fb = MagicMock()
    fb.get_today_games.return_value = [_make_game()]
    fb.build_features_for_game.return_value = {"feat1": 0.5, "feat2": 0.3}
    fb.sp_confirmed.return_value = True
    return fb


@pytest.fixture
def mock_pool():
    return MagicMock()


@pytest.fixture
def mock_artifacts():
    return {"lr_team_only": {}, "rf_team_only": {}, "xgb_team_only": {}}


# ---------------------------------------------------------------------------
# Pre-lineup tests
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_pre_lineup_run(
    mock_update_run,
    mock_insert_run,
    mock_insert_pred,
    mock_predict,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Pre-lineup inserts TEAM_ONLY with sp_uncertainty=True and pitcher names."""
    run_pipeline("pre_lineup", mock_artifacts, mock_pool, mock_feature_builder)

    mock_insert_pred.assert_called_once()
    pred_data = mock_insert_pred.call_args[0][1]
    assert pred_data["prediction_version"] == "pre_lineup"
    assert pred_data["prediction_status"] == "tbd"
    assert pred_data["feature_set"] == "team_only"
    assert pred_data["sp_uncertainty"] is True  # still True — TEAM_ONLY models
    assert pred_data["home_sp"] == "Gerrit Cole"
    assert pred_data["away_sp"] == "Brayan Bello"


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_pre_lineup_no_pitcher_available(
    mock_update_run,
    mock_insert_run,
    mock_insert_pred,
    mock_predict,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
):
    """Pre-lineup with no pitcher data sets home_sp/away_sp to None."""
    fb = MagicMock()
    fb.get_today_games.return_value = [_make_game(home_sp=None, away_sp=None)]
    fb.build_features_for_game.return_value = {"feat1": 0.5, "feat2": 0.3}
    fb.sp_confirmed.return_value = False

    run_pipeline("pre_lineup", mock_artifacts, mock_pool, fb)

    mock_insert_pred.assert_called_once()
    pred_data = mock_insert_pred.call_args[0][1]
    assert pred_data["home_sp"] is None
    assert pred_data["away_sp"] is None
    assert pred_data["sp_uncertainty"] is True


# ---------------------------------------------------------------------------
# Post-lineup tests
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_post_lineup_confirmed_sp(
    mock_update_run,
    mock_insert_run,
    mock_insert_pred,
    mock_predict,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Post-lineup with confirmed SPs inserts SP_ENHANCED prediction."""
    mock_feature_builder.sp_confirmed.return_value = True

    run_pipeline("post_lineup", mock_artifacts, mock_pool, mock_feature_builder)

    mock_insert_pred.assert_called_once()
    pred_data = mock_insert_pred.call_args[0][1]
    assert pred_data["prediction_version"] == "post_lineup"
    assert pred_data["prediction_status"] == "confirmed"
    assert pred_data["feature_set"] == "sp_enhanced"
    assert pred_data["home_sp"] == "Gerrit Cole"
    assert pred_data["away_sp"] == "Brayan Bello"


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_post_lineup_tbd_sp_skipped(
    mock_update_run,
    mock_insert_run,
    mock_insert_pred,
    mock_predict,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Post-lineup with TBD starters does NOT insert post_lineup prediction (PIPE-07)."""
    mock_feature_builder.sp_confirmed.return_value = False

    run_pipeline("post_lineup", mock_artifacts, mock_pool, mock_feature_builder)

    # insert_prediction should NOT be called for post_lineup with TBD SPs
    mock_insert_pred.assert_not_called()


# ---------------------------------------------------------------------------
# Confirmation tests
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.get_post_lineup_prediction")
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.mark_not_latest")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_confirmation_no_sp_change(
    mock_update_run,
    mock_insert_run,
    mock_mark,
    mock_insert_pred,
    mock_predict,
    mock_get_existing,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Confirmation with same SPs does NOT call mark_not_latest."""
    mock_get_existing.return_value = {
        "home_sp": "Gerrit Cole",
        "away_sp": "Brayan Bello",
    }

    run_pipeline("confirmation", mock_artifacts, mock_pool, mock_feature_builder)

    mock_mark.assert_not_called()
    mock_insert_pred.assert_called_once()
    pred_data = mock_insert_pred.call_args[0][1]
    assert pred_data["sp_may_have_changed"] is False


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.get_post_lineup_prediction")
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.mark_not_latest")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
@patch("src.pipeline.runner.update_pipeline_run")
def test_confirmation_sp_changed(
    mock_update_run,
    mock_insert_run,
    mock_mark,
    mock_insert_pred,
    mock_predict,
    mock_get_existing,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Confirmation with changed SPs calls mark_not_latest and sets sp_may_have_changed."""
    mock_get_existing.return_value = {
        "home_sp": "Carlos Rodon",
        "away_sp": "Tanner Houck",
    }

    run_pipeline("confirmation", mock_artifacts, mock_pool, mock_feature_builder)

    mock_mark.assert_called_once()
    mock_insert_pred.assert_called_once()
    pred_data = mock_insert_pred.call_args[0][1]
    assert pred_data["sp_may_have_changed"] is True


# ---------------------------------------------------------------------------
# Pipeline run logging tests
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.predict_game", return_value=_make_probs())
@patch("src.pipeline.runner.insert_prediction")
@patch("src.pipeline.runner.insert_pipeline_run", return_value=42)
@patch("src.pipeline.runner.update_pipeline_run")
def test_pipeline_run_logging(
    mock_update_run,
    mock_insert_run,
    mock_insert_pred,
    mock_predict,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
    mock_feature_builder,
):
    """Pipeline run inserts run at start and updates with success at end."""
    run_pipeline("pre_lineup", mock_artifacts, mock_pool, mock_feature_builder)

    mock_insert_run.assert_called_once()
    mock_update_run.assert_called_once()
    update_args = mock_update_run.call_args
    assert update_args[0][1] == 42  # run_id
    assert update_args[0][2] == "success"  # status
    assert update_args[0][3] == 1  # games_processed


@patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
@patch("src.pipeline.runner.insert_pipeline_run", return_value=42)
@patch("src.pipeline.runner.update_pipeline_run")
def test_pipeline_run_error_logging(
    mock_update_run,
    mock_insert_run,
    mock_kalshi,
    mock_pool,
    mock_artifacts,
):
    """Pipeline run failure logs error status."""
    fb = MagicMock()
    fb.initialize.side_effect = RuntimeError("feature build exploded")

    with pytest.raises(RuntimeError):
        run_pipeline("pre_lineup", mock_artifacts, mock_pool, fb)

    mock_update_run.assert_called_once()
    update_args = mock_update_run.call_args
    assert update_args[0][2] == "failed"  # status


# ---------------------------------------------------------------------------
# Game status gate tests
# ---------------------------------------------------------------------------


class TestGameStatusGate:
    """Pipeline must not write new prediction rows for in-progress or finished games."""

    def _run_with_status(self, status, mock_insert_pred, mock_pool, mock_artifacts):
        """Helper: run pre_lineup pipeline with a game of the given status."""
        fb = MagicMock()
        fb.get_today_games.return_value = [
            {**_make_game(), "status": status}
        ]
        fb.build_features_for_game.return_value = {"feat1": 0.5}
        fb.sp_confirmed.return_value = True
        run_pipeline("pre_lineup", mock_artifacts, mock_pool, fb)

    @patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
    @patch("src.pipeline.runner.predict_game", return_value=_make_probs())
    @patch("src.pipeline.runner.insert_prediction")
    @patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
    @patch("src.pipeline.runner.update_pipeline_run")
    def test_in_progress_game_skipped(
        self, mock_update, mock_insert_run, mock_insert_pred, mock_predict, mock_kalshi,
        mock_pool, mock_artifacts,
    ):
        """Games with status 'In Progress' must not produce a prediction row."""
        self._run_with_status("In Progress", mock_insert_pred, mock_pool, mock_artifacts)
        mock_insert_pred.assert_not_called()

    @patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
    @patch("src.pipeline.runner.predict_game", return_value=_make_probs())
    @patch("src.pipeline.runner.insert_prediction")
    @patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
    @patch("src.pipeline.runner.update_pipeline_run")
    def test_final_game_skipped(
        self, mock_update, mock_insert_run, mock_insert_pred, mock_predict, mock_kalshi,
        mock_pool, mock_artifacts,
    ):
        """Games with status 'Final' must not produce a prediction row."""
        self._run_with_status("Final", mock_insert_pred, mock_pool, mock_artifacts)
        mock_insert_pred.assert_not_called()

    @patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
    @patch("src.pipeline.runner.predict_game", return_value=_make_probs())
    @patch("src.pipeline.runner.insert_prediction")
    @patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
    @patch("src.pipeline.runner.update_pipeline_run")
    def test_game_over_skipped(
        self, mock_update, mock_insert_run, mock_insert_pred, mock_predict, mock_kalshi,
        mock_pool, mock_artifacts,
    ):
        """Games with status 'Game Over' must not produce a prediction row."""
        self._run_with_status("Game Over", mock_insert_pred, mock_pool, mock_artifacts)
        mock_insert_pred.assert_not_called()

    @pytest.mark.parametrize("status", ["Scheduled", "Pre-Game", "Preview", "Warmup", "", None])
    @patch("src.pipeline.runner.fetch_kalshi_live_prices", return_value={})
    @patch("src.pipeline.runner.predict_game", return_value=_make_probs())
    @patch("src.pipeline.runner.insert_prediction")
    @patch("src.pipeline.runner.insert_pipeline_run", return_value=1)
    @patch("src.pipeline.runner.update_pipeline_run")
    def test_pre_game_statuses_are_processed(
        self, mock_update, mock_insert_run, mock_insert_pred, mock_predict, mock_kalshi,
        mock_pool, mock_artifacts, status,
    ):
        """All recognised pre-game statuses must pass the gate and produce a prediction row."""
        self._run_with_status(status, mock_insert_pred, mock_pool, mock_artifacts)
        mock_insert_pred.assert_called_once()
