"""Health route handler for the MLB Win Forecaster API.

Provides GET /health (API-05): Returns pipeline status per prediction
version with last run timestamps.
"""

from fastapi import APIRouter, Request

from api.models import HealthResponse
from src.pipeline.health import get_health_data

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request):
    """Return pipeline health status (API-05)."""
    pool = request.app.state.pool
    health_data = get_health_data(pool)
    return HealthResponse(**health_data)
