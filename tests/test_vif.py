"""Tests for VIF (Variance Inflation Factor) computation module.

Covers requirement MDL-05: multicollinearity analysis using sklearn-based VIF.
"""

import numpy as np
import pandas as pd
import pytest

from src.models.vif import compute_vif


@pytest.fixture
def synthetic_5_features():
    """5-feature synthetic DataFrame for VIF testing."""
    rng = np.random.RandomState(42)
    n = 200
    return pd.DataFrame({
        'feat_0': rng.randn(n),
        'feat_1': rng.randn(n),
        'feat_2': rng.randn(n),
        'feat_3': rng.randn(n),
        'feat_4': rng.randn(n),
    })


def test_vif_returns_dataframe(synthetic_5_features):
    """compute_vif returns DataFrame with columns ['feature', 'VIF'], length == 5."""
    result = compute_vif(synthetic_5_features)

    assert isinstance(result, pd.DataFrame), "Result must be a DataFrame"
    assert list(result.columns) == ['feature', 'VIF'], (
        f"Expected columns ['feature', 'VIF'], got {list(result.columns)}"
    )
    assert len(result) == 5, f"Expected 5 rows, got {len(result)}"


def test_vif_perfect_collinearity():
    """When col_B = col_A * 2 + 1, VIF for col_A and col_B should be > 100."""
    rng = np.random.RandomState(42)
    n = 200
    col_a = rng.randn(n)
    df = pd.DataFrame({
        'col_A': col_a,
        'col_B': col_a * 2 + 1,  # perfect linear relationship
        'col_C': rng.randn(n),
        'col_D': rng.randn(n),
        'col_E': rng.randn(n),
    })

    result = compute_vif(df)
    vif_a = result.loc[result['feature'] == 'col_A', 'VIF'].iloc[0]
    vif_b = result.loc[result['feature'] == 'col_B', 'VIF'].iloc[0]

    assert vif_a > 100, f"col_A VIF should be > 100 (perfect collinearity), got {vif_a}"
    assert vif_b > 100, f"col_B VIF should be > 100 (perfect collinearity), got {vif_b}"


def test_vif_independent_features():
    """5 independent random columns have VIF close to 1.0 (all VIF < 2.0)."""
    rng = np.random.RandomState(42)
    n = 1000  # large sample for stability
    df = pd.DataFrame({
        f'ind_{i}': rng.randn(n) for i in range(5)
    })

    result = compute_vif(df)

    for _, row in result.iterrows():
        assert row['VIF'] < 2.0, (
            f"Independent feature {row['feature']} has VIF={row['VIF']}, expected < 2.0"
        )


def test_vif_handles_nan_free_input(synthetic_5_features):
    """No errors when DataFrame has zero NaN values."""
    assert synthetic_5_features.isna().sum().sum() == 0, "Fixture must be NaN-free"
    result = compute_vif(synthetic_5_features)
    assert len(result) == 5, "Should return result for all 5 features"
    assert result['VIF'].notna().all(), "No NaN values in VIF output"
