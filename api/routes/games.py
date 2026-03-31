"""Games route handler for the MLB Win Forecaster API.

Provides GET /games/{date} -- merges MLB schedule with predictions
to return all games for a date, including those without predictions
(stub cards).

Sync def handler (not async) following existing FastAPI pattern.
"""

import logging
from datetime import date as date_type, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from api.models import (
    GameResponse,
    GamesDateResponse,
    PredictionGroup,
    PredictionResponse,
)
from src.data.mlb_schedule import get_schedule_cached
from src.data.team_mappings import normalize_team

ET = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["games"])


def compute_view_mode(requested_date_str: str) -> str:
    """Determine rendering context for a given date.

    Returns one of: 'live', 'historical', 'tomorrow', 'future'.
    All comparisons use America/New_York timezone (ET).
    """
    requested = date_type.fromisoformat(requested_date_str)
    today = datetime.now(ET).date()
    tomorrow = today + timedelta(days=1)
    if requested == today:
        return "live"
    elif requested < today:
        return "historical"
    elif requested == tomorrow:
        return "tomorrow"
    else:
        return "future"


def _is_pitcher_confirmed(name: str | None) -> bool:
    """Check if a probable pitcher name represents a confirmed starter.

    Returns False for None, empty string, 'TBD', or whitespace-padded 'TBD'.
    """
    if not name:
        return False
    stripped = name.strip()
    return bool(stripped) and stripped.upper() != 'TBD'


def _apply_tomorrow_labels(games: list[GameResponse], schedule: list[dict]) -> None:
    """Apply PRELIMINARY prediction labels to tomorrow's games with both SPs confirmed.

    Mutates GameResponse objects in-place:
    - Both SPs confirmed: prediction_label='PRELIMINARY', pitcher names populated
    - Otherwise: prediction_label remains None, individual confirmed pitchers still populated
    """
    schedule_lookup = {g['game_id']: g for g in schedule}
    for game_resp in games:
        sched = schedule_lookup.get(game_resp.game_id, {})
        home_sp = sched.get('home_probable_pitcher')
        away_sp = sched.get('away_probable_pitcher')
        if _is_pitcher_confirmed(home_sp) and _is_pitcher_confirmed(away_sp):
            game_resp.prediction_label = 'PRELIMINARY'
            game_resp.home_probable_pitcher = home_sp
            game_resp.away_probable_pitcher = away_sp
        else:
            game_resp.home_probable_pitcher = home_sp if _is_pitcher_confirmed(home_sp) else None
            game_resp.away_probable_pitcher = away_sp if _is_pitcher_confirmed(away_sp) else None


def _parse_game_time(dt_str: str | None) -> datetime | None:
    """Parse game_datetime ISO string to timezone-aware datetime, or None."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_prediction_response(row: dict) -> PredictionResponse:
    """Map a DB row dict to a PredictionResponse with computed fields."""
    lr = row.get("lr_prob")
    rf = row.get("rf_prob")
    xgb = row.get("xgb_prob")

    if lr is not None and rf is not None and xgb is not None:
        ensemble_prob = round((lr + rf + xgb) / 3, 4)
    else:
        ensemble_prob = None

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
        game_time=None,  # game_time comes from schedule, not DB
    )


def _build_prediction_group(rows: list[dict]) -> PredictionGroup | None:
    """Group prediction rows into pre/post-lineup pair."""
    if not rows:
        return None
    pre = None
    post = None
    for row in rows:
        version = row.get("prediction_version")
        resp = _build_prediction_response(row)
        if version in ("post_lineup", "confirmation"):
            post = resp
        elif version == "pre_lineup":
            pre = resp
    if pre is None and post is None:
        return None
    return PredictionGroup(pre_lineup=pre, post_lineup=post)


def _fetch_predictions_for_date(pool, date_str: str) -> list[dict]:
    """Query all latest predictions for a given date."""
    sql = """
        SELECT *
        FROM predictions
        WHERE game_date = %(date)s AND is_latest = TRUE
        ORDER BY home_team, away_team
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"date": date_str})
            return cur.fetchall()


def build_games_response(
    schedule: list[dict],
    predictions: list[dict],
) -> list[GameResponse]:
    """Merge schedule games with prediction rows.

    - Games with predictions: prediction populated with PredictionGroup
    - Games without predictions: stub card (prediction = None)
    - Matching priority: game_id first, then (home_team, away_team) fallback

    Args:
        schedule: List of game dicts from get_schedule_cached().
        predictions: List of row dicts from _fetch_predictions_for_date().

    Returns:
        List of GameResponse objects, one per scheduled game.
    """
    # Build prediction lookups
    pred_by_game_id: dict[int, list[dict]] = {}
    pred_by_teams: dict[tuple[str, str], list[dict]] = {}
    for p in predictions:
        gid = p.get("game_id")
        if gid:
            pred_by_game_id.setdefault(gid, []).append(p)
        else:
            key = (p["home_team"], p["away_team"])
            pred_by_teams.setdefault(key, []).append(p)

    results = []
    for game in schedule:
        game_id = game["game_id"]
        try:
            home = normalize_team(game["home_name"])
            away = normalize_team(game["away_name"])
        except (ValueError, KeyError):
            logger.warning(f"Cannot normalize teams for game {game_id}, skipping")
            continue

        # Try game_id match first, then team-pair fallback
        preds = pred_by_game_id.get(game_id, [])
        if not preds:
            preds = pred_by_teams.get((home, away), [])

        prediction_group = _build_prediction_group(preds)

        results.append(GameResponse(
            game_id=game_id,
            home_team=home,
            away_team=away,
            game_time=_parse_game_time(game.get("game_datetime")),
            game_status=game["game_status"],
            prediction=prediction_group,
        ))

    return results


@router.get("/games/{date}", response_model=GamesDateResponse)
def get_games_for_date(request: Request, date: str):
    """Return all games for a specific date, merged with predictions.

    Games without prediction rows are returned with prediction=null (stub cards).
    Status badge derived from MLB abstractGameState + codedGameState.
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    pool = request.app.state.pool

    # Compute view mode (live/historical/tomorrow/future)
    view_mode = compute_view_mode(date)

    # Fetch schedule (cached, 75s TTL); include pitchers for tomorrow
    include_pitchers = view_mode == "tomorrow"
    schedule = get_schedule_cached(date, include_pitchers=include_pitchers)

    # Fetch predictions from DB
    predictions = _fetch_predictions_for_date(pool, date)

    # Merge
    games = build_games_response(schedule, predictions)

    # Apply PRELIMINARY labels for tomorrow's games with confirmed SPs
    if view_mode == "tomorrow":
        _apply_tomorrow_labels(games, schedule)

    return GamesDateResponse(
        games=games,
        generated_at=datetime.now(timezone.utc),
        view_mode=view_mode,
    )
