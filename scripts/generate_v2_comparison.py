"""Generate v2 model comparison artifacts.

Produces:
- data/results/brier_comparison.csv (4-group apples-to-apples Brier table)
- data/results/reliability_team_only.png (calibration curves for TEAM_ONLY)
- data/results/reliability_sp_enhanced.png (calibration curves for SP_ENHANCED)

Run from project root: python scripts/generate_v2_comparison.py
"""

import sys
sys.path.insert(0, ".")

import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

from src.data.kalshi import fetch_kalshi_markets, fetch_kalshi_open_prices
from src.models.evaluate import get_calibration_data


def main():
    # ---- Step 1: Load all prediction sources ----
    print("=" * 60)
    print("STEP 1: Loading prediction sources")
    print("=" * 60)

    # V2 predictions (6 model/feature-set combos)
    preds_v2 = pd.read_parquet("data/results/predictions_2025_v2.parquet")
    print(f"V2 predictions: {preds_v2.shape[0]} rows")
    print(f"  Combos: {preds_v2.groupby(['model_name','feature_set']).size().to_dict()}")

    # V1 predictions (3 models, core features)
    preds_v1 = pd.read_parquet("data/results/predictions_2025.parquet")
    print(f"V1 predictions: {preds_v1.shape[0]} rows")

    # Kalshi data
    kalshi_df = fetch_kalshi_markets(max_age_hours=float("inf"))
    kalshi_df = fetch_kalshi_open_prices(kalshi_df)

    # Fill NaN open prices with closing price (fallback for ~0.5% of games)
    n_open = kalshi_df["kalshi_open_price"].notna().sum()
    n_fallback = kalshi_df["kalshi_open_price"].isna().sum()
    print(f"Kalshi: {len(kalshi_df)} games ({n_open} open price, {n_fallback} fallback)")
    kalshi_df["kalshi_open_price"] = kalshi_df["kalshi_open_price"].fillna(
        kalshi_df["kalshi_yes_price"]
    )

    # Add game_date as datetime for joining
    kalshi_df["game_date"] = pd.to_datetime(kalshi_df["date"])

    # Drop doubleheader duplicates from Kalshi
    kalshi_deduped = kalshi_df.drop_duplicates(
        subset=["game_date", "home_team", "away_team"], keep="first"
    )
    n_dh_dropped = len(kalshi_df) - len(kalshi_deduped)
    if n_dh_dropped > 0:
        print(f"  Dropped {n_dh_dropped} doubleheader duplicate(s)")

    # ---- Step 2: Deduplicate doubleheaders and find common game set ----
    print(f"\n{'=' * 60}")
    print("STEP 2: Deduplicating doubleheaders and finding common game set")
    print("=" * 60)

    # Doubleheader games have identical (date, home, away) keys but different
    # actual games. Since we cannot distinguish them across sources, keep only
    # the first occurrence per (date, home, away, model_name) to avoid inflated
    # counts and many-to-many join issues.
    join_cols = ["game_date", "home_team", "away_team"]

    preds_v2_deduped = preds_v2.drop_duplicates(
        subset=join_cols + ["model_name", "feature_set"], keep="first"
    )
    preds_v1_deduped = preds_v1.drop_duplicates(
        subset=join_cols + ["model_name"], keep="first"
    )

    n_v2_dh = len(preds_v2) - len(preds_v2_deduped)
    n_v1_dh = len(preds_v1) - len(preds_v1_deduped)
    if n_v2_dh:
        print(f"  V2: dropped {n_v2_dh} doubleheader duplicate rows")
    if n_v1_dh:
        print(f"  V1: dropped {n_v1_dh} doubleheader duplicate rows")

    # Build common game set via inner join (more robust than string key sets)
    v2_unique = preds_v2_deduped[join_cols].drop_duplicates()
    v1_unique = preds_v1_deduped[join_cols].drop_duplicates()
    kalshi_unique = kalshi_deduped[join_cols].drop_duplicates()

    common = v2_unique.merge(v1_unique, on=join_cols).merge(kalshi_unique, on=join_cols)
    print(f"V2 unique games: {len(v2_unique)}")
    print(f"V1 unique games: {len(v1_unique)}")
    print(f"Kalshi unique games: {len(kalshi_unique)}")
    print(f"Common (intersection): {len(common)} games")

    # ---- Step 3: Filter to common games and compute Brier scores ----
    print(f"\n{'=' * 60}")
    print("STEP 3: Computing Brier scores")
    print("=" * 60)

    # Filter each source to common games via merge
    v2_sp = preds_v2_deduped[preds_v2_deduped["feature_set"] == "sp_enhanced"].merge(
        common, on=join_cols
    )
    v2_team = preds_v2_deduped[preds_v2_deduped["feature_set"] == "team_only"].merge(
        common, on=join_cols
    )
    v1_core = preds_v1_deduped.merge(common, on=join_cols)
    kalshi_common = kalshi_deduped.merge(common, on=join_cols)

    comparison_rows = []

    # V2 SP_ENHANCED - per model
    for model in ["lr", "rf", "xgb"]:
        subset = v2_sp[v2_sp["model_name"] == model]
        brier = brier_score_loss(subset["home_win"], subset["prob_calibrated"])
        comparison_rows.append(
            {
                "group": "v2_sp_enhanced",
                "model_name": model,
                "brier_score": round(brier, 4),
                "n_games": len(subset),
            }
        )
        print(f"  v2_sp_enhanced/{model}: Brier={brier:.4f} (n={len(subset)})")

    # V2 TEAM_ONLY - per model
    for model in ["lr", "rf", "xgb"]:
        subset = v2_team[v2_team["model_name"] == model]
        brier = brier_score_loss(subset["home_win"], subset["prob_calibrated"])
        comparison_rows.append(
            {
                "group": "v2_team_only",
                "model_name": model,
                "brier_score": round(brier, 4),
                "n_games": len(subset),
            }
        )
        print(f"  v2_team_only/{model}: Brier={brier:.4f} (n={len(subset)})")

    # V1 - per model
    for model in ["lr", "rf", "xgb"]:
        subset = v1_core[v1_core["model_name"] == model]
        brier = brier_score_loss(subset["home_win"], subset["prob_calibrated"])
        comparison_rows.append(
            {
                "group": "v1",
                "model_name": model,
                "brier_score": round(brier, 4),
                "n_games": len(subset),
            }
        )
        print(f"  v1/{model}: Brier={brier:.4f} (n={len(subset)})")

    # Kalshi market -- join with outcomes from v2 predictions
    outcomes = v2_sp[join_cols + ["home_win"]].drop_duplicates(subset=join_cols)
    kalshi_with_outcomes = kalshi_common.merge(outcomes, on=join_cols)
    kalshi_brier = brier_score_loss(
        kalshi_with_outcomes["home_win"], kalshi_with_outcomes["kalshi_open_price"]
    )
    comparison_rows.append(
        {
            "group": "kalshi",
            "model_name": "market",
            "brier_score": round(kalshi_brier, 4),
            "n_games": len(kalshi_with_outcomes),
        }
    )
    print(f"  kalshi/market: Brier={kalshi_brier:.4f} (n={len(kalshi_with_outcomes)})")

    # Save CSV
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv("data/results/brier_comparison.csv", index=False)
    print(f"\nSaved: data/results/brier_comparison.csv ({len(comparison_df)} rows)")

    # Best model per group
    summary = comparison_df.loc[
        comparison_df.groupby("group")["brier_score"].idxmin()
    ]
    print("\nBest Model per Group:")
    print(summary[["group", "model_name", "brier_score", "n_games"]].to_string(index=False))

    # ---- Step 4: Reliability diagrams from backtest results ----
    print(f"\n{'=' * 60}")
    print("STEP 4: Generating reliability diagrams")
    print("=" * 60)

    backtest_v2 = pd.read_parquet("data/results/backtest_results_v2.parquet")
    print(f"Backtest V2: {backtest_v2.shape[0]} rows")

    # TEAM_ONLY reliability diagram
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")
    for model in ["lr", "rf", "xgb"]:
        frac, mean_pred = get_calibration_data(backtest_v2, model, "team_only", n_bins=10)
        ax.plot(mean_pred, frac, "s-", label=f"{model} (team_only)")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Reliability Diagram - v2 TEAM_ONLY")
    ax.legend()
    plt.tight_layout()
    plt.savefig("data/results/reliability_team_only.png", dpi=150)
    plt.close(fig)
    print("Saved: data/results/reliability_team_only.png")

    # SP_ENHANCED reliability diagram
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")
    for model in ["lr", "rf", "xgb"]:
        frac, mean_pred = get_calibration_data(
            backtest_v2, model, "sp_enhanced", n_bins=10
        )
        ax.plot(mean_pred, frac, "s-", label=f"{model} (sp_enhanced)")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Reliability Diagram - v2 SP_ENHANCED")
    ax.legend()
    plt.tight_layout()
    plt.savefig("data/results/reliability_sp_enhanced.png", dpi=150)
    plt.close(fig)
    print("Saved: data/results/reliability_sp_enhanced.png")

    # ---- Step 5: Reliability assessment ----
    print(f"\n{'=' * 60}")
    print("STEP 5: Reliability assessment")
    print("=" * 60)

    for fs in ["team_only", "sp_enhanced"]:
        print(f"\n{fs.upper()}:")
        for model in ["lr", "rf", "xgb"]:
            frac, mean_pred = get_calibration_data(backtest_v2, model, fs, n_bins=10)
            max_dev = np.max(np.abs(frac - mean_pred))
            mean_dev = np.mean(np.abs(frac - mean_pred))
            print(f"  {model}: max_deviation={max_dev:.4f}, mean_deviation={mean_dev:.4f}")

    print("\nDone!")


if __name__ == "__main__":
    main()
