"""Tests for walk-forward fold generation, Brier score computation, and results schema.

Covers requirements EVAL-01, EVAL-02, EVAL-04:
- Walk-forward fold generator produces correct splits (no overlap)
- 2020 never appears as test year
- Early-season NaN rows excluded from all splits
- Fold map has correct structure
- Brier score computed correctly per fold
- Results DataFrame has required schema
"""

import numpy as np
import pandas as pd
import pytest

from src.models.backtest import FOLD_MAP, generate_folds, run_backtest
from src.models.evaluate import compute_brier_scores
from src.models.feature_sets import FULL_FEATURE_COLS, META_COLS
from src.models.train import make_lr_pipeline


@pytest.fixture
def synthetic_feature_matrix():
    """Build a synthetic feature matrix with 1000 rows (100 per season 2015-2024).

    Simulates the real feature matrix structure:
    - All META_COLS + all FULL_FEATURE_COLS
    - Sequential dates within each season
    - Cycling team names
    - Random targets and feature values
    - First 5 rows per season have NaN rolling_ops_diff (early-season games)
    """
    rng = np.random.RandomState(42)
    rows_per_season = 100
    seasons = list(range(2015, 2025))
    n_total = rows_per_season * len(seasons)

    home_teams = ['NYY', 'BOS', 'LAD', 'CHC', 'HOU']
    away_teams = ['TBR', 'BAL', 'SFG', 'MIL', 'OAK']

    records = []
    for season in seasons:
        dates = pd.date_range(f"{season}-04-01", periods=rows_per_season, freq='2D')
        for i in range(rows_per_season):
            record = {
                'season': season,
                'game_date': dates[i],
                'home_team': home_teams[i % len(home_teams)],
                'away_team': away_teams[i % len(away_teams)],
                'home_win': rng.randint(0, 2),
            }
            # Feature columns
            for col in FULL_FEATURE_COLS:
                if col == 'is_home':
                    record[col] = 1
                else:
                    record[col] = rng.randn()

            # First 5 rows per season: NaN rolling_ops_diff (early-season)
            if i < 5:
                record['rolling_ops_diff'] = np.nan

            records.append(record)

    df = pd.DataFrame(records)
    return df


def test_fold_map_structure():
    """EVAL-01: FOLD_MAP has 5 entries with correct test and calibration years."""
    assert len(FOLD_MAP) == 5, f"Expected 5 folds, got {len(FOLD_MAP)}"

    test_years = [fold[0] for fold in FOLD_MAP]
    cal_years = [fold[2] for fold in FOLD_MAP]

    assert test_years == [2019, 2021, 2022, 2023, 2024], (
        f"Test years incorrect: {test_years}"
    )
    assert cal_years == [2018, 2020, 2021, 2022, 2023], (
        f"Calibration years incorrect: {cal_years}"
    )


def test_fold_splits_no_overlap(synthetic_feature_matrix):
    """EVAL-01: No game_date overlaps between train/test or cal/test within a fold."""
    folds = generate_folds(synthetic_feature_matrix)
    assert len(folds) == 5, f"Expected 5 folds, got {len(folds)}"

    for i, (train_df, cal_df, test_df) in enumerate(folds):
        # No index overlap between train and test
        train_idx = set(train_df.index)
        test_idx = set(test_df.index)
        cal_idx = set(cal_df.index)

        assert len(train_idx & test_idx) == 0, (
            f"Fold {i}: train/test index overlap detected"
        )
        assert len(cal_idx & test_idx) == 0, (
            f"Fold {i}: cal/test index overlap detected"
        )


def test_2020_not_test_year(synthetic_feature_matrix):
    """EVAL-01: No fold has any test row from season 2020."""
    folds = generate_folds(synthetic_feature_matrix)

    for i, (_, _, test_df) in enumerate(folds):
        seasons_in_test = test_df['season'].unique()
        assert 2020 not in seasons_in_test, (
            f"Fold {i}: season 2020 found in test set"
        )


def test_nan_rows_excluded(synthetic_feature_matrix):
    """EVAL-01: No split contains rows where rolling_ops_diff is NaN."""
    folds = generate_folds(synthetic_feature_matrix)

    for i, (train_df, cal_df, test_df) in enumerate(folds):
        assert train_df['rolling_ops_diff'].isna().sum() == 0, (
            f"Fold {i}: NaN found in train rolling_ops_diff"
        )
        assert cal_df['rolling_ops_diff'].isna().sum() == 0, (
            f"Fold {i}: NaN found in cal rolling_ops_diff"
        )
        assert test_df['rolling_ops_diff'].isna().sum() == 0, (
            f"Fold {i}: NaN found in test rolling_ops_diff"
        )


def test_brier_score_per_fold():
    """EVAL-02: compute_brier_scores returns correct DataFrame with valid Brier values."""
    rng = np.random.RandomState(42)

    # Create synthetic results with known structure
    results = []
    for year in [2019, 2021, 2022, 2023, 2024]:
        n_games = 100
        results.extend([{
            'model_name': 'lr',
            'feature_set': 'full',
            'fold_test_year': year,
            'home_win': rng.randint(0, 2),
            'prob_calibrated': rng.uniform(0.3, 0.7),
        } for _ in range(n_games)])

    results_df = pd.DataFrame(results)
    brier_df = compute_brier_scores(results_df)

    # Check required columns exist
    required_cols = ['model_name', 'feature_set', 'fold_test_year', 'brier_score', 'n_games']
    for col in required_cols:
        assert col in brier_df.columns, f"Missing column: {col}"

    # Check Brier scores are valid floats in [0, 1]
    per_fold = brier_df[brier_df['fold_test_year'] != 'aggregate']
    assert len(per_fold) == 5, f"Expected 5 per-fold rows, got {len(per_fold)}"
    assert all(0 <= s <= 1 for s in per_fold['brier_score']), "Brier scores must be in [0, 1]"

    # Check aggregate row exists
    agg = brier_df[brier_df['fold_test_year'] == 'aggregate']
    assert len(agg) == 1, f"Expected 1 aggregate row, got {len(agg)}"


def test_results_schema(synthetic_feature_matrix):
    """EVAL-04: run_backtest output has all required columns for Phase 4 integration."""
    # Use subset of features for speed
    feature_subset = FULL_FEATURE_COLS[:5]

    results_df = run_backtest(
        synthetic_feature_matrix,
        make_lr_pipeline,
        'lr',
        feature_subset,
        'test_set',
        is_xgb=False,
    )

    required_cols = [
        'game_date', 'home_team', 'away_team', 'season', 'home_win',
        'model_name', 'feature_set', 'fold_test_year',
        'prob_calibrated', 'prob_raw',
    ]

    for col in required_cols:
        assert col in results_df.columns, f"Missing required column: {col}"

    # Verify we got results from all 5 folds
    fold_years = sorted(results_df['fold_test_year'].unique())
    assert fold_years == [2019, 2021, 2022, 2023, 2024], (
        f"Expected test years [2019, 2021, 2022, 2023, 2024], got {fold_years}"
    )

    # Verify probabilities are valid
    assert results_df['prob_calibrated'].between(0, 1).all(), "cal probs must be in [0, 1]"
    assert results_df['prob_raw'].between(0, 1).all(), "raw probs must be in [0, 1]"

    # Verify feature_set_name passed through
    assert (results_df['feature_set'] == 'test_set').all(), "feature_set should be 'test_set'"
