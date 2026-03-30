"""Tests for LiveFeatureBuilder with mocked data sources."""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.pipeline.live_features import LiveFeatureBuilder


@patch("src.pipeline.live_features.FeatureBuilder")
@patch("src.pipeline.live_features.date")
def _make_builder(mock_date, mock_fb_cls):
    """Helper to create a LiveFeatureBuilder with mocked date and FeatureBuilder."""
    mock_date.today.return_value = type("FakeDate", (), {
        "strftime": lambda self, fmt: "2025-07-15",
        "year": 2025,
    })()
    mock_fb_instance = MagicMock()
    mock_fb_cls.return_value = mock_fb_instance
    builder = LiveFeatureBuilder()
    return builder, mock_fb_instance


@patch("src.pipeline.live_features.fetch_today_schedule")
@patch("src.pipeline.live_features.FeatureBuilder")
@patch("src.pipeline.live_features.date")
def test_get_today_games_normalizes_teams(mock_date, mock_fb_cls, mock_fetch):
    """Team names from statsapi are normalized to 3-letter codes."""
    mock_date.today.return_value = type("FakeDate", (), {
        "strftime": lambda self, fmt: "2025-07-15",
        "year": 2025,
    })()
    mock_fb_cls.return_value = MagicMock()

    mock_fetch.return_value = [{
        "game_id": 1,
        "home_name": "New York Yankees",
        "away_name": "Boston Red Sox",
        "home_probable_pitcher": "Gerrit Cole",
        "away_probable_pitcher": "Brayan Bello",
        "game_type": "R",
        "status": "Scheduled",
    }]

    builder = LiveFeatureBuilder()
    games = builder.get_today_games()

    assert len(games) == 1
    assert games[0]["home_team"] == "NYY"
    assert games[0]["away_team"] == "BOS"
    assert games[0]["home_probable_pitcher"] == "Gerrit Cole"
    assert games[0]["away_probable_pitcher"] == "Brayan Bello"
    assert games[0]["game_date"] == "2025-07-15"


@patch("src.pipeline.live_features.fetch_today_schedule")
@patch("src.pipeline.live_features.FeatureBuilder")
@patch("src.pipeline.live_features.date")
def test_get_today_games_handles_tbd_pitcher(mock_date, mock_fb_cls, mock_fetch):
    """Empty string pitchers are normalized to None."""
    mock_date.today.return_value = type("FakeDate", (), {
        "strftime": lambda self, fmt: "2025-07-15",
        "year": 2025,
    })()
    mock_fb_cls.return_value = MagicMock()

    mock_fetch.return_value = [{
        "game_id": 2,
        "home_name": "Los Angeles Dodgers",
        "away_name": "San Francisco Giants",
        "home_probable_pitcher": "",
        "away_probable_pitcher": "Logan Webb",
        "game_type": "R",
        "status": "Scheduled",
    }]

    builder = LiveFeatureBuilder()
    games = builder.get_today_games()

    assert len(games) == 1
    assert games[0]["home_probable_pitcher"] is None
    assert games[0]["away_probable_pitcher"] == "Logan Webb"


def test_sp_confirmed_true():
    """Both pitchers set returns True."""
    game = {
        "home_probable_pitcher": "Gerrit Cole",
        "away_probable_pitcher": "Brayan Bello",
    }
    builder, _ = _make_builder()
    assert builder.sp_confirmed(game) is True


def test_sp_confirmed_false_missing_home():
    """Home pitcher missing returns False."""
    game = {
        "home_probable_pitcher": None,
        "away_probable_pitcher": "Brayan Bello",
    }
    builder, _ = _make_builder()
    assert builder.sp_confirmed(game) is False


def test_sp_confirmed_false_missing_away():
    """Away pitcher missing returns False."""
    game = {
        "home_probable_pitcher": "Gerrit Cole",
        "away_probable_pitcher": None,
    }
    builder, _ = _make_builder()
    assert builder.sp_confirmed(game) is False


@patch("src.pipeline.live_features.FeatureBuilder")
@patch("src.pipeline.live_features.date")
def test_live_feature_builder_initialize(mock_date, mock_fb_cls):
    """initialize() calls build() and sets _initialized flag."""
    mock_date.today.return_value = type("FakeDate", (), {
        "strftime": lambda self, fmt: "2025-07-15",
        "year": 2025,
    })()
    mock_fb_instance = MagicMock()
    mock_fb_instance.build.return_value = pd.DataFrame({
        "game_date": ["2025-07-14"],
        "home_team": ["NYY"],
        "away_team": ["BOS"],
    })
    mock_fb_cls.return_value = mock_fb_instance

    builder = LiveFeatureBuilder()
    assert builder._initialized is False

    builder.initialize()
    assert builder._initialized is True
    mock_fb_instance.build.assert_called_once()

    # Second call should be a no-op
    builder.initialize()
    mock_fb_instance.build.assert_called_once()  # Still only called once


@patch("src.pipeline.live_features.FeatureBuilder")
@patch("src.pipeline.live_features.date")
def test_live_feature_builder_season_and_date(mock_date, mock_fb_cls):
    """LiveFeatureBuilder sets season and today_str from current date."""
    mock_date.today.return_value = type("FakeDate", (), {
        "strftime": lambda self, fmt: "2025-07-15",
        "year": 2025,
    })()
    mock_fb_cls.return_value = MagicMock()

    builder = LiveFeatureBuilder()
    assert builder.season == 2025
    assert builder.today_str == "2025-07-15"
    mock_fb_cls.assert_called_once_with(
        seasons=[2025],
        as_of_date="2025-07-15",
    )
