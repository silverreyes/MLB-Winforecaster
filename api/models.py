"""Pydantic response models for all API endpoints.

Defines the JSON shapes returned by each route handler. All models
use strict typing with Optional fields for nullable database columns.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    """Single prediction row returned by /predictions endpoints."""

    game_date: date
    home_team: str
    away_team: str
    prediction_version: str
    prediction_status: str
    lr_prob: float | None
    rf_prob: float | None
    xgb_prob: float | None
    ensemble_prob: float | None
    feature_set: str
    home_sp: str | None
    away_sp: str | None
    sp_uncertainty: bool
    sp_may_have_changed: bool
    kalshi_yes_price: float | None
    edge_signal: str | None
    edge_magnitude: float | None
    created_at: datetime
    game_time: datetime | None = None
    actual_winner: str | None = None
    prediction_correct: bool | None = None


class TodayResponse(BaseModel):
    """Response shape for /predictions/today and /predictions/{date}."""

    predictions: list[PredictionResponse]
    latest_prediction_at: datetime | None
    generated_at: datetime


class LatestTimestampResponse(BaseModel):
    """Response shape for /predictions/latest-timestamp."""

    timestamp: datetime | None


class AccuracyResponse(BaseModel):
    """Response shape for /results/accuracy."""

    models: dict[str, dict]
    training_date: str


class HealthResponse(BaseModel):
    """Response shape for /health."""

    status: str
    last_pipeline_runs: dict
    checked_at: str


class PredictionGroup(BaseModel):
    """Pre-lineup and/or post-lineup predictions for a single game."""

    pre_lineup: PredictionResponse | None = None
    post_lineup: PredictionResponse | None = None


class LiveScoreData(BaseModel):
    """Live game score and state data, populated only for LIVE games."""

    away_score: int
    home_score: int
    inning: int
    inning_half: Literal['top', 'bottom']
    outs: int
    balls: int
    strikes: int
    runner_on_1b: bool
    runner_on_2b: bool
    runner_on_3b: bool
    current_batter: str | None
    batter_avg: str | None
    batter_ops: str | None
    on_deck_batter: str | None


class GameResponse(BaseModel):
    """Single game entry for the /games/{date} endpoint."""

    game_id: int
    home_team: str
    away_team: str
    game_time: datetime | None
    game_status: Literal['PRE_GAME', 'LIVE', 'FINAL', 'POSTPONED']
    prediction: PredictionGroup | None = None
    prediction_label: Literal['PRELIMINARY'] | None = None
    home_probable_pitcher: str | None = None
    away_probable_pitcher: str | None = None
    live_score: LiveScoreData | None = None
    home_final_score: int | None = None
    away_final_score: int | None = None
    actual_winner: str | None = None
    prediction_correct: bool | None = None


class GamesDateResponse(BaseModel):
    """Response shape for GET /games/{date}."""

    games: list[GameResponse]
    generated_at: datetime
    view_mode: Literal['live', 'historical', 'tomorrow', 'future']


# ---------------------------------------------------------------------------
# History endpoint models (Phase 18)
# ---------------------------------------------------------------------------


class HistoryRow(BaseModel):
    """Single game row for the /history endpoint."""

    game_date: date
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    lr_prob: float | None = None
    rf_prob: float | None = None
    xgb_prob: float | None = None
    ensemble_prob: float | None = None
    prediction_correct: bool


class ModelAccuracy(BaseModel):
    """Per-model accuracy stats for a date range."""

    correct: int
    total: int
    pct: float


class HistoryResponse(BaseModel):
    """Response shape for GET /history."""

    games: list[HistoryRow]
    accuracy: dict[str, ModelAccuracy]
    start_date: date
    end_date: date
