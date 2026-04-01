"""Tests for the /games/{date} endpoint and status mapping logic.

Uses mocked schedule and DB data -- no real Postgres or MLB API needed.
"""

import pytest
from datetime import datetime, timezone, date, timedelta
from unittest.mock import patch, MagicMock

from api.models import GameResponse
from api.routes.games import (
    build_games_response,
    _build_prediction_group,
    compute_view_mode,
    _is_pitcher_confirmed,
    _apply_tomorrow_labels,
    _apply_live_pitchers,
)
from src.data.mlb_schedule import map_game_status


class TestStatusMapping:
    """Verify MLB API status -> badge status mapping."""

    def test_preview_maps_to_pre_game(self):
        assert map_game_status({"abstractGameState": "Preview", "codedGameState": "S"}) == "PRE_GAME"

    def test_live_maps_to_live(self):
        assert map_game_status({"abstractGameState": "Live", "codedGameState": "I"}) == "LIVE"

    def test_final_maps_to_final(self):
        assert map_game_status({"abstractGameState": "Final", "codedGameState": "F"}) == "FINAL"

    def test_postponed_detection(self):
        """codedGameState 'D' overrides abstractGameState 'Final' -> POSTPONED."""
        assert map_game_status({"abstractGameState": "Final", "codedGameState": "D"}) == "POSTPONED"

    def test_missing_fields_default_to_pre_game(self):
        assert map_game_status({}) == "PRE_GAME"

    def test_status_mapping(self):
        """Comprehensive mapping test."""
        cases = [
            ({"abstractGameState": "Preview"}, "PRE_GAME"),
            ({"abstractGameState": "Live"}, "LIVE"),
            ({"abstractGameState": "Final"}, "FINAL"),
            ({"abstractGameState": "Final", "codedGameState": "D"}, "POSTPONED"),
            ({"abstractGameState": "Preview", "codedGameState": "S"}, "PRE_GAME"),
        ]
        for status_obj, expected in cases:
            assert map_game_status(status_obj) == expected, f"Failed for {status_obj}"


class TestBuildGamesResponse:
    """Test the schedule + predictions merge logic."""

    def _make_schedule_game(self, game_id=718520, home="New York Yankees",
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

    def _make_prediction_row(self, game_id=718520, home="NYY", away="BOS",
                             version="pre_lineup"):
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
        }

    def test_games_with_predictions(self):
        """Games with matching predictions get prediction group populated."""
        schedule = [self._make_schedule_game()]
        predictions = [self._make_prediction_row()]
        result = build_games_response(schedule, predictions)

        assert len(result) == 1
        assert result[0].game_id == 718520
        assert result[0].home_team == "NYY"
        assert result[0].away_team == "BOS"
        assert result[0].game_status == "PRE_GAME"
        assert result[0].prediction is not None
        assert result[0].prediction.pre_lineup is not None
        assert result[0].prediction.pre_lineup.lr_prob == 0.58

    def test_stub_cards_for_unpredicted_games(self):
        """Games without prediction rows get prediction=None (stub card)."""
        schedule = [self._make_schedule_game(game_id=999999, home="Los Angeles Dodgers",
                                             away="San Francisco Giants")]
        predictions = []  # No predictions
        result = build_games_response(schedule, predictions)

        assert len(result) == 1
        assert result[0].game_id == 999999
        assert result[0].prediction is None

    def test_mixed_stub_and_prediction_cards(self):
        """Schedule with both predicted and unpredicted games."""
        schedule = [
            self._make_schedule_game(game_id=718520),
            self._make_schedule_game(game_id=718521, home="Los Angeles Dodgers",
                                     away="San Francisco Giants"),
        ]
        predictions = [self._make_prediction_row(game_id=718520)]
        result = build_games_response(schedule, predictions)

        assert len(result) == 2
        predicted = [g for g in result if g.prediction is not None]
        stubs = [g for g in result if g.prediction is None]
        assert len(predicted) == 1
        assert len(stubs) == 1
        assert predicted[0].game_id == 718520
        assert stubs[0].game_id == 718521

    def test_team_fallback_matching(self):
        """Predictions without game_id match by (home_team, away_team)."""
        schedule = [self._make_schedule_game()]
        predictions = [self._make_prediction_row(game_id=None)]
        result = build_games_response(schedule, predictions)

        assert len(result) == 1
        assert result[0].prediction is not None

    def test_pre_and_post_lineup_grouping(self):
        """Pre and post-lineup predictions grouped into PredictionGroup."""
        schedule = [self._make_schedule_game()]
        predictions = [
            self._make_prediction_row(version="pre_lineup"),
            self._make_prediction_row(version="post_lineup"),
        ]
        predictions[1]["prediction_status"] = "confirmed"
        predictions[1]["feature_set"] = "sp_enhanced"
        result = build_games_response(schedule, predictions)

        assert result[0].prediction is not None
        assert result[0].prediction.pre_lineup is not None
        assert result[0].prediction.post_lineup is not None

    def test_doubleheader_separate_cards(self):
        """Two games for same teams with different game_ids produce two cards."""
        schedule = [
            self._make_schedule_game(game_id=718520),
            self._make_schedule_game(game_id=718521),
        ]
        predictions = [
            self._make_prediction_row(game_id=718520),
            self._make_prediction_row(game_id=718521),
        ]
        result = build_games_response(schedule, predictions)

        assert len(result) == 2
        assert result[0].game_id != result[1].game_id
        assert result[0].prediction is not None
        assert result[1].prediction is not None


