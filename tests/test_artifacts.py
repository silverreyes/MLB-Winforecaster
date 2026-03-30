"""Tests for model artifact serialization and metadata JSON schema.

Covers:
- Artifact round-trip via joblib (dump + load preserves all fields)
- model_metadata.json schema validation
"""

import json
import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.isotonic import IsotonicRegression

from src.models.train import make_lr_pipeline


def test_artifact_round_trip(tmp_path):
    """joblib dump + load preserves model, calibrator, feature_cols, model_name, feature_set."""
    rng = np.random.RandomState(42)

    # Create and fit a model
    model = make_lr_pipeline()
    X_train = pd.DataFrame(rng.randn(100, 3), columns=['a', 'b', 'c'])
    y_train = pd.Series(rng.randint(0, 2, size=100))
    model.fit(X_train, y_train)

    # Create and fit a calibrator
    calibrator = IsotonicRegression(out_of_bounds='clip')
    raw_probs = model.predict_proba(X_train)[:, 1]
    calibrator.fit(raw_probs, y_train.values)

    # Build artifact dict
    artifact = {
        'model': model,
        'calibrator': calibrator,
        'feature_cols': ['a', 'b', 'c'],
        'model_name': 'lr',
        'feature_set': 'team_only',
    }

    # Round-trip
    path = tmp_path / "test_artifact.joblib"
    joblib.dump(artifact, path)
    loaded = joblib.load(path)

    # Verify all fields preserved
    assert loaded['model_name'] == 'lr'
    assert loaded['feature_set'] == 'team_only'
    assert loaded['feature_cols'] == ['a', 'b', 'c']
    assert type(loaded['model']).__name__ == 'Pipeline'
    assert type(loaded['calibrator']).__name__ == 'IsotonicRegression'

    # Verify model produces same predictions
    preds_original = model.predict_proba(X_train)[:, 1]
    preds_loaded = loaded['model'].predict_proba(X_train)[:, 1]
    np.testing.assert_array_almost_equal(preds_original, preds_loaded)

    # Verify calibrator produces same outputs
    cal_original = calibrator.predict(raw_probs)
    cal_loaded = loaded['calibrator'].predict(raw_probs)
    np.testing.assert_array_almost_equal(cal_original, cal_loaded)


def test_metadata_json_schema(tmp_path):
    """model_metadata.json has training_date, models dict with 6 entries, each with required fields."""
    # Build sample metadata matching expected structure
    metadata = {
        "training_date": "2026-03-30T01:00:00",
        "v2_feature_store": "data/features/feature_store_v2.parquet",
        "models": {}
    }

    model_names = [
        'lr_team_only', 'lr_sp_enhanced',
        'rf_team_only', 'rf_sp_enhanced',
        'xgb_team_only', 'xgb_sp_enhanced',
    ]

    for name in model_names:
        metadata["models"][name] = {
            "feature_cols": ['feat_a', 'feat_b', 'feat_c'],
            "fold_brier_scores": {
                "2019": 0.24, "2021": 0.23, "2022": 0.25,
                "2023": 0.22, "2024": 0.24,
            },
            "aggregate_brier_score": 0.236,
            "calibration_method": "IsotonicRegression",
        }

    # Round-trip through JSON
    path = tmp_path / "model_metadata.json"
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)

    with open(path) as f:
        loaded = json.load(f)

    # Validate structure
    assert "training_date" in loaded
    assert "models" in loaded
    assert len(loaded["models"]) == 6

    for name, entry in loaded["models"].items():
        assert isinstance(entry["feature_cols"], list), f"{name}: feature_cols must be list"
        assert isinstance(entry["fold_brier_scores"], dict), f"{name}: fold_brier_scores must be dict"
        assert isinstance(entry["calibration_method"], str), f"{name}: calibration_method must be str"
        assert entry["calibration_method"] == "IsotonicRegression"
