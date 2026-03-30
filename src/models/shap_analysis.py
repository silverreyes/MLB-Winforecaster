"""SHAP TreeExplainer wrapper for feature importance ranking.

Uses shap.TreeExplainer to compute per-feature SHAP values for tree-based
models (XGBoost, Random Forest, etc.), then summarizes as mean absolute
SHAP importance with percentage-of-total allocation.
"""

import numpy as np
import pandas as pd
import shap


def compute_shap_importance(
    fitted_model,
    X_train: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """Compute SHAP TreeExplainer feature importance for a fitted tree model.

    Args:
        fitted_model: Fitted XGBClassifier (or any tree model).
        X_train: Training data used for SHAP computation.
        feature_cols: Feature column names matching X_train columns.
    Returns:
        DataFrame with columns ['feature', 'mean_abs_shap', 'pct_of_total'],
        sorted by mean_abs_shap descending.
    """
    explainer = shap.TreeExplainer(fitted_model)
    shap_values = explainer.shap_values(X_train[feature_cols])

    mean_abs = np.abs(shap_values).mean(axis=0)
    total = mean_abs.sum()

    if total == 0:
        pct_of_total = np.zeros_like(mean_abs)
    else:
        pct_of_total = mean_abs / total

    result = pd.DataFrame({
        'feature': feature_cols,
        'mean_abs_shap': mean_abs,
        'pct_of_total': pct_of_total,
    })
    result = result.sort_values('mean_abs_shap', ascending=False).reset_index(drop=True)
    return result
