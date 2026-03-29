"""Full unit tests for FeatureBuilder class (FEAT-01 through FEAT-08).

All data loaders are mocked -- no network calls or cached Parquet files needed.
Tests verify differential computation, rolling features with shift(1),
TBD exclusion, park factors, advanced features, and output schema.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.features.feature_builder import FeatureBuilder
from src.features.formulas import PARK_FACTORS, get_park_factor


# ---------------------------------------------------------------------------
# Shared mock data fixtures
# ---------------------------------------------------------------------------

def _make_schedule(season, n_games=10):
    """Create synthetic schedule for one season with NYY and BOS alternating."""
    rows = []
    pitchers = {
        "NYY": ["Pitcher A", "Pitcher C"],
        "BOS": ["Pitcher B", "Pitcher D"],
    }
    for i in range(n_games):
        game_date = f"{season}-05-{(i + 1):02d}"
        if i % 2 == 0:
            home, away = "NYY", "BOS"
        else:
            home, away = "BOS", "NYY"
        # Alternate pitchers
        home_sp = pitchers[home][i % 2]
        away_sp = pitchers[away][i % 2]
        # NYY wins even games, BOS wins odd games
        winner = home if i % 2 == 0 else away
        loser = away if i % 2 == 0 else home
        rows.append({
            "game_id": 100000 + season * 1000 + i,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "home_probable_pitcher": home_sp,
            "away_probable_pitcher": away_sp,
            "home_score": 5 if winner == home else 3,
            "away_score": 5 if winner == away else 3,
            "winning_team": winner,
            "losing_team": loser,
            "status": "Final",
            "is_shortened_season": season == 2020,
            "season_games": 60 if season == 2020 else 162,
            "season": season,
        })
    return pd.DataFrame(rows)


def _make_schedule_with_tbd(season):
    """Create schedule with 10 normal games + 2 TBD games = 12 total."""
    df = _make_schedule(season, n_games=10)
    # Add 2 games with TBD (None) starters
    tbd_rows = pd.DataFrame([
        {
            "game_id": 100000 + season * 1000 + 90,
            "game_date": f"{season}-05-20",
            "home_team": "NYY", "away_team": "BOS",
            "home_probable_pitcher": None,
            "away_probable_pitcher": "Pitcher B",
            "home_score": 4, "away_score": 3,
            "winning_team": "NYY", "losing_team": "BOS",
            "status": "Final",
            "is_shortened_season": False,
            "season_games": 162,
            "season": season,
        },
        {
            "game_id": 100000 + season * 1000 + 91,
            "game_date": f"{season}-05-21",
            "home_team": "BOS", "away_team": "NYY",
            "home_probable_pitcher": "Pitcher A",
            "away_probable_pitcher": None,
            "home_score": 2, "away_score": 6,
            "winning_team": "NYY", "losing_team": "BOS",
            "status": "Final",
            "is_shortened_season": False,
            "season_games": 162,
            "season": season,
        },
    ])
    return pd.concat([df, tbd_rows], ignore_index=True)


def _make_sp_stats(season, min_gs=1):
    """Create synthetic SP stats with known values."""
    data = {
        "Name": ["Pitcher A", "Pitcher B", "Pitcher C", "Pitcher D"],
        "Team": ["NYY", "BOS", "NYY", "BOS"],
        "W": [15, 12, 10, 8],
        "L": [5, 8, 7, 10],
        "ERA": [3.00, 4.00, 3.50, 4.50],
        "GS": [30, 28, 25, 22] if min_gs >= 1 else [30, 28, 25, 22],
        "IP": [200, 180, 170, 150],
        "FIP": [3.50, 4.20, 3.80, 4.60],
        "xFIP": [3.40, 4.10, 3.70, 4.50],
        "SIERA": [3.30, 4.00, 3.60, 4.40],
        "K%": [0.28, 0.22, 0.25, 0.20],
        "BB%": [0.06, 0.08, 0.07, 0.09],
        "K-BB%": [0.22, 0.14, 0.18, 0.11],
        "WHIP": [1.10, 1.25, 1.15, 1.30],
        "WAR": [5.0, 3.0, 4.0, 2.0],
        "IDfg": [10001, 10002, 10003, 10004],
        "is_shortened_season": [season == 2020] * 4,
        "season_games": [60 if season == 2020 else 162] * 4,
        "season": [season] * 4,
    }
    if min_gs == 0:
        # Add relievers for bullpen stats
        reliever_data = {
            "Name": ["Reliever X", "Reliever Y", "Reliever Z", "Reliever W"],
            "Team": ["NYY", "NYY", "BOS", "BOS"],
            "W": [3, 2, 4, 1],
            "L": [2, 3, 1, 4],
            "ERA": [3.00, 3.50, 4.00, 4.50],
            "GS": [0, 1, 0, 2],
            "IP": [60, 55, 65, 50],
            "FIP": [2.80, 3.20, 3.80, 4.20],
            "xFIP": [2.90, 3.30, 3.90, 4.30],
            "SIERA": [2.70, 3.10, 3.70, 4.10],
            "K%": [0.30, 0.27, 0.24, 0.21],
            "BB%": [0.05, 0.06, 0.07, 0.08],
            "K-BB%": [0.25, 0.21, 0.17, 0.13],
            "WHIP": [1.00, 1.10, 1.20, 1.30],
            "WAR": [2.0, 1.5, 1.0, 0.5],
            "IDfg": [10005, 10006, 10007, 10008],
            "is_shortened_season": [season == 2020] * 4,
            "season_games": [60 if season == 2020 else 162] * 4,
            "season": [season] * 4,
        }
        combined = {k: data[k] + reliever_data[k] for k in data}
        return pd.DataFrame(combined)
    return pd.DataFrame(data)


def _make_team_batting(season):
    """Create synthetic team batting stats."""
    return pd.DataFrame({
        "Team": ["NYY", "BOS"],
        "G": [162, 162],
        "PA": [6200, 6100],
        "HR": [250, 220],
        "R": [800, 750],
        "RBI": [780, 730],
        "SB": [100, 90],
        "BB%": [0.09, 0.08],
        "K%": [0.22, 0.23],
        "ISO": [0.200, 0.185],
        "BABIP": [0.300, 0.295],
        "AVG": [0.260, 0.255],
        "OBP": [0.340, 0.330],
        "SLG": [0.410, 0.390],
        "wOBA": [0.320, 0.310],
        "wRC+": [110, 105],
        "WAR": [40.0, 35.0],
        "is_shortened_season": [season == 2020] * 2,
        "season_games": [60 if season == 2020 else 162] * 2,
        "season": [season] * 2,
    })


def _make_game_logs(season, team, n_games=15):
    """Create synthetic game logs with known OPS sequence."""
    ops_sequence = [0.700 + i * 0.010 for i in range(n_games)]
    rows = []
    for i in range(n_games):
        rows.append({
            "Date": f"{season}-05-{(i + 1):02d}",
            "OBP": 0.330 + i * 0.005,
            "SLG": 0.370 + i * 0.005,
            "OPS": ops_sequence[i],
            "team": team,
            "season": season,
            "is_shortened_season": season == 2020,
        })
    return pd.DataFrame(rows)


def _make_statcast_pitcher(season):
    """Create synthetic Statcast pitcher data with xwOBA."""
    return pd.DataFrame({
        "last_name": ["A", "B", "C", "D"],
        "first_name": ["Pitcher", "Pitcher", "Pitcher", "Pitcher"],
        "xwoba": [0.290, 0.320, 0.300, 0.330],
        "xba": [0.240, 0.260, 0.250, 0.270],
        "xslg": [0.380, 0.420, 0.400, 0.440],
        "is_shortened_season": [season == 2020] * 4,
        "season_games": [60 if season == 2020 else 162] * 4,
        "season": [season] * 4,
    })


def _make_sp_recent_form_bulk(game_dates, season, sp_names=None):
    """Create synthetic SP recent form data matching MLB Stats API output."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Pitcher A", "Pitcher B", "Pitcher C", "Pitcher D"],
            "ERA": [3.20, 4.50, 3.60, 4.80],
            "FIP": [3.10, 4.30, 3.50, 4.60],
            "IP": [25.0, 22.0, 20.0, 18.0],
            "game_date": [date] * 4,
        })
    return result


