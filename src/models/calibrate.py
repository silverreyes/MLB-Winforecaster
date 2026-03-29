"""Post-hoc isotonic calibration for trained models.

Uses sklearn.isotonic.IsotonicRegression directly instead of the deprecated
CalibratedClassifierCV(cv='prefit'), which was removed in sklearn 1.8.0.

Isotonic calibration is fitted on a held-out calibration season (N-1) and
applied to the test season (N) predictions. Each fold gets an independently
fitted calibrator -- no leakage across folds.
"""

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


def calibrate_model(
    model,
    X_cal: pd.DataFrame,
    y_cal: pd.Series,
    X_test: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply isotonic calibration to a pre-trained model.

    Fits IsotonicRegression on the calibration set's raw probabilities,
    then transforms the test set's raw probabilities.

    Args:
        model: Fitted sklearn Pipeline or estimator with predict_proba.
        X_cal: Calibration features (season N-1).
        y_cal: Calibration labels (season N-1).
        X_test: Test features to produce calibrated predictions for.

    Returns:
        Tuple of (calibrated_test_probs, raw_test_probs).
        Both are 1-D numpy arrays of length len(X_test), values in [0, 1].
    """
    raw_probs_cal = model.predict_proba(X_cal)[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(raw_probs_cal, y_cal.values)

    raw_probs_test = model.predict_proba(X_test)[:, 1]
    cal_probs_test = iso.predict(raw_probs_test)

    return cal_probs_test, raw_probs_test
