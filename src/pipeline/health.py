"""Health check data aggregation for GET /api/v1/health.

Provides structured health data including last pipeline run timestamps
and status for each prediction version.
"""
import logging
from datetime import datetime, timezone

from src.pipeline.db import get_latest_pipeline_runs

logger = logging.getLogger(__name__)


def get_health_data(pool) -> dict:
    """Aggregate health data from pipeline_runs table.

    Returns:
        Dict with structure:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "last_pipeline_runs": {
                "pre_lineup": {"run_date": "...", "status": "...", "run_finished_at": "...", "games_processed": N},
                "post_lineup": {...},
                "confirmation": {...},
            },
            "checked_at": "ISO8601 timestamp",
        }
    """
    try:
        runs = get_latest_pipeline_runs(pool)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_pipeline_runs": {},
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    runs_by_version = {}
    for run in runs:
        version = run.get("prediction_version")
        runs_by_version[version] = {
            "run_date": str(run.get("run_date", "")),
            "status": run.get("status", "unknown"),
            "run_finished_at": run.get("run_finished_at", "").isoformat() if run.get("run_finished_at") else None,
            "games_processed": run.get("games_processed", 0),
        }

    # Determine overall status
    statuses = [r.get("status") for r in runs_by_version.values()]
    if not statuses:
        overall = "unhealthy"
    elif all(s == "success" for s in statuses):
        overall = "healthy"
    elif any(s == "failed" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "last_pipeline_runs": runs_by_version,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
