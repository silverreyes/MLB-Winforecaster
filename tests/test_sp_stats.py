"""Test stubs for starting pitcher stats loader (DATA-03).

These tests define the expected interface and behavior for src.data.sp_stats.
They will be skipped until the loader module is implemented in Plan 02.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Skip entire module if loader not yet implemented
sp_stats = pytest.importorskip("src.data.sp_stats")


# Sample data mimicking pybaseball.pitching_stats() output
SAMPLE_PITCHING_DATA = pd.DataFrame({
    "Name": ["Gerrit Cole", "Max Scherzer", "Nestor Cortes", "Relief Pitcher"],
    "Team": ["NYY", "NYM", "NYY", "BOS"],
    "W": [15, 12, 10, 3],
    "L": [5, 8, 6, 2],
    "ERA": [2.90, 3.20, 3.50, 4.00],
    "G": [30, 28, 28, 60],
    "GS": [30, 28, 28, 0],  # Last pitcher is a reliever
    "IP": [200.0, 185.0, 170.0, 70.0],
    "FIP": [2.80, 3.10, 3.40, 3.80],
    "xFIP": [2.90, 3.20, 3.50, 3.90],
    "K%": [0.310, 0.290, 0.260, 0.280],
    "BB%": [0.060, 0.070, 0.080, 0.090],
    "WHIP": [0.95, 1.05, 1.10, 1.25],
})


@patch("src.data.sp_stats.pybaseball_pitching_stats")
def test_fetch_sp_stats_returns_dataframe(mock_pitching, mock_cache_dir):
    """fetch_sp_stats(2023) returns a pandas DataFrame."""
    mock_pitching.return_value = SAMPLE_PITCHING_DATA.copy()
    result = sp_stats.fetch_sp_stats(2023)
    assert isinstance(result, pd.DataFrame)


@patch("src.data.sp_stats.pybaseball_pitching_stats")
def test_sp_stats_has_required_columns(mock_pitching, mock_cache_dir):
    """Result has required columns: FIP, xFIP, K%, BB%, WHIP, Name, Team."""
    mock_pitching.return_value = SAMPLE_PITCHING_DATA.copy()
    result = sp_stats.fetch_sp_stats(2023)
    required = ["FIP", "xFIP", "K%", "BB%", "WHIP", "Name", "Team"]
    for col in required:
        assert col in result.columns, f"Missing column: {col}"


@patch("src.data.sp_stats.pybaseball_pitching_stats")
def test_sp_stats_filters_to_starters(mock_pitching, mock_cache_dir):
    """Only rows with GS > 0 are returned (relievers filtered out)."""
    mock_pitching.return_value = SAMPLE_PITCHING_DATA.copy()
    result = sp_stats.fetch_sp_stats(2023)
    assert len(result) == 3  # Relief Pitcher should be filtered out
    assert (result["GS"] > 0).all()


@patch("src.data.sp_stats.pybaseball_pitching_stats")
def test_sp_stats_2020_has_shortened_flag(mock_pitching, mock_cache_dir):
    """2020 season data has is_shortened_season=True and season_games=60."""
    mock_pitching.return_value = SAMPLE_PITCHING_DATA.copy()
    result = sp_stats.fetch_sp_stats(2020)
    assert "is_shortened_season" in result.columns
    assert result["is_shortened_season"].all()
    assert "season_games" in result.columns
    assert (result["season_games"] == 60).all()


@patch("src.data.sp_stats.pybaseball_pitching_stats")
def test_sp_stats_caches_to_parquet(mock_pitching, mock_cache_dir):
    """After fetch, is_cached('sp_stats_2023_mings1') returns True."""
    from src.data.cache import is_cached

    mock_pitching.return_value = SAMPLE_PITCHING_DATA.copy()
    sp_stats.fetch_sp_stats(2023)
    assert is_cached("sp_stats_2023_mings1")
