"""Pydantic response models for all API endpoints.

Defines the JSON shapes returned by each route handler. All models
use strict typing with Optional fields for nullable database columns.
"""

from datetime import date, datetime

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
