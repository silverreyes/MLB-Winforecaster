"""Unit tests for extended pitcher game log extraction and SP recent form computation.

Tests cover:
  - v2 game log extraction (8 columns including K/BB/HR/numberOfPitches)
  - v2 versioned cache key (prevents stale 3-column cache reuse)
  - _parse_ip edge cases
  - 30-day rolling raw FIP computation
  - Pitch count from last start and days rest computation
  - Cold-start imputation (league-average 93 pitches, 7-day cap)
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.features.sp_recent_form import (
    _fetch_pitcher_game_log_v2,
    _parse_ip,
    compute_rolling_fip_bulk,
    compute_pitch_count_and_rest_bulk,
    V2_GAME_LOG_COLS,
    LEAGUE_AVG_PITCH_COUNT,
    MAX_DAYS_REST,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_response_one_split():
    """Simulated MLB Stats API gameLog response with one split containing all 8 fields."""
    return {
        "people": [{
            "stats": [{
                "splits": [{
                    "date": "2024-04-01",
                    "stat": {
                        "inningsPitched": "6.0",
                        "earnedRuns": 2,
                        "strikeOuts": 7,
                        "baseOnBalls": 2,
                        "homeRuns": 1,
                        "numberOfPitches": 98,
                        "gamesStarted": 1,
                    },
                }],
            }],
        }],
    }


def _make_v2_cached_df():
    """A pre-cached v2 game log DataFrame with all 8 columns."""
    return pd.DataFrame([{
        "date": pd.Timestamp("2024-04-01"),
        "innings_pitched": 6.0,
        "earned_runs": 2,
        "strikeouts": 7,
        "base_on_balls": 2,
        "home_runs": 1,
        "number_of_pitches": 98,
        "games_started": 1,
    }])


def _make_game_log_for_fip():
    """Synthetic game log for FIP computation: 6 starts over 40 days.

    Day 1:  IP=6, K=7, BB=2, HR=1, pitches=95, GS=1
    Day 6:  IP=5.667 (5.2), K=5, BB=3, HR=0, pitches=100, GS=1
    Day 11: IP=7, K=9, BB=1, HR=1, pitches=105, GS=1
    Day 16: IP=6, K=6, BB=2, HR=2, pitches=92, GS=1
    Day 21: IP=5, K=4, BB=4, HR=1, pitches=88, GS=1
    Day 35: IP=6, K=8, BB=1, HR=0, pitches=97, GS=1
    """
    base = pd.Timestamp("2024-06-01")
    return pd.DataFrame([
        {"date": base + timedelta(days=0), "innings_pitched": 6.0, "earned_runs": 2,
         "strikeouts": 7, "base_on_balls": 2, "home_runs": 1, "number_of_pitches": 95, "games_started": 1},
        {"date": base + timedelta(days=5), "innings_pitched": 5 + 2 / 3, "earned_runs": 3,
         "strikeouts": 5, "base_on_balls": 3, "home_runs": 0, "number_of_pitches": 100, "games_started": 1},
        {"date": base + timedelta(days=10), "innings_pitched": 7.0, "earned_runs": 1,
         "strikeouts": 9, "base_on_balls": 1, "home_runs": 1, "number_of_pitches": 105, "games_started": 1},
        {"date": base + timedelta(days=15), "innings_pitched": 6.0, "earned_runs": 4,
         "strikeouts": 6, "base_on_balls": 2, "home_runs": 2, "number_of_pitches": 92, "games_started": 1},
        {"date": base + timedelta(days=20), "innings_pitched": 5.0, "earned_runs": 2,
         "strikeouts": 4, "base_on_balls": 4, "home_runs": 1, "number_of_pitches": 88, "games_started": 1},
        {"date": base + timedelta(days=34), "innings_pitched": 6.0, "earned_runs": 1,
         "strikeouts": 8, "base_on_balls": 1, "home_runs": 0, "number_of_pitches": 97, "games_started": 1},
    ])


def _make_game_log_for_pitch_count():
    """Synthetic game log for pitch count and days rest tests.

    Day 1:  95 pitches, GS=1
    Day 6:  102 pitches, GS=1
    Day 11: 88 pitches, GS=1
    """
    base = pd.Timestamp("2024-06-01")
    return pd.DataFrame([
        {"date": base + timedelta(days=0), "innings_pitched": 6.0, "earned_runs": 2,
         "strikeouts": 5, "base_on_balls": 2, "home_runs": 1, "number_of_pitches": 95, "games_started": 1},
        {"date": base + timedelta(days=5), "innings_pitched": 7.0, "earned_runs": 1,
         "strikeouts": 8, "base_on_balls": 1, "home_runs": 0, "number_of_pitches": 102, "games_started": 1},
        {"date": base + timedelta(days=10), "innings_pitched": 5.0, "earned_runs": 3,
         "strikeouts": 4, "base_on_balls": 3, "home_runs": 1, "number_of_pitches": 88, "games_started": 1},
    ])


# ---------------------------------------------------------------------------
# Tests: v2 game log extraction
# ---------------------------------------------------------------------------

class TestFetchGameLogV2:

    @patch("src.features.sp_recent_form.save_to_cache")
    @patch("src.features.sp_recent_form.is_cached", return_value=False)
    @patch("src.features.sp_recent_form.statsapi")
    def test_fetch_game_log_v2_columns(self, mock_api, mock_cached, mock_save):
        """v2 game log returns all 8 columns with correct values."""
        mock_api.get.return_value = _make_api_response_one_split()

        result = _fetch_pitcher_game_log_v2(player_id=543037, season=2024)

        expected_cols = [
            "date", "innings_pitched", "earned_runs", "strikeouts",
            "base_on_balls", "home_runs", "number_of_pitches", "games_started",
        ]
        assert list(result.columns) == expected_cols
        assert len(result) == 1

        row = result.iloc[0]
        assert row["strikeouts"] == 7
        assert row["base_on_balls"] == 2
        assert row["home_runs"] == 1
        assert row["number_of_pitches"] == 98
        assert row["games_started"] == 1
        assert row["innings_pitched"] == 6.0
        assert row["earned_runs"] == 2

    @patch("src.features.sp_recent_form.read_cached")
    @patch("src.features.sp_recent_form.is_cached", return_value=True)
    @patch("src.features.sp_recent_form.statsapi")
    def test_fetch_game_log_v2_cache_key(self, mock_api, mock_cached, mock_read):
        """v2 function uses versioned cache key 'pitcher_game_log_v2_...' and respects cache."""
        mock_read.return_value = _make_v2_cached_df()

        result = _fetch_pitcher_game_log_v2(player_id=543037, season=2024)

        # Should have called is_cached with the v2 key
        mock_cached.assert_called_once_with("pitcher_game_log_v2_2024_543037")
        # Should have read from cache, NOT called the API
        mock_read.assert_called_once_with("pitcher_game_log_v2_2024_543037")
        mock_api.get.assert_not_called()

        # Verify returned data
        assert len(result) == 1
        assert result.iloc[0]["strikeouts"] == 7


# ---------------------------------------------------------------------------
# Tests: _parse_ip edge cases
# ---------------------------------------------------------------------------

class TestParseIP:

    def test_normal_innings(self):
        assert _parse_ip("5.0") == 5.0

    def test_one_out(self):
        assert _parse_ip("5.1") == pytest.approx(5 + 1 / 3)

    def test_two_outs(self):
        assert _parse_ip("5.2") == pytest.approx(5 + 2 / 3)

    def test_zero_innings(self):
        assert _parse_ip("0.0") == 0.0

    def test_zero_one_out(self):
        assert _parse_ip("0.1") == pytest.approx(1 / 3)

    def test_none_returns_zero(self):
        assert _parse_ip(None) == 0.0


# ---------------------------------------------------------------------------
# Tests: 30-day rolling FIP
# ---------------------------------------------------------------------------

class TestComputeRollingFIP:

    @patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2")
    @patch("src.features.sp_recent_form._get_pitcher_id_map")
    def test_compute_rolling_fip_30day(self, mock_id_map, mock_fetch_v2):
        """Rolling FIP uses 30-day window and computes raw FIP correctly."""
        mock_id_map.return_value = {"Test Pitcher": 100001}
        mock_fetch_v2.return_value = _make_game_log_for_fip()

        base = pd.Timestamp("2024-06-01")
        # Query date = Day 22 = base + 21 days
        query_date = (base + timedelta(days=21)).strftime("%Y-%m-%d")

        result = compute_rolling_fip_bulk(
            game_dates=[query_date],
            season=2024,
            sp_names={"Test Pitcher"},
        )

        assert query_date in result
        df = result[query_date]
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Test Pitcher"

        # Window: [query_date - 31 days, query_date)
        # query_date = 2024-06-22
        # window_start = 2024-05-22
        # Starts in window: Day 1 (Jun 1), Day 6 (Jun 6), Day 11 (Jun 11),
        #                    Day 16 (Jun 16), Day 21 (Jun 21) -- all >= May 22 and < Jun 22
        # Day 35 (Jul 5) is NOT in window (it's after query date).
        sum_hr = 1 + 0 + 1 + 2 + 1  # = 5
        sum_bb = 2 + 3 + 1 + 2 + 4  # = 12
        sum_k = 7 + 5 + 9 + 6 + 4   # = 31
        sum_ip = 6.0 + (5 + 2 / 3) + 7.0 + 6.0 + 5.0  # = 29.667

        expected_fip = ((13 * sum_hr) + (3 * sum_bb) - (2 * sum_k)) / sum_ip

        assert df.iloc[0]["FIP"] == pytest.approx(expected_fip, abs=0.01)

    @patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2")
    @patch("src.features.sp_recent_form._get_pitcher_id_map")
    def test_compute_rolling_fip_zero_ip(self, mock_id_map, mock_fetch_v2):
        """Pitcher with no IP in window is excluded from FIP results."""
        mock_id_map.return_value = {"No Starts": 100002}
        mock_fetch_v2.return_value = pd.DataFrame(columns=V2_GAME_LOG_COLS)

        result = compute_rolling_fip_bulk(
            game_dates=["2024-06-22"],
            season=2024,
            sp_names={"No Starts"},
        )

        df = result["2024-06-22"]
        assert len(df) == 0


# ---------------------------------------------------------------------------
# Tests: pitch count and days rest
# ---------------------------------------------------------------------------

class TestComputePitchCountAndRest:

    @patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2")
    @patch("src.features.sp_recent_form._get_pitcher_id_map")
    def test_compute_pitch_count_and_rest(self, mock_id_map, mock_fetch_v2):
        """Pitch count and days rest from most recent prior start."""
        mock_id_map.return_value = {"Test Pitcher": 100001}
        mock_fetch_v2.return_value = _make_game_log_for_pitch_count()

        base = pd.Timestamp("2024-06-01")

        # Query date = Day 12 (base + 11 days)
        query_day12 = (base + timedelta(days=11)).strftime("%Y-%m-%d")
        # Query date = Day 7 (base + 6 days)
        query_day7 = (base + timedelta(days=6)).strftime("%Y-%m-%d")

        result = compute_pitch_count_and_rest_bulk(
            game_dates=[query_day12, query_day7],
            season=2024,
            sp_names={"Test Pitcher"},
        )

        # Day 12: last start = Day 11 (88 pitches), days_rest = 1
        df12 = result[query_day12]
        assert len(df12) == 1
        assert df12.iloc[0]["pitch_count_last"] == 88
        assert df12.iloc[0]["days_rest"] == 1

        # Day 7: last start = Day 6 (102 pitches), days_rest = 1
        df7 = result[query_day7]
        assert len(df7) == 1
        assert df7.iloc[0]["pitch_count_last"] == 102
        assert df7.iloc[0]["days_rest"] == 1

    @patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2")
    @patch("src.features.sp_recent_form._get_pitcher_id_map")
    def test_pitch_count_cold_start_imputation(self, mock_id_map, mock_fetch_v2):
        """Cold start: no prior start uses league-avg 93 pitches and 7-day cap."""
        base = pd.Timestamp("2024-06-10")
        mock_id_map.return_value = {"Rookie Pitcher": 100003}
        # Only one start on Day 10 -- so querying Day 10 means no PRIOR start
        mock_fetch_v2.return_value = pd.DataFrame([{
            "date": base,
            "innings_pitched": 5.0,
            "earned_runs": 3,
            "strikeouts": 4,
            "base_on_balls": 2,
            "home_runs": 1,
            "number_of_pitches": 90,
            "games_started": 1,
        }])

        query_date = base.strftime("%Y-%m-%d")
        result = compute_pitch_count_and_rest_bulk(
            game_dates=[query_date],
            season=2024,
            sp_names={"Rookie Pitcher"},
        )

        df = result[query_date]
        assert len(df) == 1
        assert df.iloc[0]["pitch_count_last"] == LEAGUE_AVG_PITCH_COUNT  # 93
        assert df.iloc[0]["days_rest"] == MAX_DAYS_REST  # 7

    @patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2")
    @patch("src.features.sp_recent_form._get_pitcher_id_map")
    def test_days_rest_capped_at_max(self, mock_id_map, mock_fetch_v2):
        """Days rest is capped at MAX_DAYS_REST (7) even if gap is larger."""
        base = pd.Timestamp("2024-06-01")
        mock_id_map.return_value = {"Test Pitcher": 100001}
        mock_fetch_v2.return_value = pd.DataFrame([{
            "date": base,
            "innings_pitched": 6.0,
            "earned_runs": 2,
            "strikeouts": 5,
            "base_on_balls": 2,
            "home_runs": 1,
            "number_of_pitches": 95,
            "games_started": 1,
        }])

        # Query 15 days later -- gap = 15, should be capped at 7
        query_date = (base + timedelta(days=15)).strftime("%Y-%m-%d")
        result = compute_pitch_count_and_rest_bulk(
            game_dates=[query_date],
            season=2024,
            sp_names={"Test Pitcher"},
        )

        df = result[query_date]
        assert df.iloc[0]["days_rest"] == MAX_DAYS_REST  # 7 (capped)
        assert df.iloc[0]["pitch_count_last"] == 95
