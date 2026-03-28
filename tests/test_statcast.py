"""Test stubs for Statcast expected stats loader (DATA-04).

These tests define the expected interface and behavior for src.data.statcast.
They will be skipped until the loader module is implemented in Plan 02.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Skip entire module if loader not yet implemented
statcast = pytest.importorskip("src.data.statcast")


# Sample data mimicking pybaseball.statcast_pitcher_expected_stats() output
SAMPLE_STATCAST_DATA = pd.DataFrame({
    "last_name, first_name": ["Cole, Gerrit", "Scherzer, Max", "deGrom, Jacob"],
    "player_id": [543037, 453286, 594798],
    "pa": [800, 750, 700],
    "xwoba": [0.280, 0.290, 0.260],
    "xba": [0.220, 0.230, 0.210],
    "xslg": [0.350, 0.360, 0.330],
    "woba": [0.290, 0.300, 0.270],
    "ba": [0.230, 0.240, 0.220],
})


@patch("src.data.statcast.pybaseball_statcast_pitcher_expected_stats")
def test_fetch_statcast_pitcher_returns_dataframe(mock_statcast, mock_cache_dir):
    """fetch_statcast_pitcher(2023) returns a pandas DataFrame."""
    mock_statcast.return_value = SAMPLE_STATCAST_DATA.copy()
    result = statcast.fetch_statcast_pitcher(2023)
    assert isinstance(result, pd.DataFrame)


@patch("src.data.statcast.pybaseball_statcast_pitcher_expected_stats")
def test_statcast_has_xwoba_column(mock_statcast, mock_cache_dir):
    """Result has xwoba or xwOBA column."""
    mock_statcast.return_value = SAMPLE_STATCAST_DATA.copy()
    result = statcast.fetch_statcast_pitcher(2023)
    has_xwoba = "xwoba" in result.columns or "xwOBA" in result.columns
    assert has_xwoba, f"Missing xwoba/xwOBA column. Columns: {list(result.columns)}"


@patch("src.data.statcast.pybaseball_statcast_pitcher_expected_stats")
def test_statcast_2020_has_shortened_flag(mock_statcast, mock_cache_dir):
    """2020 season data has is_shortened_season=True and season_games=60."""
    mock_statcast.return_value = SAMPLE_STATCAST_DATA.copy()
    result = statcast.fetch_statcast_pitcher(2020)
    assert "is_shortened_season" in result.columns
    assert result["is_shortened_season"].all()
    assert "season_games" in result.columns
    assert (result["season_games"] == 60).all()


@patch("src.data.statcast.pybaseball_statcast_pitcher_expected_stats")
def test_statcast_caches_to_parquet(mock_statcast, mock_cache_dir):
    """After fetch, is_cached('statcast_pitcher_2023') returns True."""
    from src.data.cache import is_cached

    mock_statcast.return_value = SAMPLE_STATCAST_DATA.copy()
    statcast.fetch_statcast_pitcher(2023)
    assert is_cached("statcast_pitcher_2023")
