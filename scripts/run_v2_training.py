"""V2 Model Training Script.

Train all 6 v2 model/feature-set combinations via walk-forward backtest,
calibrate with IsotonicRegression, produce 2025 predictions, and persist
artifacts as joblib bundles with metadata JSON.

Execute from project root: python scripts/run_v2_training.py
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd

from src.models.backtest import run_all_v2_models
from src.models.evaluate import compute_brier_scores
from src.models.predict import predict_2025_v2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Cell 1 - Load v2 Feature Store
logger.info("Loading v2 feature store...")
df = pd.read_parquet("data/features/feature_store_v2.parquet")
logger.info(
    f"Loaded: {df.shape[0]} games, {df.shape[1]} columns, "
    f"seasons {sorted(df['season'].unique())}"
)

# Cell 2 - Run v2 Walk-Forward Backtest (6 models)
logger.info("Running v2 walk-forward backtest (6 model/feature-set combos)...")
results_v2, artifacts = run_all_v2_models(df)
results_v2.to_parquet("data/results/backtest_results_v2.parquet", index=False)
logger.info(f"Backtest results: {results_v2.shape[0]} rows")
print(results_v2.groupby(["model_name", "feature_set"]).size())

# Cell 3 - Run v2 2025 Predictions
logger.info("Running v2 2025 predictions...")
preds_2025_v2 = predict_2025_v2(df)
preds_2025_v2.to_parquet("data/results/predictions_2025_v2.parquet", index=False)
logger.info(f"2025 predictions: {preds_2025_v2.shape[0]} rows")
print(preds_2025_v2.groupby(["model_name", "feature_set"]).size())

# Cell 4 - Compute Fold Brier Scores for Metadata
logger.info("Computing Brier scores...")
brier_v2 = compute_brier_scores(results_v2)
print("\nV2 Brier Scores (aggregate):")
print(
    brier_v2[brier_v2["fold_test_year"] == "aggregate"].to_string(index=False)
)

# Cell 5 - Persist Artifacts + Metadata
logger.info("Persisting artifacts...")
artifacts_dir = Path("models/artifacts")
artifacts_dir.mkdir(parents=True, exist_ok=True)

metadata = {
    "training_date": datetime.now().isoformat(),
    "v2_feature_store": "data/features/feature_store_v2.parquet",
    "models": {},
}

for artifact in artifacts:
    name = f"{artifact['model_name']}_{artifact['feature_set']}"
    joblib.dump(artifact, artifacts_dir / f"{name}.joblib")
    logger.info(f"Saved {name}.joblib")

    # Get fold-level Brier scores from results
    model_brier = brier_v2[
        (brier_v2["model_name"] == artifact["model_name"])
        & (brier_v2["feature_set"] == artifact["feature_set"])
        & (brier_v2["fold_test_year"] != "aggregate")
    ]
    fold_briers = dict(
        zip(
            model_brier["fold_test_year"].astype(str),
            model_brier["brier_score"],
        )
    )
    agg_brier = brier_v2[
        (brier_v2["model_name"] == artifact["model_name"])
        & (brier_v2["feature_set"] == artifact["feature_set"])
        & (brier_v2["fold_test_year"] == "aggregate")
    ]["brier_score"].values[0]

    metadata["models"][name] = {
        "feature_cols": artifact["feature_cols"],
        "fold_brier_scores": fold_briers,
        "aggregate_brier_score": float(agg_brier),
        "calibration_method": "IsotonicRegression",
    }

with open(artifacts_dir / "model_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
logger.info(f"Saved model_metadata.json with {len(metadata['models'])} models")

# Cell 6 - Verification
logger.info("Verifying artifact round-trip...")
for name in metadata["models"]:
    loaded = joblib.load(artifacts_dir / f"{name}.joblib")
    assert "model" in loaded
    assert "calibrator" in loaded
    assert "feature_cols" in loaded
    print(
        f"  {name}: model={type(loaded['model']).__name__}, "
        f"calibrator={type(loaded['calibrator']).__name__}, "
        f"features={len(loaded['feature_cols'])}"
    )
logger.info("All 6 artifacts verified!")
