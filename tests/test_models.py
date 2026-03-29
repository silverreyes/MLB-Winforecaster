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
