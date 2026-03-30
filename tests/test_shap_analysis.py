"""Tests for SHAP TreeExplainer feature importance module.

Covers requirement MDL-06: SHAP-based feature importance ranking.
"""

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from src.models.shap_analysis import compute_shap_importance


@pytest.fixture
def fitted_xgb_and_data():
    """Train a small XGBClassifier on synthetic data (50 rows, 5 features)."""
    rng = np.random.RandomState(42)
    n = 50
    feature_cols = ['feat_0', 'feat_1', 'feat_2', 'feat_3', 'feat_4']

    X = pd.DataFrame(
        rng.randn(n, len(feature_cols)),
        columns=feature_cols,
    )
    y = pd.Series(rng.randint(0, 2, size=n), name="target")

    model = xgb.XGBClassifier(
        n_estimators=20,
        max_depth=3,
        random_state=42,
        eval_metric='logloss',
    )
    model.fit(X, y, verbose=False)

    return model, X, feature_cols


def test_shap_returns_dataframe(fitted_xgb_and_data):
    """compute_shap_importance returns DataFrame with expected columns."""
    model, X, feature_cols = fitted_xgb_and_data
    result = compute_shap_importance(model, X, feature_cols)

    assert isinstance(result, pd.DataFrame), "Result must be a DataFrame"
    expected_cols = ['feature', 'mean_abs_shap', 'pct_of_total']
    assert list(result.columns) == expected_cols, (
        f"Expected columns {expected_cols}, got {list(result.columns)}"
    )
    assert len(result) == len(feature_cols), (
        f"Expected {len(feature_cols)} rows, got {len(result)}"
    )


def test_shap_feature_names_correct(fitted_xgb_and_data):
    """Output 'feature' column matches input feature_cols exactly."""
    model, X, feature_cols = fitted_xgb_and_data
    result = compute_shap_importance(model, X, feature_cols)

    assert set(result['feature'].tolist()) == set(feature_cols), (
        f"Feature names don't match: {result['feature'].tolist()} vs {feature_cols}"
    )


def test_shap_pct_sums_to_one(fitted_xgb_and_data):
    """pct_of_total values sum to approximately 1.0."""
    model, X, feature_cols = fitted_xgb_and_data
    result = compute_shap_importance(model, X, feature_cols)

    total = result['pct_of_total'].sum()
    assert abs(total - 1.0) < 0.01, (
        f"pct_of_total should sum to ~1.0, got {total}"
    )


def test_shap_sorted_descending(fitted_xgb_and_data):
    """Output is sorted by mean_abs_shap descending."""
    model, X, feature_cols = fitted_xgb_and_data
    result = compute_shap_importance(model, X, feature_cols)

    shap_values = result['mean_abs_shap'].tolist()
    assert shap_values == sorted(shap_values, reverse=True), (
        "Results should be sorted by mean_abs_shap descending"
    )
