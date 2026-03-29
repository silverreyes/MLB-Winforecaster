"""Evaluation utilities for backtest results.

Provides Brier score computation (per-fold and aggregate), naive baseline
comparison, calibration curve data extraction, and plotting functions for
reliability diagrams and per-season Brier comparisons.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss


def compute_brier_scores(results_df: pd.DataFrame) -> pd.DataFrame:
    """Compute Brier scores per fold and in aggregate for each model/feature set.

    Args:
        results_df: DataFrame from run_backtest or run_all_models with columns
            model_name, feature_set, fold_test_year, home_win, prob_calibrated.

    Returns:
        DataFrame with columns: model_name, feature_set, fold_test_year,
        brier_score, n_games. Includes per-fold rows and an 'aggregate' row
        for each model/feature_set combination.
    """
    rows = []

    # Per-fold scores
    grouped = results_df.groupby(['model_name', 'feature_set', 'fold_test_year'])
    for (model_name, feature_set, fold_year), group in grouped:
        brier = brier_score_loss(group['home_win'], group['prob_calibrated'])
        rows.append({
            'model_name': model_name,
            'feature_set': feature_set,
            'fold_test_year': fold_year,
            'brier_score': round(brier, 4),
            'n_games': len(group),
        })

    # Aggregate scores (all folds combined per model+feature_set)
    agg_grouped = results_df.groupby(['model_name', 'feature_set'])
    for (model_name, feature_set), group in agg_grouped:
        brier = brier_score_loss(group['home_win'], group['prob_calibrated'])
        rows.append({
            'model_name': model_name,
            'feature_set': feature_set,
            'fold_test_year': 'aggregate',
            'brier_score': round(brier, 4),
            'n_games': len(group),
        })

    return pd.DataFrame(rows)


def compute_naive_baseline_brier(df: pd.DataFrame) -> dict:
    """Compute Brier score for a naive baseline predicting historical home win rate.

    The naive baseline always predicts P(home_win) = historical home win rate,
    which is approximately 0.535 in MLB data. This provides a floor that any
    useful model should beat.

    Args:
        df: Filtered feature matrix (same rows as backtest -- after
            rolling_ops_diff NaN drop).

    Returns:
        Dict with model_name, feature_set, fold_test_year, brier_score,
        n_games, home_win_rate.
    """
    home_win_rate = df['home_win'].mean()
    brier = brier_score_loss(df['home_win'], [home_win_rate] * len(df))

    return {
        "model_name": "naive_baseline",
        "feature_set": "n/a",
        "fold_test_year": "aggregate",
        "brier_score": round(brier, 4),
        "n_games": len(df),
        "home_win_rate": round(home_win_rate, 4),
    }


def get_calibration_data(
    results_df: pd.DataFrame,
    model_name: str,
    feature_set: str,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract calibration curve data for a specific model and feature set.

    Args:
        results_df: Full results DataFrame with prob_calibrated and home_win.
        model_name: Model to filter (e.g., 'lr', 'rf', 'xgb').
        feature_set: Feature set to filter (e.g., 'full', 'core').
        n_bins: Number of bins for the calibration curve.

    Returns:
        Tuple of (fraction_of_positives, mean_predicted_value), each a 1-D
        numpy array with length <= n_bins.
    """
    mask = (results_df['model_name'] == model_name) & (
        results_df['feature_set'] == feature_set
    )
    y_true = results_df.loc[mask, 'home_win']
    y_prob = results_df.loc[mask, 'prob_calibrated']

    fraction_positive, mean_predicted = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy='uniform'
    )
    return fraction_positive, mean_predicted


def plot_calibration_curves(
    results_df: pd.DataFrame,
    feature_set: str = 'full',
    n_bins: int = 10,
) -> plt.Figure:
    """Plot reliability diagrams for all 3 models on the same axes.

    Args:
        results_df: Full results DataFrame from run_all_models.
        feature_set: Which feature set to plot ('full' or 'core').
        n_bins: Number of bins for calibration curves.

    Returns:
        Matplotlib Figure object (does NOT call plt.show()).
    """
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')

    model_names = ['lr', 'rf', 'xgb']
    for name in model_names:
        fraction_positive, mean_predicted = get_calibration_data(
            results_df, name, feature_set, n_bins
        )
        ax.plot(mean_predicted, fraction_positive, 's-', label=name)

    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Fraction of positives')
    ax.set_title(f'Calibration Curves - {feature_set} features')
    ax.legend()

    return fig


def plot_brier_by_season(
    brier_df: pd.DataFrame,
    feature_set: str = 'full',
) -> plt.Figure:
    """Plot per-season Brier scores as a grouped bar chart.

    Args:
        brier_df: DataFrame from compute_brier_scores.
        feature_set: Which feature set to filter.

    Returns:
        Matplotlib Figure object.
    """
    # Filter to requested feature set, exclude aggregate rows
    mask = (brier_df['feature_set'] == feature_set) & (
        brier_df['fold_test_year'] != 'aggregate'
    )
    plot_df = brier_df[mask].copy()

    model_names = sorted(plot_df['model_name'].unique())
    seasons = sorted(plot_df['fold_test_year'].unique())

    fig, ax = plt.subplots(figsize=(10, 6))
    n_models = len(model_names)
    bar_width = 0.8 / n_models
    x = np.arange(len(seasons))

    for i, model_name in enumerate(model_names):
        model_data = plot_df[plot_df['model_name'] == model_name]
        # Align by season order
        scores = []
        for season in seasons:
            row = model_data[model_data['fold_test_year'] == season]
            scores.append(row['brier_score'].values[0] if len(row) > 0 else 0)
        ax.bar(x + i * bar_width, scores, bar_width, label=model_name)

    ax.set_xlabel('Season')
    ax.set_ylabel('Brier Score')
    ax.set_title(f'Brier Score by Season - {feature_set} features')
    ax.set_xticks(x + bar_width * (n_models - 1) / 2)
    ax.set_xticklabels([str(s) for s in seasons])
    ax.legend()

    return fig