class TestGamesEndpoint:
    """Integration tests for the /games/{date} endpoint."""

    def test_invalid_date_returns_400(self, client):
        """Invalid date format returns 400."""
        response = client.get("/api/v1/games/not-a-date")
        assert response.status_code == 400

    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_endpoint_returns_games(self, mock_preds, mock_schedule, client):
        """Valid date returns GamesDateResponse shape."""
        mock_schedule.return_value = [{
            "game_id": 718520,
            "home_name": "New York Yankees",
            "away_name": "Boston Red Sox",
            "game_datetime": "2025-07-15T23:05:00Z",
            "game_status": "PRE_GAME",
            "doubleheader": "N",
            "game_num": 1,
        }]
        mock_preds.return_value = []

        response = client.get("/api/v1/games/2025-07-15")
        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert "generated_at" in data
        assert len(data["games"]) == 1
        assert data["games"][0]["game_id"] == 718520
        assert data["games"][0]["game_status"] == "PRE_GAME"
        assert data["games"][0]["prediction"] is None  # No predictions mocked

    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_endpoint_empty_schedule(self, mock_preds, mock_schedule, client):
        """No games for date returns empty games list."""
        mock_schedule.return_value = []
        mock_preds.return_value = []

        response = client.get("/api/v1/games/2025-12-25")
        assert response.status_code == 200
        assert response.json()["games"] == []


class TestDateNavigation:
    """Tests for view_mode computation (live/historical/tomorrow/future)."""

    FIXED_NOW = datetime(2025, 7, 15, 18, 0, 0)  # 6pm ET on July 15, 2025

    @patch("api.routes.games.datetime")
    def test_compute_view_mode_today(self, mock_dt):
        """Today's date returns 'live'."""
        mock_dt.now.return_value = self.FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert compute_view_mode("2025-07-15") == "live"

    @patch("api.routes.games.datetime")
    def test_compute_view_mode_past(self, mock_dt):
        """Past date returns 'historical'."""
        mock_dt.now.return_value = self.FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert compute_view_mode("2025-07-14") == "historical"

    @patch("api.routes.games.datetime")
    def test_compute_view_mode_tomorrow(self, mock_dt):
        """Tomorrow's date returns 'tomorrow'."""
        mock_dt.now.return_value = self.FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert compute_view_mode("2025-07-16") == "tomorrow"

    @patch("api.routes.games.datetime")
    def test_compute_view_mode_future(self, mock_dt):
        """Date 2+ days ahead returns 'future'."""
        mock_dt.now.return_value = self.FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert compute_view_mode("2025-07-17") == "future"

    @patch("api.routes.games.compute_view_mode", return_value="historical")
    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_endpoint_returns_view_mode_historical(self, mock_preds, mock_schedule, mock_vm, client):
        """GET /games/{past-date} includes view_mode='historical'."""
        mock_schedule.return_value = []
        mock_preds.return_value = []

        response = client.get("/api/v1/games/2025-01-01")
        assert response.status_code == 200
        data = response.json()
        assert data["view_mode"] == "historical"

    @patch("api.routes.games.compute_view_mode", return_value="live")
    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_endpoint_returns_view_mode_live(self, mock_preds, mock_schedule, mock_vm, client):
        """GET /games/{today} includes view_mode='live'."""
        mock_schedule.return_value = []
        mock_preds.return_value = []

        response = client.get("/api/v1/games/2025-07-15")
        assert response.status_code == 200
        data = response.json()
        assert data["view_mode"] == "live"

    @patch("api.routes.games.compute_view_mode", return_value="live")
    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_include_pitchers_true_for_live(self, mock_preds, mock_schedule, mock_vm, client):
        """get_schedule_cached called with include_pitchers=True for live (today) view."""
        mock_schedule.return_value = []
        mock_preds.return_value = []
        client.get("/api/v1/games/2025-07-15")
        mock_schedule.assert_called_once_with("2025-07-15", include_pitchers=True)

    @patch("api.routes.games.compute_view_mode", return_value="tomorrow")
    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_include_pitchers_true_for_tomorrow(self, mock_preds, mock_schedule, mock_vm, client):
        """get_schedule_cached called with include_pitchers=True for tomorrow view."""
        mock_schedule.return_value = []
        mock_preds.return_value = []
        client.get("/api/v1/games/2025-07-16")
        mock_schedule.assert_called_once_with("2025-07-16", include_pitchers=True)

    @patch("api.routes.games.compute_view_mode", return_value="future")
    @patch("api.routes.games.get_schedule_cached")
    @patch("api.routes.games._fetch_predictions_for_date")
    def test_endpoint_returns_view_mode_future(self, mock_preds, mock_schedule, mock_vm, client):
        """GET /games/{future-date} includes view_mode='future'."""
        mock_schedule.return_value = []
        mock_preds.return_value = []

        response = client.get("/api/v1/games/2099-07-15")
        assert response.status_code == 200
        data = response.json()
        assert data["view_mode"] == "future"


