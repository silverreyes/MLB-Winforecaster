"""Tests for edge identification and fee-adjusted profitability (MARKET-03, MARKET-04).

Covers:
- Edge threshold filtering (configurable, default 0.05)
- Position assignment (BUY_YES when model > market, BUY_NO when model < market)
- Fee-adjusted P&L for all four cases (BUY_YES win/lose, BUY_NO win/lose)
- KALSHI_FEE_RATE constant value
"""
import pytest
import pandas as pd
from src.models.edge import KALSHI_FEE_RATE, compute_edge_signals, compute_fee_adjusted_pnl


def test_kalshi_fee_rate_value():
    """MARKET-04: KALSHI_FEE_RATE is 0.07 (7% of profits)."""
    assert KALSHI_FEE_RATE == 0.07


@pytest.fixture
def sample_merged():
    """Sample merged DataFrame with model probs and Kalshi open prices."""
    return pd.DataFrame({
        "prob_calibrated": [0.65, 0.50, 0.40, 0.70],
        "kalshi_open_price": [0.55, 0.53, 0.55, 0.55],
        "home_win": [1, 0, 0, 1],
    })


class TestComputeEdgeSignals:
    def test_edge_column_added(self, sample_merged):
        result = compute_edge_signals(sample_merged)
        assert "edge" in result.columns
        assert "abs_edge" in result.columns
        assert "has_edge" in result.columns
        assert "position" in result.columns

    def test_edge_threshold_default_flags_large(self, sample_merged):
        """MARKET-03: |0.65 - 0.55| = 0.10 > 0.05 => has_edge=True."""
        result = compute_edge_signals(sample_merged, threshold=0.05)
        assert result.iloc[0]["has_edge"] == True  # |0.10| > 0.05

    def test_edge_threshold_default_skips_small(self, sample_merged):
        """MARKET-03: |0.50 - 0.53| = 0.03 < 0.05 => has_edge=False."""
        result = compute_edge_signals(sample_merged, threshold=0.05)
        assert result.iloc[1]["has_edge"] == False  # |0.03| < 0.05

    def test_edge_threshold_custom(self, sample_merged):
        """MARKET-03: Custom threshold=0.02 flags |0.03| > 0.02."""
        result = compute_edge_signals(sample_merged, threshold=0.02)
        assert result.iloc[1]["has_edge"] == True  # |0.03| > 0.02

    def test_position_buy_yes(self, sample_merged):
        """Positive edge (model > market) => BUY_YES."""
        result = compute_edge_signals(sample_merged)
        assert result.iloc[0]["position"] == "BUY_YES"  # 0.65 > 0.55

    def test_position_buy_no(self, sample_merged):
        """Negative edge (model < market) => BUY_NO."""
        result = compute_edge_signals(sample_merged)
        assert result.iloc[2]["position"] == "BUY_NO"  # 0.40 < 0.55

    def test_does_not_modify_input(self, sample_merged):
        """compute_edge_signals returns a copy, not a mutated input."""
        original_cols = list(sample_merged.columns)
        compute_edge_signals(sample_merged)
        assert list(sample_merged.columns) == original_cols


class TestComputeFeeAdjustedPnl:
    def test_buy_yes_win(self):
        """MARKET-04: BUY_YES win => (1-0.55)*(1-0.07) = 0.4185."""
        row = {"kalshi_open_price": 0.55, "home_win": 1, "position": "BUY_YES"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(0.4185, abs=0.0001)

    def test_buy_yes_lose(self):
        """MARKET-04: BUY_YES lose => -0.55."""
        row = {"kalshi_open_price": 0.55, "home_win": 0, "position": "BUY_YES"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(-0.55, abs=0.0001)

    def test_buy_no_win(self):
        """MARKET-04: BUY_NO win => 0.55*(1-0.07) = 0.5115."""
        row = {"kalshi_open_price": 0.55, "home_win": 0, "position": "BUY_NO"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(0.5115, abs=0.0001)

    def test_buy_no_lose(self):
        """MARKET-04: BUY_NO lose => -(1-0.55) = -0.45."""
        row = {"kalshi_open_price": 0.55, "home_win": 1, "position": "BUY_NO"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(-0.45, abs=0.0001)

    def test_extreme_price_low(self):
        """Fee math at low price (p=0.10): win profit is 0.90*0.93=0.837."""
        row = {"kalshi_open_price": 0.10, "home_win": 1, "position": "BUY_YES"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(0.837, abs=0.001)

    def test_extreme_price_high(self):
        """Fee math at high price (p=0.90): loss is -0.90."""
        row = {"kalshi_open_price": 0.90, "home_win": 0, "position": "BUY_YES"}
        pnl = compute_fee_adjusted_pnl(row)
        assert pnl == pytest.approx(-0.90, abs=0.001)