def _make_rolling_fip_bulk(game_dates, season, sp_names=None):
    """Create synthetic rolling FIP bulk data for compute_rolling_fip_bulk mock."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Pitcher A", "Pitcher B", "Pitcher C", "Pitcher D"],
            "FIP": [3.10, 4.30, 3.50, 4.60],
        })
    return result


def _make_pitch_count_and_rest_bulk(game_dates, season, sp_names=None):
    """Create synthetic pitch count and rest bulk data."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Pitcher A", "Pitcher B", "Pitcher C", "Pitcher D"],
            "pitch_count_last": [95, 90, 92, 85],
            "days_rest": [5, 4, 5, 4],
        })
    return result


def _make_kalshi_markets():
    """Create empty Kalshi markets (no 2022/2023 coverage)."""
    return pd.DataFrame(columns=[
        "date", "home_team", "away_team", "kalshi_yes_price",
        "kalshi_no_price", "result", "market_ticker",
    ])


def _make_pitcher_id_map(season):
    """Create synthetic pitcher ID map for game log v2 lookups."""
    return {
        "Pitcher A": 1001,
        "Pitcher B": 1002,
        "Pitcher C": 1003,
        "Pitcher D": 1004,
    }


def _make_pitcher_game_log_v2(player_id, season):
    """Create synthetic v2 game logs for each pitcher with varying stats.

    Returns game logs that align with the schedule dates (May 1-10).
    Each pitcher gets 5 starts matching their scheduled appearances.
    """
    # Map player IDs to their scheduled game dates
    # Schedule: 10 games on May 01-10
    # Even games (0,2,4,6,8): NYY home, BOS away
    # Odd games (1,3,5,7,9): BOS home, NYY away
    # Pitcher A: NYY pitcher in even-index games (home_sp for i%2==0 when home=NYY)
    # Pitcher B: BOS pitcher in even-index games (away_sp for i%2==0 when away=BOS)
    # Pitcher C: NYY pitcher in odd-index games
    # Pitcher D: BOS pitcher in odd-index games
    pitcher_logs = {
        1001: {  # Pitcher A - starts on dates when he's scheduled
            "dates": [f"{season}-05-01", f"{season}-05-03", f"{season}-05-05",
                      f"{season}-05-07", f"{season}-05-09"],
            "ip":  [6.0, 7.0, 5.0, 6.0, 7.0],
            "er":  [2,   1,   3,   2,   1],
            "k":   [7,   8,   5,   7,   9],
            "bb":  [2,   1,   3,   2,   1],
            "hr":  [1,   0,   1,   1,   0],
            "np":  [95,  100, 88,  92,  105],
        },
        1002: {  # Pitcher B
            "dates": [f"{season}-05-01", f"{season}-05-03", f"{season}-05-05",
                      f"{season}-05-07", f"{season}-05-09"],
            "ip":  [5.0, 6.0, 4.0, 5.0, 6.0],
            "er":  [3,   2,   4,   3,   2],
            "k":   [5,   6,   4,   5,   7],
            "bb":  [3,   2,   3,   3,   2],
            "hr":  [1,   1,   2,   1,   1],
            "np":  [90,  95,  82,  88,  98],
        },
        1003: {  # Pitcher C
            "dates": [f"{season}-05-02", f"{season}-05-04", f"{season}-05-06",
                      f"{season}-05-08", f"{season}-05-10"],
            "ip":  [6.0, 5.0, 7.0, 6.0, 5.0],
            "er":  [2,   3,   1,   2,   3],
            "k":   [6,   5,   8,   6,   5],
            "bb":  [2,   3,   1,   2,   3],
            "hr":  [1,   1,   0,   1,   1],
            "np":  [92,  88,  102, 94,  87],
        },
        1004: {  # Pitcher D
            "dates": [f"{season}-05-02", f"{season}-05-04", f"{season}-05-06",
                      f"{season}-05-08", f"{season}-05-10"],
            "ip":  [5.0, 4.0, 6.0, 5.0, 4.0],
            "er":  [3,   4,   2,   3,   4],
            "k":   [4,   3,   6,   4,   3],
            "bb":  [3,   4,   2,   3,   4],
            "hr":  [2,   2,   1,   2,   2],
            "np":  [85,  78,  95,  86,  80],
        },
    }
    if player_id not in pitcher_logs:
        return pd.DataFrame(columns=[
            "date", "innings_pitched", "earned_runs", "strikeouts",
            "base_on_balls", "home_runs", "number_of_pitches", "games_started",
        ])
    info = pitcher_logs[player_id]
    return pd.DataFrame({
        "date": pd.to_datetime(info["dates"]),
        "innings_pitched": info["ip"],
        "earned_runs": info["er"],
        "strikeouts": info["k"],
        "base_on_balls": info["bb"],
        "home_runs": info["hr"],
        "number_of_pitches": info["np"],
        "games_started": [1] * len(info["dates"]),
    })