class TestTomorrowPreliminary:
    """Tests for pitcher confirmation and PRELIMINARY label logic."""

    def test_is_pitcher_confirmed_real_name(self):
        """Real pitcher name is confirmed."""
        assert _is_pitcher_confirmed("Gerrit Cole") is True

    def test_is_pitcher_confirmed_none(self):
        """None is not confirmed."""
        assert _is_pitcher_confirmed(None) is False

    def test_is_pitcher_confirmed_empty(self):
        """Empty string is not confirmed."""
        assert _is_pitcher_confirmed("") is False

    def test_is_pitcher_confirmed_tbd(self):
        """'TBD' is not confirmed."""
        assert _is_pitcher_confirmed("TBD") is False

    def test_is_pitcher_confirmed_tbd_whitespace(self):
        """' TBD ' with whitespace is not confirmed."""
        assert _is_pitcher_confirmed(" TBD ") is False

    def test_both_sps_confirmed_gets_preliminary(self):
        """Both SPs confirmed -> prediction_label='PRELIMINARY', pitcher names populated."""
        game = GameResponse(
            game_id=718520,
            home_team="NYY",
            away_team="BOS",
            game_time=None,
            game_status="PRE_GAME",
        )
        schedule = [{
            "game_id": 718520,
            "home_probable_pitcher": "Gerrit Cole",
            "away_probable_pitcher": "Chris Sale",
        }]
        _apply_tomorrow_labels([game], schedule)
        assert game.prediction_label == "PRELIMINARY"
        assert game.home_probable_pitcher == "Gerrit Cole"
        assert game.away_probable_pitcher == "Chris Sale"

    def test_missing_sp_no_label(self):
        """Missing home SP -> prediction_label stays None."""
        game = GameResponse(
            game_id=718520,
            home_team="NYY",
            away_team="BOS",
            game_time=None,
            game_status="PRE_GAME",
        )
        schedule = [{
            "game_id": 718520,
            "home_probable_pitcher": None,
            "away_probable_pitcher": "Chris Sale",
        }]
        _apply_tomorrow_labels([game], schedule)
        assert game.prediction_label is None

    def test_tbd_sp_no_label(self):
        """TBD away SP -> prediction_label stays None."""
        game = GameResponse(
            game_id=718520,
            home_team="NYY",
            away_team="BOS",
            game_time=None,
            game_status="PRE_GAME",
        )
        schedule = [{
            "game_id": 718520,
            "home_probable_pitcher": "Gerrit Cole",
            "away_probable_pitcher": "TBD",
        }]
        _apply_tomorrow_labels([game], schedule)
        assert game.prediction_label is None


class TestApplyLivePitchers:
    """Tests for _apply_live_pitchers -- pitcher name population for live (today) view."""

    def _make_game(self, game_id=718520):
        return GameResponse(game_id=game_id, home_team="NYY", away_team="BOS",
                            game_time=None, game_status="PRE_GAME")

    def test_both_confirmed_populates_names_no_label(self):
        """Both SPs confirmed -> names set, prediction_label stays None (no PRELIMINARY)."""
        game = self._make_game()
        schedule = [{"game_id": 718520,
                     "home_probable_pitcher": "Gerrit Cole",
                     "away_probable_pitcher": "Chris Sale"}]
        _apply_live_pitchers([game], schedule)
        assert game.home_probable_pitcher == "Gerrit Cole"
        assert game.away_probable_pitcher == "Chris Sale"
        assert game.prediction_label is None

    def test_one_tbd_populates_confirmed_only(self):
        """One TBD SP -> confirmed name set, TBD side is None."""
        game = self._make_game()
        schedule = [{"game_id": 718520,
                     "home_probable_pitcher": "Gerrit Cole",
                     "away_probable_pitcher": "TBD"}]
        _apply_live_pitchers([game], schedule)
        assert game.home_probable_pitcher == "Gerrit Cole"
        assert game.away_probable_pitcher is None
        assert game.prediction_label is None

    def test_both_tbd_sets_none(self):
        """Both SPs TBD -> both pitcher fields None."""
        game = self._make_game()
        schedule = [{"game_id": 718520,
                     "home_probable_pitcher": "TBD",
                     "away_probable_pitcher": "TBD"}]
        _apply_live_pitchers([game], schedule)
        assert game.home_probable_pitcher is None
        assert game.away_probable_pitcher is None
