"""Tests for health API endpoint.

Tests cover:
- GET /api/v1/health returns pipeline status data
"""

from unittest.mock import patch


SAMPLE_HEALTH = {
    "status": "healthy",
    "last_pipeline_runs": {
        "pre_lineup": {"status": "success"},
    },
    "checked_at": "2025-06-15T18:00:00Z",
}


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_endpoint(self, client):
        with patch("api.routes.health.get_health_data", return_value=SAMPLE_HEALTH):
            resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "pre_lineup" in data["last_pipeline_runs"]
        assert data["checked_at"] == "2025-06-15T18:00:00Z"