# ---------------------------------------------------------------------------
# Helper: build features with all mocks
# ---------------------------------------------------------------------------

def _mock_fetch_schedule(season):
    return _make_schedule_with_tbd(season)


def _mock_fetch_sp_stats(season, min_gs=1):
    return _make_sp_stats(season, min_gs)


def _mock_fetch_team_batting(season):
    return _make_team_batting(season)


def _mock_fetch_team_game_log(season, team):
    return _make_game_logs(season, team)


def _mock_fetch_statcast_pitcher(season):
    return _make_statcast_pitcher(season)


def _mock_fetch_kalshi_markets():
    return _make_kalshi_markets()


PATCH_TARGETS = {
    "src.features.feature_builder.fetch_schedule": _mock_fetch_schedule,
    "src.features.feature_builder.fetch_sp_stats": _mock_fetch_sp_stats,
    "src.features.feature_builder.fetch_team_batting": _mock_fetch_team_batting,
    "src.features.feature_builder.fetch_team_game_log": _mock_fetch_team_game_log,
    "src.features.feature_builder.fetch_statcast_pitcher": _mock_fetch_statcast_pitcher,
    "src.features.feature_builder.fetch_kalshi_markets": _mock_fetch_kalshi_markets,
    "src.features.feature_builder.fetch_sp_recent_form_bulk": _make_sp_recent_form_bulk,
    "src.features.feature_builder._get_pitcher_id_map": _make_pitcher_id_map,
    "src.features.feature_builder._fetch_pitcher_game_log_v2": _make_pitcher_game_log_v2,
    "src.features.feature_builder.compute_rolling_fip_bulk": _make_rolling_fip_bulk,
    "src.features.feature_builder.compute_pitch_count_and_rest_bulk": _make_pitch_count_and_rest_bulk,
}


@pytest.fixture
def built_features():
    """Build features with all mocked data loaders for seasons [2022, 2023]."""
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_mock_fetch_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2022, 2023])
        df = fb.build()
    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sp_differential(built_features):
    """FEAT-01: SP FIP, xFIP, WHIP, ERA, K-BB% differentials computed correctly."""
    df = built_features
    assert "sp_fip_diff" in df.columns
    assert "sp_xfip_diff" in df.columns
    assert "sp_k_bb_pct_diff" in df.columns
    assert "sp_whip_diff" in df.columns
    assert "sp_era_diff" in df.columns
    # sp_k_pct_diff should be REMOVED (replaced by sp_k_bb_pct_diff)
    assert "sp_k_pct_diff" not in df.columns

    # FIP and xFIP still come from FanGraphs season-level.
    # For a NYY-home game where Pitcher A (FIP=3.50) faces Pitcher B (FIP=4.20):
    # sp_fip_diff = 3.50 - 4.20 = -0.70
    nyy_home = df[(df["home_team"] == "NYY") & (df["home_probable_pitcher"] == "Pitcher A") &
                  (df["away_probable_pitcher"] == "Pitcher B")]
    if len(nyy_home) > 0:
        row = nyy_home.iloc[0]
        assert row["sp_fip_diff"] == pytest.approx(-0.70, abs=0.01)
        assert row["sp_xfip_diff"] == pytest.approx(3.40 - 4.10, abs=0.01)
        # WHIP: Pitcher A WHIP=1.10, Pitcher B WHIP=1.25
        assert row["sp_whip_diff"] == pytest.approx(1.10 - 1.25, abs=0.01)


def test_offense_differential(built_features):
    """FEAT-02: Team wOBA, OPS differentials."""
    df = built_features
    assert "team_woba_diff" in df.columns
    assert "team_ops_diff" in df.columns

    # NYY home: wOBA=0.320, OPS=(0.340+0.410)=0.750
    # BOS away: wOBA=0.310, OPS=(0.330+0.390)=0.720
    nyy_home = df[df["home_team"] == "NYY"]
    if len(nyy_home) > 0:
        row = nyy_home.iloc[0]
        assert row["team_woba_diff"] == pytest.approx(0.010, abs=0.001)
        assert row["team_ops_diff"] == pytest.approx(0.030, abs=0.001)


def test_rolling_ops(built_features):
    """FEAT-03: Rolling 10-game OPS with shift(1) and season boundary reset."""
    df = built_features
    assert "rolling_ops_diff" in df.columns

    # With 15 game logs per team per season and min_periods=10 + shift(1):
    # - Games 1-10 should have NaN (shift(1) means game 10 only has 9 prior values)
    # - Game 11+ should have non-NaN
    season_df = df[df["season"] == 2022].sort_values("game_date")
    # Some early games should have NaN rolling features
    early_games = season_df.head(5)
    assert early_games["rolling_ops_diff"].isna().any(), "Expected NaN for early-season games"


def test_bullpen_differential(built_features):
    """FEAT-04: Bullpen ERA differential."""
    df = built_features
    assert "bullpen_era_diff" in df.columns
    assert "bullpen_fip_diff" in df.columns

    # NYY relievers: Reliever X (ERA=3.00), Reliever Y (ERA=3.50, GS=1 < 3) -> mean = 3.25
    # BOS relievers: Reliever Z (ERA=4.00), Reliever W (ERA=4.50, GS=2 < 3) -> mean = 4.25
    # bullpen_era_diff for NYY home = 3.25 - 4.25 = -1.00
    nyy_home = df[df["home_team"] == "NYY"]
    if len(nyy_home) > 0:
        row = nyy_home.iloc[0]
        assert row["bullpen_era_diff"] == pytest.approx(3.25 - 4.25, abs=0.01)


def test_park_features(built_features):
    """FEAT-05: is_home is 1 for all rows. park_factor matches PARK_FACTORS."""
    df = built_features
    assert "is_home" in df.columns
    assert "park_factor" in df.columns

    # is_home should be 1 for all rows
    assert (df["is_home"] == 1).all()

    # park_factor should match PARK_FACTORS for each home_team
    for _, row in df.iterrows():
        expected = get_park_factor(row["home_team"])
        assert row["park_factor"] == expected


