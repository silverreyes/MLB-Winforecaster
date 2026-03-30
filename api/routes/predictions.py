"""Prediction route handlers for the MLB Win Forecaster API.

Provides three endpoints:
- GET /predictions/today (API-01): All games for current date
- GET /predictions/latest-timestamp (API-03): Lightweight polling endpoint
- GET /predictions/{date} (API-02): Same shape for a historical date

All handlers are sync (def, not async def) to run in FastAPI's thread pool,
since psycopg3 sync connections block the event loop if called from async.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from api.models import (
    LatestTimestampResponse,
    PredictionResponse,
    TodayResponse,
)
from src.data.mlb_schedule import fetch_today_schedule
from src.data.team_mappings import normalize_team

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predictions"])


def _build_schedule_lookup() -> dict[tuple[str, str], str]:
    """Build (home_team, away_team) -> game_datetime lookup from today's schedule."""
    try:
        games = fetch_today_schedule()
    except Exception:
        logger.warning("Failed to fetch schedule for game times, returning empty lookup")
        return {}
    lookup: dict[tuple[str, str], str] = {}
    for g in games:
        try:
            home = normalize_team(g.get("home_name", ""))
            away = normalize_team(g.get("away_name", ""))
            dt = g.get("game_datetime")
            if home and away and dt:
                lookup[(home, away)] = dt
        except (ValueError, KeyError):
            continue
    return lookup


def _parse_game_time(dt_str: str | None) -> datetime | None:
    """Parse game_datetime ISO string to timezone-aware datetime, or None."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_prediction(row: dict, game_time: str | None = None) -> PredictionResponse:
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
        game_time=_parse_game_time(game_time),
    )


def _fetch_predictions(
    pool,
    game_date_clause: str,
    params: dict | None = None,
    schedule_lookup: dict[tuple[str, str], str] | None = None,
) -> TodayResponse:
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

    predictions = []
    for row in rows:
        game_time = None
        if schedule_lookup:
            game_time = schedule_lookup.get((row["home_team"], row["away_team"]))
        predictions.append(_build_prediction(row, game_time=game_time))
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
    schedule_lookup = _build_schedule_lookup()
    return _fetch_predictions(pool, "CURRENT_DATE", schedule_lookup=schedule_lookup)


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
