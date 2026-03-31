"""Tests for the /games/{date} endpoint and status mapping logic.

Uses mocked schedule and DB data -- no real Postgres or MLB API needed.
"""

import pytest
from datetime import datetime, timezone, date
from unittest.mock import patch, MagicMock

from api.routes.games import build_games_response, _build_prediction_group
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
