"""Tests for src/pipeline/health.py.

All tests mock get_latest_pipeline_runs -- no real DB calls.
"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from src.pipeline.health import get_health_data


def _make_run(version, status="success", games=8):
    """Create a mock pipeline run dict."""
    return {
        "prediction_version": version,
        "run_date": "2025-07-15",
        "status": status,
        "run_finished_at": datetime(2025, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
        "games_processed": games,
    }


@patch("src.pipeline.health.get_latest_pipeline_runs")
def test_health_data_all_success(mock_runs):
    """All runs successful => healthy."""
    mock_runs.return_value = [
        _make_run("pre_lineup"),
        _make_run("post_lineup"),
        _make_run("confirmation"),
    ]
    pool = MagicMock()
    result = get_health_data(pool)
    assert result["status"] == "healthy"
    assert len(result["last_pipeline_runs"]) == 3


@patch("src.pipeline.health.get_latest_pipeline_runs")
def test_health_data_one_failed(mock_runs):
    """One run failed => degraded."""
    mock_runs.return_value = [
        _make_run("pre_lineup"),
        _make_run("post_lineup", status="failed"),
        _make_run("confirmation"),
    ]
    pool = MagicMock()
    result = get_health_data(pool)
    assert result["status"] == "degraded"


@patch("src.pipeline.health.get_latest_pipeline_runs")
def test_health_data_no_runs(mock_runs):
    """No runs => unhealthy."""
    mock_runs.return_value = []
    pool = MagicMock()
    result = get_health_data(pool)
    assert result["status"] == "unhealthy"


@patch("src.pipeline.health.get_latest_pipeline_runs")
def test_health_data_db_error(mock_runs):
    """DB error => unhealthy with error key."""
    mock_runs.side_effect = Exception("connection refused")
    pool = MagicMock()
    result = get_health_data(pool)
    assert result["status"] == "unhealthy"
    assert "error" in result
    assert "connection refused" in result["error"]


@patch("src.pipeline.health.get_latest_pipeline_runs")
def test_health_data_structure(mock_runs):
    """Result has required top-level keys."""
    mock_runs.return_value = [_make_run("pre_lineup")]
    pool = MagicMock()
    result = get_health_data(pool)
    assert "status" in result
    assert "last_pipeline_runs" in result
    assert "checked_at" in result
    # checked_at should be ISO8601
    datetime.fromisoformat(result["checked_at"])
