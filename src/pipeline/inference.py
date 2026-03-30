"""Model artifact loading and prediction for the live pipeline.

Loads all 6 model artifacts (LR/RF/XGB x team_only/sp_enhanced) at startup.
Provides predict_game() for running inference on a single game's features.
"""
import logging

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
from pathlib import Path

ARTIFACT_DIR = Path("models/artifacts")
ARTIFACT_NAMES = [
    "lr_team_only", "lr_sp_enhanced",
    "rf_team_only", "rf_sp_enhanced",
    "xgb_team_only", "xgb_sp_enhanced",
]


def load_all_artifacts(artifact_dir: Path | None = None) -> dict[str, dict]:
    """Load all 6 model artifacts at startup. Fail hard if any missing.

    Args:
        artifact_dir: Override path for testing. Defaults to models/artifacts/.

    Returns:
        Dict mapping artifact name -> artifact dict.
        Each artifact dict contains: model, calibrator, feature_cols, model_name, feature_set.

    Raises:
        FileNotFoundError: If any artifact file is missing.
    """
    base = artifact_dir or ARTIFACT_DIR
    artifacts = {}
    for name in ARTIFACT_NAMES:
        path = base / f"{name}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"Missing model artifact: {path}")
        artifacts[name] = joblib.load(path)
    return artifacts


def predict_game(
    artifacts: dict[str, dict],
    features: dict,
    feature_set: str,
) -> dict[str, float]:
    """Run inference for a single game using the appropriate model artifacts.

    Args:
        artifacts: Dict of all loaded artifacts (from load_all_artifacts).
        features: Dict of feature_name -> value for one game.
        feature_set: Either "team_only" or "sp_enhanced".

    Returns:
        Dict of {model_name: calibrated_probability} e.g.,
        {"lr": 0.58, "rf": 0.55, "xgb": 0.57}
    """
    results = {}
    for name, artifact in artifacts.items():
        if artifact["feature_set"] != feature_set:
            continue
        feature_cols = artifact["feature_cols"]
        model = artifact["model"]
        calibrator = artifact["calibrator"]

        # Build 1-row DataFrame with correct column order
        X = pd.DataFrame([features])[feature_cols]

        # Check for NaN in features -- skip if any are missing
        if X.isna().any().any():
            nan_cols = X.columns[X.isna().any()].tolist()
            logger.warning(f"Skipping {name}: NaN in features {nan_cols}")
            continue

        raw_prob = model.predict_proba(X)[:, 1]
        calibrated_prob = calibrator.predict(raw_prob)
        model_short_name = artifact["model_name"]  # "lr", "rf", "xgb"
        results[model_short_name] = float(np.clip(calibrated_prob[0], 0.01, 0.99))

    return results