def test_advanced_features(built_features):
    """FEAT-06: Advanced features including SP recent ERA from mocked pitching_stats_range."""
    df = built_features
    assert "sp_siera_diff" in df.columns
    assert "xwoba_diff" in df.columns
    assert "log5_home_wp" in df.columns
    assert "bullpen_fip_diff" in df.columns
    assert "sp_recent_era_diff" in df.columns

    # sp_recent_era_diff for game where Pitcher A (recent ERA=3.20) is home SP
    # and Pitcher B (recent ERA=4.50) is away SP: diff = 3.20 - 4.50 = -1.30
    nyy_home_a = df[(df["home_team"] == "NYY") &
                     (df["home_probable_pitcher"] == "Pitcher A") &
                     (df["away_probable_pitcher"] == "Pitcher B")]
    if len(nyy_home_a) > 0:
        row = nyy_home_a.iloc[0]
        assert row["sp_recent_era_diff"] == pytest.approx(-1.30, abs=0.01)


def test_tbd_starters_excluded(built_features):
    """FEAT-07 (partial): Games with TBD starters are excluded."""
    df = built_features
    # No rows should have None/NaN in pitcher columns
    assert df["home_probable_pitcher"].notna().all()
    assert df["away_probable_pitcher"].notna().all()
    # 12 games per season (10 + 2 TBD) x 2 seasons = 24 total, minus 4 TBD = 20
    assert len(df) == 20


def test_output_schema(built_features):
    """FEAT-08: Output has all required columns."""
    df = built_features
    required_columns = [
        "game_date", "home_team", "away_team", "season", "home_win",
        "sp_fip_diff", "sp_xfip_diff", "sp_k_bb_pct_diff",
        "sp_whip_diff", "sp_era_diff", "sp_siera_diff",
        "team_ops_diff", "rolling_ops_diff",
        "bullpen_era_diff", "is_home", "park_factor",
        "sp_recent_era_diff", "kalshi_yes_price",
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing column: {col}"
    # sp_k_pct_diff must NOT be in output
    assert "sp_k_pct_diff" not in df.columns, "sp_k_pct_diff should be removed"


def test_season_column_present(built_features):
    """FEAT-08: season column present with correct values."""
    df = built_features
    assert "season" in df.columns
    assert set(df["season"].unique()) == {2022, 2023}


def test_game_date_column_present(built_features):
    """FEAT-08: game_date column present with datetime dtype."""
    df = built_features
    assert "game_date" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["game_date"])


# ---------------------------------------------------------------------------
# xwOBA bug fix test (SP-01)
# ---------------------------------------------------------------------------


def _make_statcast_pitcher_fixed(season):
    """Statcast data with correct column schema: 'last_name, first_name' and 'est_woba'."""
    return pd.DataFrame({
        "last_name, first_name": ["Webb, Logan", "Cole, Gerrit", "C, Pitcher", "D, Pitcher"],
        "est_woba": [0.280, 0.290, 0.300, 0.330],
        "player_id": [543321, 543037, 500003, 500004],
        "is_shortened_season": [season == 2020] * 4,
        "season_games": [60 if season == 2020 else 162] * 4,
        "season": [season] * 4,
    })


def _make_schedule_xwoba(season, n_games=10):
    """Schedule with Logan Webb vs Gerrit Cole matchups for xwOBA test."""
    rows = []
    for i in range(n_games):
        game_date = f"{season}-06-{(i + 1):02d}"
        if i % 2 == 0:
            home_sp, away_sp = "Logan Webb", "Gerrit Cole"
            home, away = "SFG", "NYY"
        else:
            home_sp, away_sp = "Gerrit Cole", "Logan Webb"
            home, away = "NYY", "SFG"
        winner = home if i % 2 == 0 else away
        loser = away if i % 2 == 0 else home
        rows.append({
            "game_id": 300000 + season * 1000 + i,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "home_probable_pitcher": home_sp,
            "away_probable_pitcher": away_sp,
            "home_score": 5 if winner == home else 3,
            "away_score": 5 if winner == away else 3,
            "winning_team": winner,
            "losing_team": loser,
            "status": "Final",
            "is_shortened_season": season == 2020,
            "season_games": 60 if season == 2020 else 162,
            "season": season,
        })
    return pd.DataFrame(rows)


def _make_sp_stats_xwoba(season, min_gs=1):
    """SP stats including Logan Webb and Gerrit Cole."""
    data = {
        "Name": ["Logan Webb", "Gerrit Cole", "Pitcher C", "Pitcher D"],
        "Team": ["SFG", "NYY", "SFG", "NYY"],
        "W": [15, 12, 10, 8],
        "L": [5, 8, 7, 10],
        "ERA": [3.00, 3.50, 3.50, 4.50],
        "GS": [30, 28, 25, 22],
        "IP": [200, 180, 170, 150],
        "FIP": [3.20, 3.60, 3.80, 4.60],
        "xFIP": [3.10, 3.50, 3.70, 4.50],
        "SIERA": [3.00, 3.40, 3.60, 4.40],
        "K%": [0.28, 0.25, 0.25, 0.20],
        "BB%": [0.06, 0.07, 0.07, 0.09],
        "K-BB%": [0.22, 0.18, 0.18, 0.11],
        "WHIP": [1.10, 1.15, 1.15, 1.30],
        "WAR": [5.0, 4.0, 4.0, 2.0],
        "IDfg": [19052, 13125, 99901, 99902],
        "is_shortened_season": [season == 2020] * 4,
        "season_games": [60 if season == 2020 else 162] * 4,
        "season": [season] * 4,
    }
    if min_gs == 0:
        reliever_data = {
            "Name": ["Reliever X", "Reliever Y", "Reliever Z", "Reliever W"],
            "Team": ["SFG", "SFG", "NYY", "NYY"],
            "W": [3, 2, 4, 1], "L": [2, 3, 1, 4],
            "ERA": [3.00, 3.50, 4.00, 4.50],
            "GS": [0, 1, 0, 2],
            "IP": [60, 55, 65, 50],
            "FIP": [2.80, 3.20, 3.80, 4.20],
            "xFIP": [2.90, 3.30, 3.90, 4.30],
            "SIERA": [2.70, 3.10, 3.70, 4.10],
            "K%": [0.30, 0.27, 0.24, 0.21],
            "BB%": [0.05, 0.06, 0.07, 0.08],
            "K-BB%": [0.25, 0.21, 0.17, 0.13],
            "WHIP": [1.00, 1.10, 1.20, 1.30],
            "WAR": [2.0, 1.5, 1.0, 0.5],
            "IDfg": [99903, 99904, 99905, 99906],
            "is_shortened_season": [season == 2020] * 4,
            "season_games": [60 if season == 2020 else 162] * 4,
            "season": [season] * 4,
        }
        combined = {k: data[k] + reliever_data[k] for k in data}
        return pd.DataFrame(combined)
    return pd.DataFrame(data)


