"""Tests for prediction API endpoints.

Tests cover:
- GET /api/v1/predictions/today with empty and populated results
- GET /api/v1/predictions/today game_time from schedule lookup
- GET /api/v1/predictions/{date} for historical dates (game_time null)
- GET /api/v1/predictions/latest-timestamp with and without data
- Graceful degradation when schedule fetch fails
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_ROW = {
    "id": 1,
    "game_date": date(2025, 6, 15),
    "home_team": "NYY",
    "away_team": "BOS",
    "prediction_version": "post_lineup",
    "prediction_status": "confirmed",
    "lr_prob": 0.58,
    "rf_prob": 0.55,
    "xgb_prob": 0.60,
    "feature_set": "sp_enhanced",
    "home_sp": "Gerrit Cole",
    "away_sp": "Brayan Bello",
    "sp_uncertainty": False,
    "sp_may_have_changed": False,
    "kalshi_yes_price": 0.52,
    "edge_signal": "BUY_YES",
    "is_latest": True,
    "created_at": datetime(2025, 6, 15, 17, 0, tzinfo=timezone.utc),
}

SAMPLE_ROW_2 = {
    "id": 2,
    "game_date": date(2025, 6, 15),
    "home_team": "LAD",
    "away_team": "SFG",
    "prediction_version": "pre_lineup",
    "prediction_status": "tbd",
    "lr_prob": 0.65,
    "rf_prob": 0.62,
    "xgb_prob": 0.68,
    "feature_set": "team_only",
    "home_sp": None,
    "away_sp": None,
    "sp_uncertainty": True,
    "sp_may_have_changed": False,
    "kalshi_yes_price": None,
    "edge_signal": None,
    "is_latest": True,
    "created_at": datetime(2025, 6, 15, 14, 0, tzinfo=timezone.utc),
}

MOCK_SCHEDULE = [
    {
        "home_name": "New York Yankees",
        "away_name": "Boston Red Sox",
        "game_datetime": "2025-06-15T23:05:00Z",
        "game_type": "R",
    },
    {
        "home_name": "Los Angeles Dodgers",
        "away_name": "San Francisco Giants",
        "game_datetime": "2025-06-16T01:10:00Z",
        "game_type": "R",
    },
]


def _mock_pool_fetchall(mock_pool, rows):
    """Configure mock_pool so pool.connection().cursor().fetchall() returns rows."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_pool.connection.return_value = mock_conn


def _mock_pool_fetchone(mock_pool, row):
    """Configure mock_pool so pool.connection().cursor().fetchone() returns row."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = row
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_pool.connection.return_value = mock_conn


class TestTodayEndpoint:
    """Tests for GET /api/v1/predictions/today."""

    def test_today_endpoint_empty(self, client, mock_pool):
        _mock_pool_fetchall(mock_pool, [])
        with patch("api.routes.predictions.fetch_today_schedule", return_value=[]):
            resp = client.get("/api/v1/predictions/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["predictions"] == []
        assert data["latest_prediction_at"] is None
        assert "generated_at" in data

    def test_today_endpoint_with_data(self, client, mock_pool):
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW, SAMPLE_ROW_2])
        with patch("api.routes.predictions.fetch_today_schedule", return_value=MOCK_SCHEDULE):
            resp = client.get("/api/v1/predictions/today")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 2

        # Check first prediction (NYY vs BOS)
        p1 = data["predictions"][0]
        expected_ensemble = round((0.58 + 0.55 + 0.60) / 3, 4)
        assert p1["ensemble_prob"] == expected_ensemble
        expected_edge = round((expected_ensemble - 0.52) * 100, 1)
        assert p1["edge_magnitude"] == expected_edge
        assert p1["home_team"] == "NYY"
        assert p1["away_team"] == "BOS"

        # game_time should be populated from schedule data
        assert p1["game_time"] is not None
        assert "2025-06-15T23:05:00" in p1["game_time"]

        # Check second prediction (LAD vs SFG) -- no kalshi price
        p2 = data["predictions"][1]
        expected_ensemble_2 = round((0.65 + 0.62 + 0.68) / 3, 4)
        assert p2["ensemble_prob"] == expected_ensemble_2
        assert p2["edge_magnitude"] is None  # No kalshi price
        assert p2["kalshi_yes_price"] is None

        # game_time should also be populated for second matchup
        assert p2["game_time"] is not None
        assert "2025-06-16T01:10:00" in p2["game_time"]

        # latest_prediction_at should be the max created_at
        assert data["latest_prediction_at"] is not None

    def test_today_endpoint_game_time_null_when_no_schedule(self, client, mock_pool):
        """When schedule returns no games, game_time should be null for all predictions."""
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW, SAMPLE_ROW_2])
        with patch("api.routes.predictions.fetch_today_schedule", return_value=[]):
            resp = client.get("/api/v1/predictions/today")
        assert resp.status_code == 200
        data = resp.json()
        for pred in data["predictions"]:
            assert pred["game_time"] is None

    def test_today_endpoint_schedule_fetch_fails_gracefully(self, client, mock_pool):
        """When schedule fetch raises an exception, endpoint still returns 200 with game_time null."""
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW])
        with patch("api.routes.predictions.fetch_today_schedule", side_effect=Exception("API down")):
            resp = client.get("/api/v1/predictions/today")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 1
        assert data["predictions"][0]["game_time"] is None


class TestDateEndpoint:
    """Tests for GET /api/v1/predictions/{date}."""

    def test_date_endpoint(self, client, mock_pool):
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW])
        resp = client.get("/api/v1/predictions/2025-06-15")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 1
        assert data["predictions"][0]["home_team"] == "NYY"
        # Historical date endpoint does NOT do schedule lookup -- game_time is null
        assert data["predictions"][0]["game_time"] is None

    def test_date_endpoint_invalid_format(self, client, mock_pool):
        resp = client.get("/api/v1/predictions/not-a-date")
        assert resp.status_code == 400


class TestLatestTimestamp:
    """Tests for GET /api/v1/predictions/latest-timestamp."""

    def test_latest_timestamp(self, client, mock_pool):
        ts = datetime(2025, 6, 15, 18, 30, tzinfo=timezone.utc)
        _mock_pool_fetchone(mock_pool, {"latest": ts})
        resp = client.get("/api/v1/predictions/latest-timestamp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timestamp"] is not None

    def test_latest_timestamp_empty(self, client, mock_pool):
        _mock_pool_fetchone(mock_pool, {"latest": None})
        resp = client.get("/api/v1/predictions/latest-timestamp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timestamp"] is None
