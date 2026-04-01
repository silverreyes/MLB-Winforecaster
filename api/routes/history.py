"""History route handler for the MLB Win Forecaster API.

Provides GET /history -- returns past predictions with outcomes
and per-model accuracy for a date range.

Sync def handler (not async) following existing FastAPI pattern.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import HistoryResponse, HistoryRow, ModelAccuracy
from src.pipeline.db import get_history

router = APIRouter(tags=["history"])


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


@router.get("/history", response_model=HistoryResponse)
def get_history_route(
    request: Request,
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Return past predictions with outcomes and per-model accuracy.

    Only returns games where prediction_correct IS NOT NULL.
    Prefers post_lineup prediction; falls back to pre_lineup.
    """
    # Validate date formats
    for label, val in [("start", start), ("end", end)]:
        try:
            datetime.strptime(val, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {label} date format. Use YYYY-MM-DD.",
            )

    pool = request.app.state.pool
    rows = get_history(pool, start, end)

    games = [
        HistoryRow(
            game_date=r["game_date"],
            home_team=r["home_team"],
            away_team=r["away_team"],
            home_score=r.get("home_score"),
            away_score=r.get("away_score"),
            lr_prob=r.get("lr_prob"),
            rf_prob=r.get("rf_prob"),
            xgb_prob=r.get("xgb_prob"),
            prediction_correct=r["prediction_correct"],
        )
        for r in rows
    ]

    accuracy = _compute_accuracy(rows)

    return HistoryResponse(
        games=games,
        accuracy=accuracy,
        start_date=start,
        end_date=end,
    )
