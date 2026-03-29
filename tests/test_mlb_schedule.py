"""Test stubs for MLB schedule data loader (DATA-01).

These tests define the expected interface and behavior for src.data.mlb_schedule.
They will be skipped until the loader module is implemented in Plan 02.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Skip entire module if loader not yet implemented
mlb_schedule = pytest.importorskip("src.data.mlb_schedule")


# Sample data mimicking statsapi.schedule() output (list of game dicts)
SAMPLE_SCHEDULE_DATA = [
    {
        "game_id": 718001,
        "game_date": "2023-04-01",
        "game_type": "R",
        "home_name": "New York Yankees",
        "away_name": "Boston Red Sox",
        "home_probable_pitcher": "Gerrit Cole",
        "away_probable_pitcher": "Chris Sale",
        "home_score": 5,
        "away_score": 3,
        "winning_team": "New York Yankees",
        "losing_team": "Boston Red Sox",
        "status": "Final",
    },
    {
        "game_id": 718002,
        "game_date": "2023-04-01",
        "game_type": "R",
        "home_name": "Los Angeles Dodgers",
        "away_name": "San Francisco Giants",
        "home_probable_pitcher": "Clayton Kershaw",
        "away_probable_pitcher": "Logan Webb",
        "home_score": 2,
        "away_score": 4,
        "winning_team": "San Francisco Giants",
        "losing_team": "Los Angeles Dodgers",
        "status": "Final",
    },
]

# Sample schedule for 2025 to test SEASON_DATES coverage
SAMPLE_2025_SCHEDULE = [
    {
        "game_id": 750001,
        "game_date": "2025-03-27",
        "game_type": "R",
        "home_name": "Chicago Cubs",
        "away_name": "Chicago White Sox",
        "home_probable_pitcher": "TBD",
        "away_probable_pitcher": "TBD",
        "home_score": 0,
        "away_score": 0,
        "winning_team": "",
        "losing_team": "",
        "status": "Scheduled",
    },
]


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_fetch_schedule_returns_dataframe(mock_schedule, mock_cache_dir):
    """fetch_schedule(2023) returns a pandas DataFrame."""
    mock_schedule.return_value = SAMPLE_SCHEDULE_DATA
    result = mlb_schedule.fetch_schedule(2023)
    assert isinstance(result, pd.DataFrame)


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_schedule_has_pitcher_columns(mock_schedule, mock_cache_dir):
    """Result has home_probable_pitcher and away_probable_pitcher columns."""
    mock_schedule.return_value = SAMPLE_SCHEDULE_DATA
    result = mlb_schedule.fetch_schedule(2023)
    assert "home_probable_pitcher" in result.columns
    assert "away_probable_pitcher" in result.columns


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_schedule_has_team_columns(mock_schedule, mock_cache_dir):
    """Result has home_team and away_team columns (normalized)."""
    mock_schedule.return_value = SAMPLE_SCHEDULE_DATA
    result = mlb_schedule.fetch_schedule(2023)
    assert "home_team" in result.columns
    assert "away_team" in result.columns


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_schedule_has_game_result(mock_schedule, mock_cache_dir):
    """Result has score or winning_team columns for game results."""
    mock_schedule.return_value = SAMPLE_SCHEDULE_DATA
    result = mlb_schedule.fetch_schedule(2023)
    has_scores = "home_score" in result.columns and "away_score" in result.columns
    has_winner = "winning_team" in result.columns
    assert has_scores or has_winner, (
        "Need either home_score/away_score or winning_team columns"
    )


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_schedule_caches_to_parquet(mock_schedule, mock_cache_dir):
    """After fetch, is_cached('schedule_2023') returns True."""
    from src.data.cache import is_cached

    mock_schedule.return_value = SAMPLE_SCHEDULE_DATA
    mlb_schedule.fetch_schedule(2023)
    assert is_cached("schedule_2023")


@patch("src.data.mlb_schedule.statsapi_schedule")
def test_schedule_2025_does_not_raise(mock_schedule, mock_cache_dir):
    """fetch_schedule(2025) does not raise ValueError -- 2025 is in SEASON_DATES.

    This test confirms that 2025 was explicitly added to the SEASON_DATES
    mapping. Without this test, the 2025 addition could silently be reverted.
    """
    mock_schedule.return_value = SAMPLE_2025_SCHEDULE
    # Should not raise ValueError about unsupported season
    result = mlb_schedule.fetch_schedule(2025)
    assert isinstance(result, pd.DataFrame)
