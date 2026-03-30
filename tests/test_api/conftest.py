"""Shared test fixtures for API tests.

Provides a FastAPI TestClient with mocked DB pool and model artifacts,
so tests run without a real Postgres database.
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_artifacts():
    """Return a mock artifacts dict matching load_all_artifacts() shape."""
    names = [
        "lr_team_only", "lr_sp_enhanced",
        "rf_team_only", "rf_sp_enhanced",
        "xgb_team_only", "xgb_sp_enhanced",
    ]
    return {
        name: {
            "model": MagicMock(),
            "calibrator": MagicMock(),
            "feature_cols": [],
            "model_name": name.split("_")[0],
            "feature_set": "_".join(name.split("_")[1:]),
        }
        for name in names
    }


@pytest.fixture
def mock_pool():
    """Return a mock ConnectionPool."""
    return MagicMock()


@pytest.fixture
def client(mock_artifacts, mock_pool):
    """Create a TestClient with mocked lifespan dependencies."""
    with patch("api.main.load_all_artifacts", return_value=mock_artifacts), \
         patch("api.main.get_pool", return_value=mock_pool):
        from api.main import app
        with TestClient(app) as c:
            yield c