def _make_team_batting_xwoba(season):
    """Team batting for SFG and NYY."""
    return pd.DataFrame({
        "Team": ["SFG", "NYY"],
        "G": [162, 162], "PA": [6200, 6100], "HR": [200, 250],
        "R": [700, 800], "RBI": [680, 780], "SB": [80, 100],
        "BB%": [0.08, 0.09], "K%": [0.21, 0.22],
        "ISO": [0.180, 0.200], "BABIP": [0.295, 0.300],
        "AVG": [0.255, 0.260], "OBP": [0.330, 0.340],
        "SLG": [0.390, 0.410], "wOBA": [0.310, 0.320],
        "wRC+": [105, 110], "WAR": [35.0, 40.0],
        "is_shortened_season": [season == 2020] * 2,
        "season_games": [60 if season == 2020 else 162] * 2,
        "season": [season] * 2,
    })


def _make_game_logs_xwoba(season, team, n_games=15):
    """Game logs for xwOBA test."""
    rows = []
    for i in range(n_games):
        rows.append({
            "Date": f"{season}-06-{(i + 1):02d}",
            "OBP": 0.330 + i * 0.005,
            "SLG": 0.370 + i * 0.005,
            "OPS": 0.700 + i * 0.010,
            "team": team,
            "season": season,
            "is_shortened_season": season == 2020,
        })
    return pd.DataFrame(rows)


