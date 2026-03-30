"""Tests for v2 walk-forward backtest infrastructure.

Covers v2 model combinations (3 models x 2 feature sets = 6 combos),
V2_FOLD_MAP structure, run_all_v2_models schema, and predict_2025_v2.
"""

import numpy as np
import pandas as pd
import pytest

from src.models.feature_sets import (
    SP_ENHANCED_PRUNED_COLS,
    TEAM_ONLY_FEATURE_COLS,
    FULL_FEATURE_COLS,
)
from src.models.train import make_lr_pipeline


@pytest.fixture
def synthetic_v2_feature_matrix():
    """Build a synthetic feature matrix spanning 2015-2025 with all v2 columns.

    Includes all columns from SP_ENHANCED_PRUNED_COLS and TEAM_ONLY_FEATURE_COLS
    (union), plus META_COLS and rolling_ops_diff. 100 rows per season.
    """
    rng = np.random.RandomState(42)
    rows_per_season = 100
    seasons = list(range(2015, 2026))

    # Union of all needed feature columns
    all_feature_cols = sorted(
        set(SP_ENHANCED_PRUNED_COLS) | set(TEAM_ONLY_FEATURE_COLS) | set(FULL_FEATURE_COLS)
    )

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
            for col in all_feature_cols:
                if col == 'is_home':
                    record[col] = 1
                elif col == 'park_factor':
                    record[col] = 1.0 + rng.normal(0, 0.05)
                elif col == 'log5_home_wp':
                    record[col] = 0.5 + rng.normal(0, 0.05)
                else:
                    record[col] = rng.normal(0, 0.1)

            # First 5 rows per season: NaN rolling_ops_diff (early-season)
            if i < 5:
                record['rolling_ops_diff'] = np.nan

            records.append(record)

    return pd.DataFrame(records)


def test_v2_fold_map_structure():
    """V2_FOLD_MAP has 5 entries, same as v1 FOLD_MAP."""
    from src.models.backtest import V2_FOLD_MAP, FOLD_MAP

    assert len(V2_FOLD_MAP) == 5
    # V2_FOLD_MAP is the same as FOLD_MAP
    assert V2_FOLD_MAP == FOLD_MAP


def test_v2_combinations_count():
    """V2_COMBINATIONS has exactly 6 entries (3 models x 2 feature sets)."""
    from src.models.backtest import V2_COMBINATIONS

    assert len(V2_COMBINATIONS) == 6


def test_v2_combinations_feature_sets():
    """V2_COMBINATIONS contains both 'team_only' and 'sp_enhanced' labels."""
    from src.models.backtest import V2_COMBINATIONS

    feature_sets = {combo[3] for combo in V2_COMBINATIONS}
    assert feature_sets == {'team_only', 'sp_enhanced'}


def test_run_all_v2_models_schema(synthetic_v2_feature_matrix):
    """run_all_v2_models output has required columns."""
    from src.models.backtest import run_all_v2_models

    results_df, artifacts = run_all_v2_models(synthetic_v2_feature_matrix)

    required_cols = [
        'game_date', 'home_team', 'away_team', 'season', 'home_win',
        'model_name', 'feature_set', 'fold_test_year',
        'prob_calibrated', 'prob_raw',
    ]
    for col in required_cols:
        assert col in results_df.columns, f"Missing column: {col}"


def test_run_all_v2_models_six_combos(synthetic_v2_feature_matrix):
    """run_all_v2_models output contains 6 unique (model_name, feature_set) pairs."""
    from src.models.backtest import run_all_v2_models

    results_df, artifacts = run_all_v2_models(synthetic_v2_feature_matrix)

    combos = results_df.groupby(['model_name', 'feature_set']).size()
    assert len(combos) == 6, f"Expected 6 combos, got {len(combos)}"

    expected_models = {'lr', 'rf', 'xgb'}
    expected_sets = {'team_only', 'sp_enhanced'}
    actual_models = set(results_df['model_name'].unique())
    actual_sets = set(results_df['feature_set'].unique())
    assert actual_models == expected_models
    assert actual_sets == expected_sets


def test_predict_2025_v2_schema(synthetic_v2_feature_matrix):
    """predict_2025_v2 output has same schema as predict_2025 but with both feature sets."""
    from src.models.predict import predict_2025_v2

    result = predict_2025_v2(synthetic_v2_feature_matrix)

    expected_cols = {
        'game_date', 'home_team', 'away_team', 'season', 'home_win',
        'model_name', 'feature_set', 'fold_test_year',
        'prob_calibrated', 'prob_raw',
    }
    assert set(result.columns) == expected_cols
    assert (result['season'] == 2025).all()
    assert (result['fold_test_year'] == 2025).all()


def test_predict_2025_v2_six_combos(synthetic_v2_feature_matrix):
    """predict_2025_v2 output contains 6 unique (model_name, feature_set) pairs."""
    from src.models.predict import predict_2025_v2

    result = predict_2025_v2(synthetic_v2_feature_matrix)

    combos = result.groupby(['model_name', 'feature_set']).size()
    assert len(combos) == 6, f"Expected 6 combos, got {len(combos)}"
