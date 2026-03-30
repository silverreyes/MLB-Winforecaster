"""Tests for accuracy API endpoint.

Tests cover:
- GET /api/v1/results/accuracy with valid metadata file
- GET /api/v1/results/accuracy when metadata file is missing
"""

import json
from unittest.mock import patch, mock_open


SAMPLE_METADATA = {
    "training_date": "2026-03-29T19:26:50.440602",
    "models": {
        "lr_team_only": {"aggregate_brier_score": 0.2374},
        "lr_sp_enhanced": {"aggregate_brier_score": 0.2331},
        "rf_team_only": {"aggregate_brier_score": 0.2383},
        "rf_sp_enhanced": {"aggregate_brier_score": 0.2342},
        "xgb_team_only": {"aggregate_brier_score": 0.2397},
        "xgb_sp_enhanced": {"aggregate_brier_score": 0.2349},
    },
}


class TestAccuracyEndpoint:
    """Tests for GET /api/v1/results/accuracy."""

    def test_accuracy_endpoint(self, client):
        m = mock_open(read_data=json.dumps(SAMPLE_METADATA))
        with patch("builtins.open", m):
            resp = client.get("/api/v1/results/accuracy")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) == 6
        assert "lr_sp_enhanced" in data["models"]
        assert data["training_date"] == "2026-03-29T19:26:50.440602"

    def test_accuracy_not_found(self, client):
        with patch("builtins.open", side_effect=FileNotFoundError):
            resp = client.get("/api/v1/results/accuracy")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