def _make_sp_recent_form_xwoba(game_dates, season, sp_names=None):
    """SP recent form for xwOBA test."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Logan Webb", "Gerrit Cole", "Pitcher C", "Pitcher D"],
            "ERA": [3.00, 3.50, 3.60, 4.80],
            "FIP": [3.10, 3.40, 3.50, 4.60],
            "IP": [25.0, 22.0, 20.0, 18.0],
            "game_date": [date] * 4,
        })
    return result


def _make_pitcher_id_map_xwoba(season):
    """Pitcher ID map for xwOBA test (maps Webb/Cole names to IDs)."""
    return {
        "Logan Webb": 543321,
        "Gerrit Cole": 543037,
        "Pitcher C": 500003,
        "Pitcher D": 500004,
    }


def _make_pitcher_game_log_v2_xwoba(player_id, season):
    """Game log v2 for xwOBA test."""
    # Generate 5 starts in June for each pitcher
    pitcher_data = {
        543321: {"er": [2, 1, 3, 2, 1], "k": [7, 8, 5, 7, 9], "bb": [2, 1, 3, 2, 1]},
        543037: {"er": [3, 2, 4, 3, 2], "k": [6, 7, 5, 6, 8], "bb": [2, 2, 3, 2, 1]},
        500003: {"er": [2, 3, 1, 2, 3], "k": [6, 5, 8, 6, 5], "bb": [2, 3, 1, 2, 3]},
        500004: {"er": [3, 4, 2, 3, 4], "k": [4, 3, 6, 4, 3], "bb": [3, 4, 2, 3, 4]},
    }
    if player_id not in pitcher_data:
        return pd.DataFrame(columns=[
            "date", "innings_pitched", "earned_runs", "strikeouts",
            "base_on_balls", "home_runs", "number_of_pitches", "games_started",
        ])
    d = pitcher_data[player_id]
    dates = [f"{season}-06-{(i + 1):02d}" for i in range(5)]
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "innings_pitched": [6.0, 7.0, 5.0, 6.0, 7.0],
        "earned_runs": d["er"],
        "strikeouts": d["k"],
        "base_on_balls": d["bb"],
        "home_runs": [1, 0, 1, 1, 0],
        "number_of_pitches": [95, 100, 88, 92, 105],
        "games_started": [1, 1, 1, 1, 1],
    })


def test_xwoba_fix():
    """SP-01: xwoba_diff is non-NaN when both pitchers have Statcast data.

    Verifies the fix for the v1 bug where:
    - 'last_name, first_name' (single merged column) was incorrectly parsed
      as separate 'last_name' and 'first_name' columns
    - 'est_woba' column was incorrectly accessed as 'xwoba'
    """
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_make_schedule_xwoba), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_make_sp_stats_xwoba), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_make_team_batting_xwoba), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_make_game_logs_xwoba), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_make_statcast_pitcher_fixed), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_make_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_xwoba), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map_xwoba), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2_xwoba), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2024])
        df = fb.build()

    # xwoba_diff should have non-NaN values
    assert df["xwoba_diff"].notna().any(), (
        "xwoba_diff is all NaN -- the est_woba / 'last_name, first_name' bug is not fixed"
    )

    # For Webb (home, xwoba=0.280) vs Cole (away, xwoba=0.290):
    # xwoba_diff = 0.280 - 0.290 = -0.010
    webb_home = df[
        (df["home_probable_pitcher"] == "Logan Webb")
        & (df["away_probable_pitcher"] == "Gerrit Cole")
    ]
    if len(webb_home) > 0:
        row = webb_home.iloc[0]
        assert row["xwoba_diff"] == pytest.approx(-0.010, abs=0.001), (
            f"Expected xwoba_diff ~ -0.010 but got {row['xwoba_diff']}"
        )


# ---------------------------------------------------------------------------
# SP-03/SP-04/SP-05/SP-06/SP-10 tests (season-to-date rolling, cold-start)
# ---------------------------------------------------------------------------


def test_k_bb_pct_diff():
    """SP-04: sp_k_bb_pct_diff is present and sp_k_pct_diff is removed.

    Mock v2 game logs with varying K and BB per game.
    After cumsum + shift(1), games after the first start should have non-NaN values.
    """
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_mock_fetch_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2022])
        df = fb.build()

    assert "sp_k_bb_pct_diff" in df.columns
    assert "sp_k_pct_diff" not in df.columns
    # Games after the first start for both pitchers should have non-NaN
    assert df["sp_k_bb_pct_diff"].notna().any(), (
        "sp_k_bb_pct_diff is all NaN -- season-to-date rolling K-BB not working"
    )


def test_whip_diff():
    """SP-05: sp_whip_diff is computed from FanGraphs season-level WHIP."""
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_mock_fetch_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2022])
        df = fb.build()

    assert "sp_whip_diff" in df.columns
    assert df["sp_whip_diff"].notna().any()
    # Pitcher A (WHIP=1.10) vs Pitcher B (WHIP=1.25) when NYY is home:
    # sp_whip_diff = 1.10 - 1.25 = -0.15
    nyy_home = df[(df["home_team"] == "NYY") &
                  (df["home_probable_pitcher"] == "Pitcher A") &
                  (df["away_probable_pitcher"] == "Pitcher B")]
    if len(nyy_home) > 0:
        row = nyy_home.iloc[0]
        assert row["sp_whip_diff"] == pytest.approx(-0.15, abs=0.01)


def test_era_diff():
    """SP-03: sp_era_diff uses season-to-date rolling via cumsum + shift(1).

    Pitcher A (1001) game log:
        Game 1 (May 01): IP=6, ER=2
        Game 2 (May 03): IP=7, ER=1
        Game 3 (May 05): IP=5, ER=3
    After shift(1):
        Game 1: std_era = NaN (cold-start -> prev_season or league_avg)
        Game 2: std_era = (2*9)/6 = 3.00
        Game 3: std_era = ((2+1)*9)/(6+7) = 27/13 = 2.077

    Pitcher B (1002) game log:
        Game 1 (May 01): IP=5, ER=3
        Game 2 (May 03): IP=6, ER=2
        Game 3 (May 05): IP=4, ER=4
    After shift(1):
        Game 1: std_era = NaN (cold-start)
        Game 2: std_era = (3*9)/5 = 5.40
        Game 3: std_era = ((3+2)*9)/(5+6) = 45/11 = 4.091

    On game 3 (May 05): NYY home with Pitcher A vs BOS away with Pitcher B
    sp_era_diff = 2.077 - 4.091 = -2.014
    """
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_mock_fetch_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2022])
        df = fb.build()

    assert "sp_era_diff" in df.columns
    # Game 3 of the schedule (index 2): May 05, NYY home, Pitcher A vs Pitcher B
    game_3 = df[(df["game_date"] == pd.Timestamp("2022-05-05")) &
                (df["home_team"] == "NYY")]
    if len(game_3) > 0:
        row = game_3.iloc[0]
        expected_a_era = (2 * 9) / 6 + (1 * 9) / 6  # cumsum approach: (2+1)*9 / (6+7) = 2.077
        expected_a_era = (3 * 9) / 13  # = 2.077
        expected_b_era = (5 * 9) / 11  # = 4.091
        expected_diff = expected_a_era - expected_b_era  # = -2.014
        assert row["sp_era_diff"] == pytest.approx(expected_diff, abs=0.05), (
            f"Expected sp_era_diff ~ {expected_diff:.3f} but got {row['sp_era_diff']}"
        )


def test_cold_start():
    """SP-10: Cold-start uses previous-season FanGraphs stats, then league-average.

    For the first game of a season, shift(1) produces NaN. The cold-start
    fallback should use previous-season stats from fetch_sp_stats(season-1).
    For pitchers with no previous-season data, use LEAGUE_AVG_ERA (4.25).
    """
    # Custom schedule: 2 seasons, just 2 games each
    def _make_cold_start_schedule(season):
        rows = [{
            "game_id": 400000 + season * 10 + 0,
            "game_date": f"{season}-04-01",
            "home_team": "NYY", "away_team": "BOS",
            "home_probable_pitcher": "Pitcher A",
            "away_probable_pitcher": "Pitcher B",
            "home_score": 5, "away_score": 3,
            "winning_team": "NYY", "losing_team": "BOS",
            "status": "Final",
            "is_shortened_season": False, "season_games": 162,
            "season": season,
        }, {
            "game_id": 400000 + season * 10 + 1,
            "game_date": f"{season}-04-05",
            "home_team": "NYY", "away_team": "BOS",
            "home_probable_pitcher": "Pitcher A",
            "away_probable_pitcher": "Rookie X",
            "home_score": 4, "away_score": 2,
            "winning_team": "NYY", "losing_team": "BOS",
            "status": "Final",
            "is_shortened_season": False, "season_games": 162,
            "season": season,
        }]
        return pd.DataFrame(rows)

    # Custom game log v2: Pitcher A has 1 start in April for each season
    def _cold_start_game_log_v2(player_id, season):
        if player_id == 1001:  # Pitcher A
            return pd.DataFrame({
                "date": pd.to_datetime([f"{season}-04-01", f"{season}-04-05"]),
                "innings_pitched": [6.0, 7.0],
                "earned_runs": [2, 1],
                "strikeouts": [7, 8],
                "base_on_balls": [2, 1],
                "home_runs": [1, 0],
                "number_of_pitches": [95, 100],
                "games_started": [1, 1],
            })
        if player_id == 1002:  # Pitcher B
            return pd.DataFrame({
                "date": pd.to_datetime([f"{season}-04-01"]),
                "innings_pitched": [5.0],
                "earned_runs": [3],
                "strikeouts": [5],
                "base_on_balls": [3],
                "home_runs": [1],
                "number_of_pitches": [90],
                "games_started": [1],
            })
        # Rookie X has no game log data at all
        return pd.DataFrame(columns=[
            "date", "innings_pitched", "earned_runs", "strikeouts",
            "base_on_balls", "home_runs", "number_of_pitches", "games_started",
        ])

    def _cold_start_id_map(season):
        return {"Pitcher A": 1001, "Pitcher B": 1002, "Rookie X": 9999}

    with patch("src.features.feature_builder.fetch_schedule", side_effect=_make_cold_start_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_cold_start_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_cold_start_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2023, 2024])
        df = fb.build()

    # All games should have non-NaN sp_era_diff (cold-start fills in)
    assert df["sp_era_diff"].notna().all(), (
        "sp_era_diff has NaN -- cold-start fallback not working"
    )

    # Game 2 of 2024 (Apr 5): Pitcher A vs Rookie X
    # Pitcher A's 2nd game in 2024: std_era from game 1 = (2*9)/6 = 3.00
    # Rookie X: no game log, no prev season -> LEAGUE_AVG_ERA = 4.25
    game_2_2024 = df[(df["game_date"] == pd.Timestamp("2024-04-05")) &
                     (df["home_probable_pitcher"] == "Pitcher A") &
                     (df["away_probable_pitcher"] == "Rookie X")]
    if len(game_2_2024) > 0:
        row = game_2_2024.iloc[0]
        from src.features.feature_builder import LEAGUE_AVG_ERA
        # Home: Pitcher A std_era = 3.00, Away: Rookie X = LEAGUE_AVG_ERA (4.25)
        assert row["sp_era_diff"] == pytest.approx(3.00 - LEAGUE_AVG_ERA, abs=0.05), (
            f"Expected sp_era_diff ~ {3.00 - LEAGUE_AVG_ERA:.3f} but got {row['sp_era_diff']}"
        )


def test_feature_set_constants():
    """SP-09: Three named feature set constants with correct sizes and contents."""
    from src.models.feature_sets import (
        TEAM_ONLY_FEATURE_COLS, SP_ENHANCED_FEATURE_COLS,
        V1_FULL_FEATURE_COLS, FULL_FEATURE_COLS, TARGET_COL,
    )

    # V1 preservation
    assert V1_FULL_FEATURE_COLS == FULL_FEATURE_COLS  # backward compat
    assert len(V1_FULL_FEATURE_COLS) == 14
    assert 'sp_k_pct_diff' in V1_FULL_FEATURE_COLS  # v1 had K%

    # Team-only (no SP columns)
    assert len(TEAM_ONLY_FEATURE_COLS) == 9
    for col in TEAM_ONLY_FEATURE_COLS:
        assert not col.startswith('sp_'), f"Team-only should not have SP col: {col}"
        assert col != 'xwoba_diff', "Team-only should not have xwoba_diff"

    # SP-enhanced (includes all new columns)
    assert 'sp_k_bb_pct_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'sp_whip_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'sp_era_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'sp_recent_fip_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'sp_pitch_count_last_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'sp_days_rest_diff' in SP_ENHANCED_FEATURE_COLS
    assert 'xwoba_diff' in SP_ENHANCED_FEATURE_COLS

    # SP-enhanced should NOT have v1-only columns
    assert 'sp_k_pct_diff' not in SP_ENHANCED_FEATURE_COLS

    # All feature sets should be subsets of what FeatureBuilder produces
    assert set(TEAM_ONLY_FEATURE_COLS).issubset(set(SP_ENHANCED_FEATURE_COLS))

    assert TARGET_COL == 'home_win'


# ---------------------------------------------------------------------------
# SP-07, SP-08, SP-09, SP-11 tests (Plan 04)
# ---------------------------------------------------------------------------


def _make_fip_schedule(season, n_games=1):
    """Schedule with one game for FIP test: Pitcher A (home) vs Pitcher B (away)."""
    return pd.DataFrame([{
        "game_id": 600000 + season * 10,
        "game_date": f"{season}-06-15",
        "home_team": "NYY", "away_team": "BOS",
        "home_probable_pitcher": "Pitcher A",
        "away_probable_pitcher": "Pitcher B",
        "home_score": 5, "away_score": 3,
        "winning_team": "NYY", "losing_team": "BOS",
        "status": "Final",
        "is_shortened_season": False, "season_games": 162,
        "season": season,
    }])


def _make_fip_game_log_v2(player_id, season):
    """v2 game logs for FIP test.

    Pitcher A (1001): 3 starts in 30-day window before Jun 15.
        May 20: K=20 (spread across 3 starts), BB=6, HR=3, IP=18
        We split: 3 starts on May 20, May 25, Jun 01.
    Pitcher B (1002): 2 starts in 30-day window.
        May 22, Jun 05: K=10, BB=8, HR=4, IP=12
    """
    if player_id == 1001:  # Pitcher A
        return pd.DataFrame({
            "date": pd.to_datetime([
                f"{season}-05-20", f"{season}-05-25", f"{season}-06-01",
            ]),
            "innings_pitched": [6.0, 6.0, 6.0],
            "earned_runs": [2, 1, 3],
            "strikeouts": [7, 7, 6],         # total K=20
            "base_on_balls": [2, 2, 2],       # total BB=6
            "home_runs": [1, 1, 1],           # total HR=3
            "number_of_pitches": [95, 100, 88],
            "games_started": [1, 1, 1],
        })
    elif player_id == 1002:  # Pitcher B
        return pd.DataFrame({
            "date": pd.to_datetime([
                f"{season}-05-22", f"{season}-06-05",
            ]),
            "innings_pitched": [6.0, 6.0],
            "earned_runs": [3, 4],
            "strikeouts": [5, 5],             # total K=10
            "base_on_balls": [4, 4],          # total BB=8
            "home_runs": [2, 2],              # total HR=4
            "number_of_pitches": [90, 92],
            "games_started": [1, 1],
        })
    return pd.DataFrame(columns=[
        "date", "innings_pitched", "earned_runs", "strikeouts",
        "base_on_balls", "home_runs", "number_of_pitches", "games_started",
    ])


def _make_sp_form_fip(game_dates, season, sp_names=None):
    """SP recent form (ERA) for FIP test."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Pitcher A", "Pitcher B"],
            "ERA": [3.00, 4.50],
            "game_date": [date] * 2,
        })
    return result


