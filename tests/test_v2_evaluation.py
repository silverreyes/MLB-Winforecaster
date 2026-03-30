"""Tests for v2 model evaluation: Brier comparison table and reliability diagrams.

MDL-03: Apples-to-apples Brier comparison (v2 SP_ENHANCED, v2 TEAM_ONLY, v1, Kalshi)
MDL-04: Reliability diagrams with visual inspection gate
"""

import pandas as pd
import pytest
import numpy as np


def test_brier_comparison_has_four_groups():
    """MDL-03: Comparison table has all four groups."""
    comparison = pd.read_csv("data/results/brier_comparison.csv")
    groups = set(comparison['group'].values)
    assert groups == {'v2_sp_enhanced', 'v2_team_only', 'v1', 'kalshi'}, f"Groups: {groups}"


def test_brier_comparison_same_n_games():
    """MDL-03: All groups compared on identical game set (same n_games)."""
    comparison = pd.read_csv("data/results/brier_comparison.csv")
    # Each group may have multiple rows (one per model), but
    # all rows within a group should have the same n_games,
    # and all groups should share the same n_games value.
    n_games_per_group = comparison.groupby('group')['n_games'].first()
    unique_n = n_games_per_group.unique()
    assert len(unique_n) == 1, (
        f"Different n_games across groups: {n_games_per_group.to_dict()}"
    )


def test_brier_comparison_valid_scores():
    """MDL-03: Brier scores are valid floats in reasonable MLB range."""
    comparison = pd.read_csv("data/results/brier_comparison.csv")
    for _, row in comparison.iterrows():
        assert 0 <= row['brier_score'] <= 0.5, (
            f"{row['group']} {row['model_name']} Brier {row['brier_score']} out of range"
        )


def test_brier_comparison_columns():
    """MDL-03: Comparison CSV has required columns."""
    comparison = pd.read_csv("data/results/brier_comparison.csv")
    required = {'group', 'model_name', 'brier_score', 'n_games'}
    assert required.issubset(set(comparison.columns)), (
        f"Missing columns: {required - set(comparison.columns)}"
    )


def test_reliability_diagrams_generated():
    """MDL-04: Reliability diagram PNGs exist for both feature sets."""
    import os
    assert os.path.isfile("data/results/reliability_team_only.png"), (
        "Missing reliability_team_only.png"
    )
    assert os.path.isfile("data/results/reliability_sp_enhanced.png"), (
        "Missing reliability_sp_enhanced.png"
    )
