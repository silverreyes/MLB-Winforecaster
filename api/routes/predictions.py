"""Prediction route handlers for the MLB Win Forecaster API.

Provides three endpoints:
- GET /predictions/today (API-01): All games for current date
- GET /predictions/latest-timestamp (API-03): Lightweight polling endpoint
- GET /predictions/{date} (API-02): Same shape for a historical date

All handlers are sync (def, not async def) to run in FastAPI's thread pool,
since psycopg3 sync connections block the event loop if called from async.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from api.models import (
    LatestTimestampResponse,
    PredictionResponse,
    TodayResponse,
)

router = APIRouter(tags=["predictions"])


def _build_prediction(row: dict) -> PredictionResponse:
    """Map a DB row dict to a PredictionResponse with computed fields."""
    lr = row.get("lr_prob")
    rf = row.get("rf_prob")
    xgb = row.get("xgb_prob")

    # Compute ensemble probability (average of 3 models)
    if lr is not None and rf is not None and xgb is not None:
        ensemble_prob = round((lr + rf + xgb) / 3, 4)
    else:
        ensemble_prob = None

    # Compute edge magnitude (model vs market divergence in percentage points)
    kalshi = row.get("kalshi_yes_price")
    if ensemble_prob is not None and kalshi is not None:
        edge_magnitude = round((ensemble_prob - kalshi) * 100, 1)
    else:
        edge_magnitude = None

    return PredictionResponse(
        game_date=row["game_date"],
        home_team=row["home_team"],
        away_team=row["away_team"],
        prediction_version=row["prediction_version"],
        prediction_status=row["prediction_status"],
        lr_prob=lr,
        rf_prob=rf,
        xgb_prob=xgb,
        ensemble_prob=ensemble_prob,
        feature_set=row["feature_set"],
        home_sp=row.get("home_sp"),
        away_sp=row.get("away_sp"),
        sp_uncertainty=row.get("sp_uncertainty", False),
        sp_may_have_changed=row.get("sp_may_have_changed", False),
        kalshi_yes_price=kalshi,
        edge_signal=row.get("edge_signal"),
        edge_magnitude=edge_magnitude,
        created_at=row["created_at"],
    )


def _fetch_predictions(pool, game_date_clause: str, params: dict | None = None) -> TodayResponse:
    """Shared query logic for /today and /{date} endpoints."""
    sql = f"""
        SELECT *
        FROM predictions
        WHERE game_date = {game_date_clause} AND is_latest = TRUE
        ORDER BY home_team, away_team
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    predictions = [_build_prediction(row) for row in rows]
    latest_prediction_at = max(
        (row["created_at"] for row in rows), default=None
    )

    return TodayResponse(
        predictions=predictions,
        latest_prediction_at=latest_prediction_at,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/predictions/today", response_model=TodayResponse)
def get_today_predictions(request: Request):
    """Return all predictions for today's games (API-01)."""
    pool = request.app.state.pool
    return _fetch_predictions(pool, "CURRENT_DATE")


# DO NOT REORDER: /latest-timestamp must precede /{date} to prevent path parameter capture
@router.get("/predictions/latest-timestamp", response_model=LatestTimestampResponse)
def get_latest_timestamp(request: Request):
    """Return the most recent prediction timestamp for today (API-03)."""
    pool = request.app.state.pool
    sql = """
        SELECT MAX(created_at) as latest
        FROM predictions
        WHERE game_date = CURRENT_DATE AND is_latest = TRUE
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            result = cur.fetchone()

    timestamp = result["latest"] if result else None
    return LatestTimestampResponse(timestamp=timestamp)


@router.get("/predictions/{date}", response_model=TodayResponse)
def get_date_predictions(request: Request, date: str):
    """Return all predictions for a specific date (API-02)."""
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    pool = request.app.state.pool
    return _fetch_predictions(pool, "%(date)s", {"date": date})
