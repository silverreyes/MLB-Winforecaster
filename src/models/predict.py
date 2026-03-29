"""Single-fold prediction for 2025 season (Phase 4 Kalshi comparison track).

Trains on 2015-2023, calibrates on 2024, predicts 2025 -- core feature set only.
Produces predictions with same schema as backtest_results.parquet.
"""
import logging
import pandas as pd
from src.models.train import make_lr_pipeline, make_rf_pipeline, make_xgb_model
from src.models.calibrate import calibrate_model
from src.models.feature_sets import CORE_FEATURE_COLS, TARGET_COL

logger = logging.getLogger(__name__)

TRAIN_SEASONS = list(range(2015, 2024))  # 2015-2023
CAL_SEASON = 2024
TEST_SEASON = 2025


def predict_2025(df: pd.DataFrame) -> pd.DataFrame:
    """Run 3 models on the 2025 fold, return predictions DataFrame.

    Args:
        df: Full feature matrix covering seasons 2015-2025 with columns
            from CORE_FEATURE_COLS plus META_COLS (season, home_win,
            game_date, home_team, away_team) and rolling_ops_diff.

    Returns:
        DataFrame with columns: game_date, home_team, away_team, season,
        home_win, model_name, feature_set, fold_test_year, prob_calibrated,
        prob_raw. One row per (game, model).
    """
    # Filter NaN rolling_ops_diff (same pattern as backtest.py:generate_folds)
    df_clean = df[df["rolling_ops_diff"].notna()].copy()
    train_df = df_clean[df_clean["season"].isin(TRAIN_SEASONS)]
    cal_df = df_clean[df_clean["season"] == CAL_SEASON]
    test_df = df_clean[df_clean["season"] == TEST_SEASON]

    logger.info(
        "2025 fold: %d train, %d cal, %d test rows",
        len(train_df), len(cal_df), len(test_df),
    )

    models = [
        ("lr", make_lr_pipeline, False),
        ("rf", make_rf_pipeline, False),
        ("xgb", make_xgb_model, True),
    ]

    results = []
    for model_name, factory, is_xgb in models:
        logger.info("Training %s for 2025 fold...", model_name)
        model = factory()

        X_train = train_df[CORE_FEATURE_COLS]
        y_train = train_df[TARGET_COL]
        X_cal = cal_df[CORE_FEATURE_COLS]
        y_cal = cal_df[TARGET_COL]
        X_test = test_df[CORE_FEATURE_COLS]

        if is_xgb:
            n_val = int(len(X_train) * 0.2)
            X_tr = X_train.iloc[:-n_val]
            y_tr = y_train.iloc[:-n_val]
            X_val = X_train.iloc[-n_val:]
            y_val = y_train.iloc[-n_val:]
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        else:
            model.fit(X_train, y_train)

        cal_probs, raw_probs = calibrate_model(model, X_cal, y_cal, X_test)

        for i, (_, row) in enumerate(test_df.iterrows()):
            results.append({
                "game_date": row["game_date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "season": row["season"],
                "home_win": row["home_win"],
                "model_name": model_name,
                "feature_set": "core",
                "fold_test_year": TEST_SEASON,
                "prob_calibrated": cal_probs[i],
                "prob_raw": raw_probs[i],
            })

    return pd.DataFrame(results)
