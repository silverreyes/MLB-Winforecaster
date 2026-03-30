"""Accuracy route handler for the MLB Win Forecaster API.

Provides GET /results/accuracy (API-04): Returns Brier scores from
model_metadata.json for all 6 models.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models import AccuracyResponse

router = APIRouter(tags=["accuracy"])

_METADATA_PATH = Path("models/artifacts/model_metadata.json")


@router.get("/results/accuracy", response_model=AccuracyResponse)
def get_accuracy():
    """Return model Brier scores and training date (API-04)."""
    try:
        with open(_METADATA_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model metadata not found")

    return AccuracyResponse(
        models=data["models"],
        training_date=data.get("training_date", "unknown"),
    )
