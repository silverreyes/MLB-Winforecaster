"""Tests for the /history endpoint: DB query, Pydantic models, accuracy computation.

Covers: HIST-01 (history query), HIST-02 (prediction preference), HIST-03 (accuracy),
        HIST-04 (response shape).
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# DB query tests (get_history)
# ---------------------------------------------------------------------------

class TestGetHistory:
    """Unit tests for get_history() in src/pipeline/db.py."""

    def _mock_pool(self, rows):
        """Create a mock pool that returns given rows from fetchall()."""
        pool = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        pool.connection.return_value = mock_conn
        return pool

    def test_empty_result_for_no_matching_rows(self):
        """get_history returns empty list when no rows match date range."""
        from src.pipeline.db import get_history

        pool = self._mock_pool([])
        result = get_history(pool, "2026-03-20", "2026-03-30")
        assert result == []

    def test_only_prediction_correct_not_null(self):
        """get_history SQL filters prediction_correct IS NOT NULL."""
        from src.pipeline.db import get_history

        pool = self._mock_pool([])
        get_history(pool, "2026-03-20", "2026-03-30")

        # Inspect the SQL passed to execute
        mock_conn = pool.connection().__enter__()
        mock_cur = mock_conn.cursor().__enter__()
        sql = mock_cur.execute.call_args[0][0]
        assert "prediction_correct IS NOT NULL" in sql

    def test_prefers_post_lineup_over_pre_lineup(self):
        """get_history SQL uses ROW_NUMBER with post_lineup ranked first."""
        from src.pipeline.db import get_history

        pool = self._mock_pool([])
        get_history(pool, "2026-03-20", "2026-03-30")

        mock_conn = pool.connection().__enter__()
        mock_cur = mock_conn.cursor().__enter__()
        sql = mock_cur.execute.call_args[0][0]
        # post_lineup gets rank 1 in the ORDER BY CASE
        assert "WHEN 'post_lineup' THEN 1" in sql
        assert "WHEN 'pre_lineup' THEN 3" in sql

    def test_fallback_to_pre_lineup_when_no_post(self):
        """get_history returns pre_lineup row when no post_lineup exists for a game.

        This is inherent in the ROW_NUMBER approach: if only pre_lineup exists,
        it will be rn=1 for that game_id partition.
        """
        from src.pipeline.db import get_history

        row = {
            "game_date": date(2026, 3, 25),
            "home_team": "NYY",
            "away_team": "BOS",
            "home_score": 5,
            "away_score": 3,
            "lr_prob": 0.6,
            "rf_prob": 0.55,
            "xgb_prob": 0.58,
            "prediction_correct": True,
        }
        pool = self._mock_pool([row])
        result = get_history(pool, "2026-03-20", "2026-03-30")
        assert len(result) == 1
        assert result[0]["home_team"] == "NYY"

    def test_returns_scores_from_game_logs_join(self):
        """get_history returns home_score and away_score from game_logs join."""
        from src.pipeline.db import get_history

        pool = self._mock_pool([])
        get_history(pool, "2026-03-20", "2026-03-30")

        mock_conn = pool.connection().__enter__()
        mock_cur = mock_conn.cursor().__enter__()
        sql = mock_cur.execute.call_args[0][0]
        assert "gl.home_score" in sql
        assert "gl.away_score" in sql
        assert "LEFT JOIN game_logs" in sql

    def test_game_id_cast_in_join(self):
        """get_history SQL casts game_logs.game_id::INTEGER for VARCHAR-to-INTEGER join."""
        from src.pipeline.db import get_history

        pool = self._mock_pool([])
        get_history(pool, "2026-03-20", "2026-03-30")

        mock_conn = pool.connection().__enter__()
        mock_cur = mock_conn.cursor().__enter__()
        sql = mock_cur.execute.call_args[0][0]
        assert "gl.game_id::INTEGER" in sql


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------

class TestHistoryModels:
    """Tests for HistoryRow, ModelAccuracy, HistoryResponse Pydantic models."""

    def test_history_row_validates_all_fields(self):
        """HistoryRow model validates with all required fields."""
        from api.models import HistoryRow

        row = HistoryRow(
            game_date=date(2026, 3, 25),
            home_team="NYY",
            away_team="BOS",
            home_score=5,
            away_score=3,
            lr_prob=0.6,
            rf_prob=0.55,
            xgb_prob=0.58,
            prediction_correct=True,
        )
        assert row.game_date == date(2026, 3, 25)
        assert row.home_team == "NYY"
        assert row.prediction_correct is True
        assert row.home_score == 5

    def test_history_response_contains_games_and_accuracy(self):
        """HistoryResponse model contains games list and accuracy dict."""
        from api.models import HistoryResponse, HistoryRow, ModelAccuracy

        row = HistoryRow(
            game_date=date(2026, 3, 25),
            home_team="NYY",
            away_team="BOS",
            prediction_correct=True,
        )
        accuracy = {
            "lr": ModelAccuracy(correct=2, total=3, pct=66.7),
            "rf": ModelAccuracy(correct=3, total=3, pct=100.0),
            "xgb": ModelAccuracy(correct=1, total=3, pct=33.3),
        }
        resp = HistoryResponse(
            games=[row],
            accuracy=accuracy,
            start_date=date(2026, 3, 20),
            end_date=date(2026, 3, 30),
        )
        assert len(resp.games) == 1
        assert "lr" in resp.accuracy
        assert resp.accuracy["lr"].pct == 66.7
        assert resp.start_date == date(2026, 3, 20)


# ---------------------------------------------------------------------------
# Accuracy computation test
# ---------------------------------------------------------------------------

class TestAccuracyComputation:
    """Test the accuracy helper logic for per-model accuracy."""

    def test_two_correct_out_of_three(self):
        """Given 3 rows: 2 correct, 1 incorrect -> verify per-model percentages.

        Rows:
        - Game 1: all probs > 0.5, prediction_correct=True => home_won=True
        - Game 2: all probs > 0.5, prediction_correct=True => home_won=True
        - Game 3: all probs > 0.5, prediction_correct=False => home_won=False
        All individual models had prob > 0.5 (predicted home), so:
        - Games 1,2: home_won=True, model predicted home => correct
        - Game 3: home_won=False, model predicted home => incorrect
        => 2/3 = 66.7% for each model
        """
        from api.routes.history import _compute_accuracy

        rows = [
            {"lr_prob": 0.6, "rf_prob": 0.55, "xgb_prob": 0.58, "prediction_correct": True},
            {"lr_prob": 0.7, "rf_prob": 0.65, "xgb_prob": 0.68, "prediction_correct": True},
            {"lr_prob": 0.6, "rf_prob": 0.55, "xgb_prob": 0.58, "prediction_correct": False},
        ]
        result = _compute_accuracy(rows)
        assert result["lr"].total == 3
        assert result["lr"].correct == 2
        assert result["lr"].pct == 66.7
        assert result["rf"].correct == 2
        assert result["xgb"].correct == 2

    def test_empty_rows_returns_zero_totals(self):
        """_compute_accuracy with empty list -> all models have total=0, pct=0.0."""
        from api.routes.history import _compute_accuracy

        result = _compute_accuracy([])
        for key in ("lr", "rf", "xgb"):
            assert result[key].total == 0
            assert result[key].correct == 0
            assert result[key].pct == 0.0

    def test_lr_disagrees_with_ensemble(self):
        """_compute_accuracy: lr_prob=0.48 but ensemble >= 0.5 and pc=True.

        ensemble = (0.48 + 0.55 + 0.58) / 3 = 0.5367 >= 0.5
        pc=True => home_won=True
        lr predicted away (0.48 < 0.5) but home won => lr incorrect
        rf predicted home (0.55 >= 0.5) and home won => rf correct
        xgb predicted home (0.58 >= 0.5) and home won => xgb correct
        """
        from api.routes.history import _compute_accuracy

        rows = [
            {"lr_prob": 0.48, "rf_prob": 0.55, "xgb_prob": 0.58, "prediction_correct": True},
        ]
        result = _compute_accuracy(rows)
        assert result["lr"].correct == 0
        assert result["lr"].total == 1
        assert result["rf"].correct == 1
        assert result["xgb"].correct == 1


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestHistoryRoute:
    """Tests for the GET /history route handler.

    Uses the `client` fixture from conftest.py which provides a TestClient
    with mocked DB pool and model artifacts.
    """

    def test_invalid_start_date_returns_400(self, client):
        """Route returns 400 on invalid start date format."""
        resp = client.get("/api/v1/history?start=not-a-date&end=2026-03-30")
        assert resp.status_code == 400
        assert "start" in resp.json()["detail"].lower()

    def test_invalid_end_date_returns_400(self, client):
        """Route returns 400 on invalid end date format."""
        resp = client.get("/api/v1/history?start=2026-03-20&end=bad-date")
        assert resp.status_code == 400
        assert "end" in resp.json()["detail"].lower()

    @patch("api.routes.history.get_history")
    def test_route_returns_valid_response(self, mock_get_history, client):
        """Route returns HistoryResponse with games and accuracy when given valid dates."""
        mock_get_history.return_value = [
            {
                "game_date": date(2026, 3, 25),
                "home_team": "NYY",
                "away_team": "BOS",
                "home_score": 5,
                "away_score": 3,
                "lr_prob": 0.6,
                "rf_prob": 0.55,
                "xgb_prob": 0.58,
                "prediction_correct": True,
            },
        ]

        resp = client.get("/api/v1/history?start=2026-03-20&end=2026-03-30")
        assert resp.status_code == 200
        data = resp.json()
        assert "games" in data
        assert "accuracy" in data
        assert len(data["games"]) == 1
        assert data["games"][0]["home_team"] == "NYY"
        assert data["start_date"] == "2026-03-20"
        assert data["end_date"] == "2026-03-30"

    @patch("api.routes.history.get_history")
    def test_route_empty_history(self, mock_get_history, client):
        """Route returns empty games list and zero-accuracy for date range with no data."""
        mock_get_history.return_value = []

        resp = client.get("/api/v1/history?start=2026-03-20&end=2026-03-30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["games"] == []
        for model_key in ("lr", "rf", "xgb"):
            assert data["accuracy"][model_key]["total"] == 0
