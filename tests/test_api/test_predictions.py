"""Tests for prediction API endpoints.

Tests cover:
- GET /api/v1/predictions/today with empty and populated results
- GET /api/v1/predictions/{date} for historical dates
- GET /api/v1/predictions/latest-timestamp with and without data
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
        resp = client.get("/api/v1/predictions/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["predictions"] == []
        assert data["latest_prediction_at"] is None
        assert "generated_at" in data

    def test_today_endpoint_with_data(self, client, mock_pool):
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW, SAMPLE_ROW_2])
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

        # Check second prediction (LAD vs SFG) -- no kalshi price
        p2 = data["predictions"][1]
        expected_ensemble_2 = round((0.65 + 0.62 + 0.68) / 3, 4)
        assert p2["ensemble_prob"] == expected_ensemble_2
        assert p2["edge_magnitude"] is None  # No kalshi price
        assert p2["kalshi_yes_price"] is None

        # latest_prediction_at should be the max created_at
        assert data["latest_prediction_at"] is not None


class TestDateEndpoint:
    """Tests for GET /api/v1/predictions/{date}."""

    def test_date_endpoint(self, client, mock_pool):
        _mock_pool_fetchall(mock_pool, [SAMPLE_ROW])
        resp = client.get("/api/v1/predictions/2025-06-15")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 1
        assert data["predictions"][0]["home_team"] == "NYY"

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
