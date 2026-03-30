"""Tests for model artifact loading and prediction."""
import math
from unittest.mock import MagicMock

import joblib
import numpy as np
import pytest

from src.pipeline.inference import load_all_artifacts, predict_game, ARTIFACT_NAMES


def _make_picklable_artifact(model_name: str, feature_set: str, feature_cols: list[str]) -> dict:
    """Create a picklable artifact dict for joblib dump/load tests.

    Uses plain dicts instead of MagicMock (which cannot be pickled by joblib).
    """
    return {
        "model": "placeholder_model",
        "calibrator": "placeholder_calibrator",
        "feature_cols": feature_cols,
        "model_name": model_name,
        "feature_set": feature_set,
    }


def _make_fake_artifact(model_name: str, feature_set: str, feature_cols: list[str]) -> dict:
    """Create a fake artifact dict with mock model/calibrator for predict tests."""
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.array([[0.4, 0.6]])
    mock_calibrator = MagicMock()
    mock_calibrator.predict.return_value = np.array([0.58])
    return {
        "model": mock_model,
        "calibrator": mock_calibrator,
        "feature_cols": feature_cols,
        "model_name": model_name,
        "feature_set": feature_set,
    }


def test_load_all_artifacts_success(tmp_path):
    """All 6 artifact files present -- loads successfully."""
    feature_cols_team = ["a", "b"]
    feature_cols_sp = ["a", "b", "c"]
    for name in ARTIFACT_NAMES:
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]  # lr, rf, xgb
        cols = feature_cols_team if fs == "team_only" else feature_cols_sp
        artifact = _make_picklable_artifact(mn, fs, cols)
        joblib.dump(artifact, tmp_path / f"{name}.joblib")

    result = load_all_artifacts(artifact_dir=tmp_path)
    assert len(result) == 6
    for name in ARTIFACT_NAMES:
        assert name in result
        assert "model" in result[name]
        assert "calibrator" in result[name]
        assert "feature_cols" in result[name]
        assert "model_name" in result[name]
        assert "feature_set" in result[name]


def test_load_all_artifacts_missing_file(tmp_path):
    """Only 5 of 6 artifacts present -- raises FileNotFoundError."""
    for name in ARTIFACT_NAMES[:5]:  # Skip the 6th
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]
        artifact = _make_picklable_artifact(mn, fs, ["a", "b"])
        joblib.dump(artifact, tmp_path / f"{name}.joblib")

    with pytest.raises(FileNotFoundError, match="Missing model artifact"):
        load_all_artifacts(artifact_dir=tmp_path)


def test_predict_game_team_only():
    """predict_game with team_only returns lr, rf, xgb predictions."""
    artifacts = {}
    for name in ARTIFACT_NAMES:
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]
        artifacts[name] = _make_fake_artifact(mn, fs, ["a", "b"])

    features = {"a": 1.0, "b": 2.0}
    result = predict_game(artifacts, features, "team_only")

    assert set(result.keys()) == {"lr", "rf", "xgb"}
    for model_name, prob in result.items():
        assert prob == pytest.approx(0.58, abs=0.01)


def test_predict_game_sp_enhanced():
    """predict_game with sp_enhanced returns only sp_enhanced model predictions."""
    artifacts = {}
    for name in ARTIFACT_NAMES:
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]
        cols = ["a", "b"] if fs == "team_only" else ["a", "b", "c"]
        artifacts[name] = _make_fake_artifact(mn, fs, cols)

    features = {"a": 1.0, "b": 2.0, "c": 3.0}
    result = predict_game(artifacts, features, "sp_enhanced")

    assert set(result.keys()) == {"lr", "rf", "xgb"}
    for model_name, prob in result.items():
        assert prob == pytest.approx(0.58, abs=0.01)


def test_predict_game_skips_nan_features():
    """predict_game skips models when features contain NaN."""
    artifacts = {}
    for name in ARTIFACT_NAMES:
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]
        artifacts[name] = _make_fake_artifact(mn, fs, ["a", "b"])

    features = {"a": float("nan"), "b": 2.0}
    result = predict_game(artifacts, features, "team_only")

    assert result == {}


def test_predict_game_clips_extreme_probabilities():
    """predict_game clips calibrated probabilities to [0.01, 0.99]."""
    artifacts = {}
    for name in ARTIFACT_NAMES:
        fs = "team_only" if "team_only" in name else "sp_enhanced"
        mn = name.split("_")[0]
        artifact = _make_fake_artifact(mn, fs, ["a", "b"])
        # Make calibrator return extreme values
        artifact["calibrator"].predict.return_value = np.array([1.05])
        artifacts[name] = artifact

    features = {"a": 1.0, "b": 2.0}
    result = predict_game(artifacts, features, "team_only")

    for model_name, prob in result.items():
        assert prob <= 0.99
        assert prob >= 0.01