def test_recent_fip_diff():
    """SP-07: sp_recent_fip_diff computed from 30-day rolling raw FIP.

    Pitcher A: 3 starts in window. K=20, BB=6, HR=3, IP=18.
    Raw FIP = ((13*3) + (3*6) - (2*20)) / 18 = (39 + 18 - 40) / 18 = 0.944

    Pitcher B: 2 starts in window. K=10, BB=8, HR=4, IP=12.
    Raw FIP = ((13*4) + (3*8) - (2*10)) / 12 = (52 + 24 - 20) / 12 = 4.667

    sp_recent_fip_diff = 0.944 - 4.667 = -3.722
    """
    # Mock at both feature_builder and sp_recent_form namespaces so
    # compute_rolling_fip_bulk (called in _add_advanced_features) uses mock data.
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_make_fip_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_form_fip), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_fip_game_log_v2), \
         patch("src.features.sp_recent_form._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2", side_effect=_make_fip_game_log_v2), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2024])
        df = fb.build()

    assert "sp_recent_fip_diff" in df.columns
    assert len(df) == 1
    actual = df["sp_recent_fip_diff"].iloc[0]
    assert actual == pytest.approx(-3.722, abs=0.01), (
        f"Expected sp_recent_fip_diff ~ -3.722 but got {actual}"
    )


