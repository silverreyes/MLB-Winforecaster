"""FastAPI application for the MLB Win Forecaster API.

Provides read-only endpoints for predictions, accuracy metrics, and
pipeline health. The lifespan context manager initializes the DB
connection pool and loads model artifacts at startup.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.accuracy import router as accuracy_router
from api.routes.games import router as games_router
from api.routes.health import router as health_router
from api.routes.history import router as history_router
from api.routes.predictions import router as predictions_router
from api.spa import SPAStaticFiles
from src.pipeline.db import apply_schema, get_pool
from src.pipeline.inference import load_all_artifacts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB pool and model artifacts at startup; clean up on shutdown."""
    artifacts = load_all_artifacts()  # Raises FileNotFoundError if missing (API-06)
    pool = get_pool(min_size=2, max_size=5)
    apply_schema(pool)
    logging.getLogger("mlb_api").info("Database schema applied")
    app.state.artifacts = artifacts
    app.state.pool = pool
    yield
    pool.close()


app = FastAPI(title="MLB Win Forecaster API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Include API routers -- all under /api/v1 prefix
app.include_router(predictions_router, prefix="/api/v1")
app.include_router(games_router, prefix="/api/v1")
app.include_router(accuracy_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")

# Mount SPA LAST (only if frontend/dist exists, to avoid startup crash during API-only dev)
_dist = Path("frontend/dist")
if _dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(_dist), html=True), name="spa")
