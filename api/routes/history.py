"""History route handler for the MLB Win Forecaster API.

Provides GET /history -- returns past predictions with outcomes
and per-model accuracy for a date range.

Sync def handler (not async) following existing FastAPI pattern.
"""

from api.models import ModelAccuracy


def _compute_accuracy(rows: list[dict]) -> dict[str, ModelAccuracy]:
    """Compute per-model accuracy from history rows.

    Derives the actual outcome by computing ensemble probability (mean of
    lr_prob, rf_prob, xgb_prob) and combining it with prediction_correct:
        home_won = (ensemble >= 0.5 AND prediction_correct)
                   OR (ensemble < 0.5 AND NOT prediction_correct)

    Each model is then evaluated individually against that derived outcome.
    Rows missing any probability or prediction_correct are skipped.
    """
    models = {"lr": {"correct": 0, "total": 0},
              "rf": {"correct": 0, "total": 0},
              "xgb": {"correct": 0, "total": 0}}

    for row in rows:
        lr = row.get("lr_prob")
        rf = row.get("rf_prob")
        xgb = row.get("xgb_prob")
        pc = row.get("prediction_correct")

        if lr is None or rf is None or xgb is None or pc is None:
            continue

        # Derive whether home team actually won:
        # ensemble >= 0.5 means model predicted home win
        # prediction_correct True means ensemble prediction was right
        # So: home_won = (ensemble >= 0.5 AND pc) OR (ensemble < 0.5 AND NOT pc)
        ensemble = (lr + rf + xgb) / 3.0
        home_won = (ensemble >= 0.5 and pc) or (ensemble < 0.5 and not pc)

        # Per-model correctness
        for key, prob in [("lr", lr), ("rf", rf), ("xgb", xgb)]:
            model_predicted_home = prob >= 0.5
            model_correct = (model_predicted_home == home_won)
            models[key]["total"] += 1
            if model_correct:
                models[key]["correct"] += 1

    result = {}
    for key, stats in models.items():
        total = stats["total"]
        correct = stats["correct"]
        pct = round((correct / total) * 100, 1) if total > 0 else 0.0
        result[key] = ModelAccuracy(correct=correct, total=total, pct=pct)

    return result
