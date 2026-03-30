"""Tests for FastAPI lifespan behavior.

Tests cover:
- API fails to start when model artifacts are missing (API-06)
- Lifespan correctly loads artifacts and creates pool
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLifespan:
    """Tests for the lifespan context manager in api/main.py."""

    def test_missing_artifact_fails(self):
        """API-06: App must fail to start if model artifacts are missing."""
        # Patch ARTIFACT_DIR to a nonexistent directory so load_all_artifacts
        # raises FileNotFoundError (without mocking load_all_artifacts itself)
        fake_dir = Path("/nonexistent/artifacts/dir")
        with patch("src.pipeline.inference.ARTIFACT_DIR", fake_dir):
            with pytest.raises(FileNotFoundError):
                from api.main import app
                with TestClient(app):
                    pass  # Should never reach here

    def test_lifespan_loads_artifacts_and_pool(self):
        """Verify lifespan calls load_all_artifacts and get_pool."""
        mock_artifacts = {"lr_team_only": MagicMock()}
        mock_pool = MagicMock()

        with patch("api.main.load_all_artifacts", return_value=mock_artifacts) as mock_load, \
             patch("api.main.get_pool", return_value=mock_pool) as mock_get_pool:
            from api.main import app
            with TestClient(app) as c:
                # Verify artifacts and pool were loaded
                mock_load.assert_called_once()
                mock_get_pool.assert_called_once_with(min_size=2, max_size=5)
                assert app.state.artifacts == mock_artifacts
                assert app.state.pool == mock_pool
