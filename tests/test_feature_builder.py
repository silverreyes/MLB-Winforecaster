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
        "WHIP": [1.10, 1.25, 1.15, 1.30],
        "WAR": [5.0, 3.0, 4.0, 2.0],
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
            "WHIP": [1.00, 1.10, 1.20, 1.30],
            "WAR": [2.0, 1.5, 1.0, 0.5],
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


def _make_kalshi_markets():
    """Create empty Kalshi markets (no 2022/2023 coverage)."""
    return pd.DataFrame(columns=[
        "date", "home_team", "away_team", "kalshi_yes_price",
        "kalshi_no_price", "result", "market_ticker",
    ])


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
         patch("src.features.feature_builder.fetch_sp_recent_form_bulk", side_effect=_make_sp_recent_form_bulk):
        fb = FeatureBuilder(seasons=[2022, 2023])
        df = fb.build()
    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sp_differential(built_features):
    """FEAT-01: SP FIP, xFIP, K% differentials computed correctly."""
    df = built_features
    assert "sp_fip_diff" in df.columns
    assert "sp_xfip_diff" in df.columns
    assert "sp_k_pct_diff" in df.columns

    # For a NYY-home game where Pitcher A (FIP=3.50) faces Pitcher B (FIP=4.20):
    # sp_fip_diff = 3.50 - 4.20 = -0.70
    nyy_home = df[(df["home_team"] == "NYY") & (df["home_probable_pitcher"] == "Pitcher A") &
                  (df["away_probable_pitcher"] == "Pitcher B")]
    if len(nyy_home) > 0:
        row = nyy_home.iloc[0]
        assert row["sp_fip_diff"] == pytest.approx(-0.70, abs=0.01)
        assert row["sp_xfip_diff"] == pytest.approx(3.40 - 4.10, abs=0.01)
        assert row["sp_k_pct_diff"] == pytest.approx(0.28 - 0.22, abs=0.01)


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
        "sp_fip_diff", "team_ops_diff", "rolling_ops_diff",
        "bullpen_era_diff", "is_home", "park_factor",
        "sp_recent_era_diff", "kalshi_yes_price",
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing column: {col}"


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
