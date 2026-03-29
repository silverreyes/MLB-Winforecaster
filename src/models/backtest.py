"""Walk-forward backtest loop for MLB win probability models.

Provides the 5-fold walk-forward split structure, fold generation,
and the main backtest orchestrator that trains, calibrates, and evaluates
each model across all folds.

Key design decisions:
- 2020 is never a test year (60-game season, statistically unreliable for Brier)
- 2020 IS included in training sets (contributes signal)
- Early-season NaN rows (rolling_ops_diff is NaN) dropped from all splits
- XGBoost uses last 20% of training window for early stopping validation
- No hardcoded game count assertions (2020 calibration has ~891 games)
"""

import logging

import pandas as pd

from src.models.calibrate import calibrate_model
from src.models.feature_sets import (
    CORE_FEATURE_COLS,
    FULL_FEATURE_COLS,
    TARGET_COL,
)
from src.models.train import make_lr_pipeline, make_rf_pipeline, make_xgb_model

logger = logging.getLogger(__name__)

# Explicit 5-fold walk-forward structure
# (test_year, train_seasons, calibration_season)
FOLD_MAP = [
    (2019, list(range(2015, 2018)), 2018),   # train 2015-2017, cal 2018, test 2019
    (2021, list(range(2015, 2020)), 2020),   # train 2015-2019, cal 2020, test 2021
    (2022, list(range(2015, 2021)), 2021),   # train 2015-2020, cal 2021, test 2022
    (2023, list(range(2015, 2022)), 2022),   # train 2015-2021, cal 2022, test 2023
    (2024, list(range(2015, 2023)), 2023),   # train 2015-2022, cal 2023, test 2024
]


def generate_folds(
    df: pd.DataFrame,
) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Generate (train_df, cal_df, test_df) splits for each fold.

    Drops early-season NaN rows (where rolling_ops_diff is NaN) from all
    splits before filtering by season.

    Args:
        df: Full feature matrix with 'season' and 'rolling_ops_diff' columns.

    Returns:
        List of 5 tuples, each containing (train_df, cal_df, test_df).
    """
    df_clean = df[df["rolling_ops_diff"].notna()].copy()
    folds = []
    for test_year, train_years, cal_year in FOLD_MAP:
        train_df = df_clean[df_clean["season"].isin(train_years)]
        cal_df = df_clean[df_clean["season"] == cal_year]
        test_df = df_clean[df_clean["season"] == test_year]
        folds.append((train_df, cal_df, test_df))
    return folds


def run_backtest(
    df: pd.DataFrame,
    model_factory,
    model_name: str,
    feature_cols: list[str],
    feature_set_name: str,
    is_xgb: bool = False,
) -> pd.DataFrame:
    """Run walk-forward backtest for one model across all folds.

    For each fold:
    1. Create a fresh model via model_factory()
    2. Train on the training window (with early stopping for XGBoost)
    3. Calibrate on the calibration season via isotonic regression
    4. Record per-game predictions for the test season

    Args:
        df: Full feature matrix (will be cleaned of NaN rows internally).
        model_factory: Callable that returns a fresh model instance.
        model_name: Label for this model (e.g., 'lr', 'rf', 'xgb').
        feature_cols: List of feature column names to use.
        feature_set_name: Explicit label (e.g., 'full' or 'core').
        is_xgb: If True, use early stopping with temporal validation split.

    Returns:
        DataFrame with per-game predictions across all folds.
    """
    folds = generate_folds(df)
    results = []

    for fold_idx, (train_df, cal_df, test_df) in enumerate(folds):
        test_year = FOLD_MAP[fold_idx][0]

        X_train = train_df[feature_cols]
        y_train = train_df[TARGET_COL]
        X_cal = cal_df[feature_cols]
        y_cal = cal_df[TARGET_COL]
        X_test = test_df[feature_cols]

        # Train base model
        model = model_factory()
        if is_xgb:
            # Early stopping on last 20% of training window (temporal split)
            n_val = int(len(X_train) * 0.2)
            X_tr = X_train.iloc[:-n_val]
            y_tr = y_train.iloc[:-n_val]
            X_val = X_train.iloc[-n_val:]
            y_val = y_train.iloc[-n_val:]
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
        else:
            model.fit(X_train, y_train)

        # Calibrate on season N-1, predict on season N
        cal_probs, raw_probs = calibrate_model(model, X_cal, y_cal, X_test)

        # Collect per-game results
        for i, (_, row) in enumerate(test_df.iterrows()):
            results.append({
                'game_date': row['game_date'],
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'season': row['season'],
                'home_win': row['home_win'],
                'model_name': model_name,
                'feature_set': feature_set_name,
                'fold_test_year': test_year,
                'prob_calibrated': cal_probs[i],
                'prob_raw': raw_probs[i],
            })

    return pd.DataFrame(results)


def run_all_models(df: pd.DataFrame) -> pd.DataFrame:
    """Run backtest for all 6 model/feature-set combinations.

    Combinations: 3 models (LR, RF, XGBoost) x 2 feature sets (full, core).
    Logs progress before each run.

    Args:
        df: Full feature matrix.

    Returns:
        Concatenated DataFrame with results from all 6 runs.
    """
    combinations = [
        ('lr', make_lr_pipeline, FULL_FEATURE_COLS, 'full', False),
        ('lr', make_lr_pipeline, CORE_FEATURE_COLS, 'core', False),
        ('rf', make_rf_pipeline, FULL_FEATURE_COLS, 'full', False),
        ('rf', make_rf_pipeline, CORE_FEATURE_COLS, 'core', False),
        ('xgb', make_xgb_model, FULL_FEATURE_COLS, 'full', True),
        ('xgb', make_xgb_model, CORE_FEATURE_COLS, 'core', True),
    ]

    all_results = []
    for model_name, factory, feature_cols, feature_set_name, is_xgb in combinations:
        logger.info(f"Running {model_name} on {feature_set_name}...")
        result_df = run_backtest(
            df, factory, model_name, feature_cols, feature_set_name, is_xgb
        )
        all_results.append(result_df)

    return pd.concat(all_results, ignore_index=True)