def _make_pcount_schedule(season, n_games=1):
    """Schedule for pitch count / days rest test: game on May 12."""
    return pd.DataFrame([{
        "game_id": 700000 + season * 10,
        "game_date": f"{season}-05-12",
        "home_team": "NYY", "away_team": "BOS",
        "home_probable_pitcher": "Pitcher A",
        "away_probable_pitcher": "Pitcher B",
        "home_score": 4, "away_score": 2,
        "winning_team": "NYY", "losing_team": "BOS",
        "status": "Final",
        "is_shortened_season": False, "season_games": 162,
        "season": season,
    }])


def _make_pcount_game_log_v2(player_id, season):
    """v2 game logs for pitch count / days rest test.

    Pitcher A (1001): starts May 1 (95p), May 6 (102p), May 11 (88p).
    Pitcher B (1002): starts May 2 (90p), May 7 (100p).
    Game on May 12.
    Expected A: pitch_count_last=88, days_rest=min(12-11,7)=1
    Expected B: pitch_count_last=100, days_rest=min(12-7,7)=5
    """
    if player_id == 1001:
        return pd.DataFrame({
            "date": pd.to_datetime([
                f"{season}-05-01", f"{season}-05-06", f"{season}-05-11",
            ]),
            "innings_pitched": [6.0, 7.0, 5.0],
            "earned_runs": [2, 1, 3],
            "strikeouts": [7, 8, 5],
            "base_on_balls": [2, 1, 3],
            "home_runs": [1, 0, 1],
            "number_of_pitches": [95, 102, 88],
            "games_started": [1, 1, 1],
        })
    elif player_id == 1002:
        return pd.DataFrame({
            "date": pd.to_datetime([
                f"{season}-05-02", f"{season}-05-07",
            ]),
            "innings_pitched": [5.0, 6.0],
            "earned_runs": [3, 2],
            "strikeouts": [5, 6],
            "base_on_balls": [3, 2],
            "home_runs": [1, 1],
            "number_of_pitches": [90, 100],
            "games_started": [1, 1],
        })
    return pd.DataFrame(columns=[
        "date", "innings_pitched", "earned_runs", "strikeouts",
        "base_on_balls", "home_runs", "number_of_pitches", "games_started",
    ])


def _make_sp_form_pcount(game_dates, season, sp_names=None):
    """SP recent form for pitch count test."""
    result = {}
    for date in sorted(set(game_dates)):
        result[date] = pd.DataFrame({
            "Name": ["Pitcher A", "Pitcher B"],
            "ERA": [3.00, 4.50],
            "game_date": [date] * 2,
        })
    return result


def test_pitch_count_days_rest():
    """SP-08: sp_pitch_count_last_diff and sp_days_rest_diff from most recent start.

    Pitcher A: last start May 11 (88p). days_rest = 12 - 11 = 1.
    Pitcher B: last start May 7 (100p). days_rest = min(12 - 7, 7) = 5.
    sp_pitch_count_last_diff = 88 - 100 = -12.
    sp_days_rest_diff = 1 - 5 = -4.
    """
    # Mock at both feature_builder and sp_recent_form namespaces so
    # compute_pitch_count_and_rest_bulk (called in _add_advanced_features) uses mock data.
    with patch("src.features.feature_builder.fetch_schedule", side_effect=_make_pcount_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_form_pcount), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pcount_game_log_v2), \
         patch("src.features.sp_recent_form._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.sp_recent_form._fetch_pitcher_game_log_v2", side_effect=_make_pcount_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk):
        fb = FeatureBuilder(seasons=[2024])
        df = fb.build()

    assert "sp_pitch_count_last_diff" in df.columns
    assert "sp_days_rest_diff" in df.columns
    assert len(df) == 1

    actual_pc = df["sp_pitch_count_last_diff"].iloc[0]
    actual_dr = df["sp_days_rest_diff"].iloc[0]
    assert actual_pc == pytest.approx(-12, abs=0.01), (
        f"Expected sp_pitch_count_last_diff = -12 but got {actual_pc}"
    )
    assert actual_dr == pytest.approx(-4, abs=0.01), (
        f"Expected sp_days_rest_diff = -4 but got {actual_dr}"
    )


def test_v2_parquet_output():
    """SP-11: FeatureBuilder.build() output contains all SP_ENHANCED_FEATURE_COLS."""
    from src.models.feature_sets import SP_ENHANCED_FEATURE_COLS, TARGET_COL

    with patch("src.features.feature_builder.fetch_schedule", side_effect=_mock_fetch_schedule), \
         patch("src.features.feature_builder.fetch_sp_stats", side_effect=_mock_fetch_sp_stats), \
         patch("src.features.feature_builder.fetch_team_batting", side_effect=_mock_fetch_team_batting), \
         patch("src.features.feature_builder.fetch_team_game_log", side_effect=_mock_fetch_team_game_log), \
         patch("src.features.feature_builder.fetch_statcast_pitcher", side_effect=_mock_fetch_statcast_pitcher), \
         patch("src.features.feature_builder.fetch_kalshi_markets", side_effect=_mock_fetch_kalshi_markets), \
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk), \
         patch("src.features.feature_builder._get_pitcher_id_map", side_effect=_make_pitcher_id_map), \
         patch("src.features.feature_builder._fetch_pitcher_game_log_v2", side_effect=_make_pitcher_game_log_v2), \
         patch("src.features.feature_builder.compute_rolling_fip_bulk", side_effect=_make_rolling_fip_bulk), \
         patch("src.features.feature_builder.compute_pitch_count_and_rest_bulk", side_effect=_make_pitch_count_and_rest_bulk):
        fb = FeatureBuilder(seasons=[2024])
        df = fb.build()

    # DataFrame should contain all SP_ENHANCED columns
    for col in SP_ENHANCED_FEATURE_COLS:
        assert col in df.columns, f"Missing SP_ENHANCED column: {col}"

    # Target column present
    assert TARGET_COL in df.columns

    # Non-empty
    assert df.shape[0] > 0, "DataFrame is empty"

    # Columns that are expected to have non-NaN values with mock data.
    # Excluded: xwoba_diff (mock uses old Statcast schema, tested in test_xwoba_fix),
    #   rolling_ops_diff (needs 11+ games, mock only has 10 per season),
    #   kalshi_yes_price (empty mock, pre-2025 games)
    known_nan_in_mock = {'xwoba_diff', 'rolling_ops_diff'}
    for col in SP_ENHANCED_FEATURE_COLS:
        if col in known_nan_in_mock:
            continue
        if col in df.columns:
            assert df[col].notna().any(), (
                f"SP_ENHANCED column '{col}' is entirely NaN"
            )
