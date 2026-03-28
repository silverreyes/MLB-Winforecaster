"""Test stubs for team batting data loader (DATA-02).

These tests define the expected interface and behavior for src.data.team_batting.
They will be skipped until the loader module is implemented in Plan 02.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Skip entire module if loader not yet implemented
team_batting = pytest.importorskip("src.data.team_batting")


# Sample data mimicking pybaseball.team_batting() output
SAMPLE_BATTING_DATA = pd.DataFrame({
    "Team": ["NYY", "BOS", "LAD", "HOU", "ATL"],
    "G": [162, 162, 162, 162, 162],
    "PA": [6200, 6100, 6300, 6150, 6250],
    "HR": [230, 200, 250, 220, 240],
    "wOBA": [0.340, 0.310, 0.350, 0.330, 0.345],
    "OPS": [0.780, 0.740, 0.800, 0.770, 0.790],
    "OBP": [0.340, 0.320, 0.350, 0.335, 0.345],
    "SLG": [0.440, 0.420, 0.450, 0.435, 0.445],
})


@patch("src.data.team_batting.pybaseball_team_batting")
def test_fetch_team_batting_returns_dataframe(mock_batting, mock_cache_dir):
    """fetch_team_batting(2023) returns a pandas DataFrame."""
    mock_batting.return_value = SAMPLE_BATTING_DATA.copy()
    result = team_batting.fetch_team_batting(2023)
    assert isinstance(result, pd.DataFrame)


@patch("src.data.team_batting.pybaseball_team_batting")
def test_team_batting_has_required_columns(mock_batting, mock_cache_dir):
    """Result has required columns: wOBA, OPS, OBP, SLG, Team."""
    mock_batting.return_value = SAMPLE_BATTING_DATA.copy()
    result = team_batting.fetch_team_batting(2023)
    required = ["wOBA", "OPS", "OBP", "SLG", "Team"]
    for col in required:
        assert col in result.columns, f"Missing column: {col}"


@patch("src.data.team_batting.pybaseball_team_batting")
def test_team_batting_2020_has_shortened_flag(mock_batting, mock_cache_dir):
    """2020 season data has is_shortened_season=True and season_games=60."""
    mock_batting.return_value = SAMPLE_BATTING_DATA.copy()
    result = team_batting.fetch_team_batting(2020)
    assert "is_shortened_season" in result.columns
    assert result["is_shortened_season"].all()
    assert "season_games" in result.columns
    assert (result["season_games"] == 60).all()


@patch("src.data.team_batting.pybaseball_team_batting")
def test_team_batting_non_2020_has_full_season_flag(mock_batting, mock_cache_dir):
    """Non-2020 season data has is_shortened_season=False and season_games=162."""
    mock_batting.return_value = SAMPLE_BATTING_DATA.copy()
    result = team_batting.fetch_team_batting(2023)
    assert "is_shortened_season" in result.columns
    assert not result["is_shortened_season"].any()
    assert "season_games" in result.columns
    assert (result["season_games"] == 162).all()


@patch("src.data.team_batting.pybaseball_team_batting")
def test_team_batting_caches_to_parquet(mock_batting, mock_cache_dir):
    """After fetch, is_cached('team_batting_2023') returns True."""
    from src.data.cache import is_cached

    mock_batting.return_value = SAMPLE_BATTING_DATA.copy()
    team_batting.fetch_team_batting(2023)
    assert is_cached("team_batting_2023")
