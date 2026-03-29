"""Edge identification and fee-adjusted profitability analysis.

KALSHI_FEE_RATE is a named module-level constant (7% of profits on winning
trades). Easy to update when actual 2025 MLB-specific fee is verified.

Fee formula per CONTEXT.md:
  BUY_YES win:  net = (1.0 - p) * (1 - KALSHI_FEE_RATE)
  BUY_YES lose: net = -p
  BUY_NO win:   net = p * (1 - KALSHI_FEE_RATE)
  BUY_NO lose:  net = -(1.0 - p)

Position sizing: flat $1 per contract for all simulated positions.
"""
import pandas as pd

KALSHI_FEE_RATE = 0.07  # 7% of profits on winning trades


def compute_edge_signals(
    merged: pd.DataFrame,
    prob_col: str = "prob_calibrated",
    price_col: str = "kalshi_open_price",
    threshold: float = 0.05,
) -> pd.DataFrame:
    """Identify games where model probability diverges from Kalshi opening price.

    Args:
        merged: DataFrame with model probabilities and Kalshi opening prices.
        prob_col: Column name for model probability.
        price_col: Column name for Kalshi opening price.
        threshold: Minimum absolute divergence to flag as edge (default 0.05 = 5pp).

    Returns:
        Copy of merged with added columns: edge, abs_edge, has_edge, position.
        - edge = prob_col - price_col (positive means model thinks home more likely)
        - abs_edge = |edge|
        - has_edge = abs_edge > threshold
        - position = "BUY_YES" if edge > 0 else "BUY_NO" (only meaningful where has_edge=True)
    """
    out = merged.copy()
    out["edge"] = out[prob_col] - out[price_col]
    out["abs_edge"] = out["edge"].abs()
    out["has_edge"] = out["abs_edge"] > threshold
    out["position"] = out["edge"].apply(lambda e: "BUY_YES" if e > 0 else "BUY_NO")
    return out


def compute_fee_adjusted_pnl(row) -> float:
    """Compute P&L for a $1 flat bet based on edge signal.

    Args:
        row: Dict-like with keys: kalshi_open_price, home_win, position.

    Returns:
        Net P&L in dollars (positive = profit, negative = loss).
    """
    p = row["kalshi_open_price"]
    actual_home_win = row["home_win"]
    position = row["position"]

    if position == "BUY_YES":
        if actual_home_win == 1:
            return (1.0 - p) * (1 - KALSHI_FEE_RATE)
        else:
            return -p
    else:  # BUY_NO
        if actual_home_win == 0:
            return p * (1 - KALSHI_FEE_RATE)
        else:
            return -(1.0 - p)
