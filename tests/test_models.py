"""Tests for model factory functions, isotonic calibration, and calibration curves.

Covers requirements MODEL-01 through MODEL-04 and EVAL-03:
- LR pipeline trains and produces valid probabilities
- RF pipeline trains and produces valid probabilities
- XGBoost trains with early stopping and handles NaN
- Isotonic calibration produces probabilities in [0,1]
- Calibration curve data has correct output shape
"""

import numpy as np
import pandas as pd
import pytest

from src.models.calibrate import calibrate_model
from src.models.evaluate import get_calibration_data
from src.models.train import make_lr_pipeline, make_rf_pipeline, make_xgb_model


@pytest.fixture
def synthetic_train_data():
    """Create synthetic training data: 200 rows, 5 features, binary target.

    Column 0 has ~10% NaN values sprinkled in to test imputation handling.
    """
    rng = np.random.RandomState(42)
    n_rows = 200
    n_features = 5

    X = pd.DataFrame(
        rng.randn(n_rows, n_features),
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    # Sprinkle NaN in first column (~10% of rows)
    nan_idx = rng.choice(n_rows, size=int(n_rows * 0.1), replace=False)
    X.iloc[nan_idx, 0] = np.nan

    y = pd.Series(rng.randint(0, 2, size=n_rows), name="target")

    return X, y


def test_lr_pipeline_trains(synthetic_train_data):
    """MODEL-01: LR pipeline fits on synthetic data, produces valid probabilities."""
    X, y = synthetic_train_data
    model = make_lr_pipeline()
    model.fit(X, y)

    proba = model.predict_proba(X)
    assert proba.shape == (len(X), 2), f"Expected shape ({len(X)}, 2), got {proba.shape}"
    assert np.all(proba >= 0) and np.all(proba <= 1), "Probabilities must be in [0, 1]"


def test_rf_pipeline_trains(synthetic_train_data):
    """MODEL-02: RF pipeline fits on synthetic data, produces valid probabilities."""
    X, y = synthetic_train_data
    model = make_rf_pipeline()
    model.fit(X, y)

    proba = model.predict_proba(X)
    assert proba.shape == (len(X), 2), f"Expected shape ({len(X)}, 2), got {proba.shape}"
    assert np.all(proba >= 0) and np.all(proba <= 1), "Probabilities must be in [0, 1]"


def test_xgb_early_stopping():
    """MODEL-03: XGBoost trains with early stopping and handles NaN natively."""
    rng = np.random.RandomState(42)
    n_rows = 200
    n_features = 5

    X = pd.DataFrame(
        rng.randn(n_rows, n_features),
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    # Insert NaN values to verify native NaN handling
    X.iloc[10:20, 0] = np.nan
    X.iloc[50:55, 2] = np.nan

    y = pd.Series(rng.randint(0, 2, size=n_rows), name="target")

    # Split 80/20 for early stopping
    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    model = make_xgb_model()
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    proba = model.predict_proba(X)
    assert proba.shape == (len(X), 2), f"Expected shape ({len(X)}, 2), got {proba.shape}"
    assert np.all(proba >= 0) and np.all(proba <= 1), "Probabilities must be in [0, 1]"


def test_isotonic_calibration(synthetic_train_data):
    """MODEL-04: calibrate_model returns valid (cal_probs, raw_probs) tuple."""
    X, y = synthetic_train_data

    # Split into train, calibration, and test
    X_train, X_cal, X_test = X.iloc[:120], X.iloc[120:160], X.iloc[160:]
    y_train, y_cal = y.iloc[:120], y.iloc[120:160]

    # Train a base model
    model = make_lr_pipeline()
    model.fit(X_train, y_train)

    # Calibrate and get predictions
    cal_probs, raw_probs = calibrate_model(model, X_cal, y_cal, X_test)

    assert isinstance(cal_probs, np.ndarray), "cal_probs must be ndarray"
    assert isinstance(raw_probs, np.ndarray), "raw_probs must be ndarray"
    assert len(cal_probs) == len(X_test), "cal_probs length must match X_test"
    assert len(raw_probs) == len(X_test), "raw_probs length must match X_test"
    assert np.all(cal_probs >= 0) and np.all(cal_probs <= 1), "cal_probs must be in [0, 1]"
    assert np.all(raw_probs >= 0) and np.all(raw_probs <= 1), "raw_probs must be in [0, 1]"


def test_calibration_curve_output():
    """EVAL-03: get_calibration_data returns correctly shaped calibration data."""
    rng = np.random.RandomState(42)
    n_games = 500
    n_bins = 10

    # Create synthetic results DataFrame
    results_df = pd.DataFrame({
        'model_name': ['lr'] * n_games,
        'feature_set': ['full'] * n_games,
        'home_win': rng.randint(0, 2, size=n_games),
        'prob_calibrated': rng.uniform(0.2, 0.8, size=n_games),
    })

    fraction_positive, mean_predicted = get_calibration_data(
        results_df, 'lr', 'full', n_bins=n_bins
    )

    assert isinstance(fraction_positive, np.ndarray), "fraction_positive must be ndarray"
    assert isinstance(mean_predicted, np.ndarray), "mean_predicted must be ndarray"
    assert len(fraction_positive) == len(mean_predicted), "Arrays must have same length"
    assert len(fraction_positive) <= n_bins, f"Length must be <= {n_bins}"


# ===========================================================================
# predict_2025 — unit tests (MARKET-02)
# ===========================================================================

from src.models.predict import predict_2025, TRAIN_SEASONS, CAL_SEASON, TEST_SEASON


def test_predict_2025_constants():
    """Verify 2025 fold configuration constants."""
    assert TRAIN_SEASONS == list(range(2015, 2024))
    assert CAL_SEASON == 2024
    assert TEST_SEASON == 2025


@pytest.fixture
def synthetic_feature_matrix():
    """Create synthetic feature matrix spanning seasons 2015-2025.

    Generates 100 rows per season (1100 total) with core features
    and metadata columns matching the real feature matrix schema.
    """
    rng = np.random.RandomState(42)
    rows = []
    for season in range(2015, 2026):
        for i in range(100):
            row = {
                "season": season,
                "game_date": pd.Timestamp(f"{season}-06-{(i % 28) + 1:02d}"),
                "home_team": "NYY",
                "away_team": "BOS",
                "home_win": rng.randint(0, 2),
                "rolling_ops_diff": rng.normal(0, 0.05),
                "sp_fip_diff": rng.normal(0, 0.5),
                "sp_xfip_diff": rng.normal(0, 0.5),
                "sp_k_pct_diff": rng.normal(0, 0.03),
                "sp_siera_diff": rng.normal(0, 0.5),
                "team_woba_diff": rng.normal(0, 0.02),
                "team_ops_diff": rng.normal(0, 0.03),
                "pyth_win_pct_diff": rng.normal(0, 0.05),
                "bullpen_era_diff": rng.normal(0, 0.5),
                "bullpen_fip_diff": rng.normal(0, 0.5),
                "is_home": 1,
                "park_factor": 1.0 + rng.normal(0, 0.05),
                "log5_home_wp": 0.5 + rng.normal(0, 0.05),
            }
            rows.append(row)
    # Set first 10 rows of each season to NaN rolling_ops_diff (warmup)
    df = pd.DataFrame(rows)
    for season in range(2015, 2026):
        mask = df["season"] == season
        idx = df[mask].index[:10]
        df.loc[idx, "rolling_ops_diff"] = np.nan
    return df


def test_predict_2025_schema(synthetic_feature_matrix):
    """MARKET-02: predict_2025 output has correct column schema."""
    result = predict_2025(synthetic_feature_matrix)
    expected_cols = {
        "game_date", "home_team", "away_team", "season", "home_win",
        "model_name", "feature_set", "fold_test_year", "prob_calibrated", "prob_raw",
    }
    assert set(result.columns) == expected_cols


def test_predict_2025_core_feature_set(synthetic_feature_matrix):
    """MARKET-02: All rows use core feature set (xwoba_diff excluded)."""
    result = predict_2025(synthetic_feature_matrix)
    assert (result["feature_set"] == "core").all()


def test_predict_2025_fold_year(synthetic_feature_matrix):
    """MARKET-02: All rows have fold_test_year=2025."""
    result = predict_2025(synthetic_feature_matrix)
    assert (result["fold_test_year"] == 2025).all()


def test_predict_2025_three_models(synthetic_feature_matrix):
    """MARKET-02: Output contains predictions from all 3 models."""
    result = predict_2025(synthetic_feature_matrix)
    assert set(result["model_name"].unique()) == {"lr", "rf", "xgb"}


def test_predict_2025_probs_valid(synthetic_feature_matrix):
    """MARKET-02: All probabilities are in [0, 1]."""
    result = predict_2025(synthetic_feature_matrix)
    assert (result["prob_calibrated"] >= 0).all()
    assert (result["prob_calibrated"] <= 1).all()
    assert (result["prob_raw"] >= 0).all()
    assert (result["prob_raw"] <= 1).all()


def test_predict_2025_season_only_2025(synthetic_feature_matrix):
    """MARKET-02: Only season 2025 appears in output (no train/cal leakage)."""
    result = predict_2025(synthetic_feature_matrix)
    assert (result["season"] == 2025).all()
