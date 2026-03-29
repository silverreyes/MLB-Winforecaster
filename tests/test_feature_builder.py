"""Wave 0 test stubs for FeatureBuilder class (FEAT-01 through FEAT-08).

These stubs define the FeatureBuilder testing contract. Each stub uses
pytest.importorskip so stubs SKIP (not FAIL) until FeatureBuilder is
implemented in Plan 02.

Stub bodies are `pass` -- Plan 02 fills them in with real assertions.
"""

import pytest

fb_mod = pytest.importorskip(
    "src.features.feature_builder", reason="FeatureBuilder not yet implemented"
)


def test_sp_differential():
    """FEAT-01: SP FIP, xFIP, K% differentials computed correctly.
    Verify: home_sp_fip - away_sp_fip = sp_fip_diff (and similarly for xFIP, K%).
    """
    pass


def test_offense_differential():
    """FEAT-02: Team wOBA, OPS, Pythagorean win% differentials.
    Verify: home_team_ops - away_team_ops = team_ops_diff.
    """
    pass


def test_rolling_ops():
    """FEAT-03: Rolling 10-game OPS with shift(1) and season boundary reset.
    Verify: games 1-10 of season have NaN rolling OPS (shift(1) + min_periods=10:
    game 10 only sees 9 prior values). Game 11 is the first non-NaN row (mean of games 1-10).
    """
    pass


def test_bullpen_differential():
    """FEAT-04: Bullpen ERA differential between home and away teams.
    Verify: home_bullpen_era - away_bullpen_era = bullpen_era_diff.
    """
    pass


def test_park_features():
    """FEAT-05: Home/away indicator and park run factor present.
    Verify: is_home column is 1 for all rows. park_factor column matches PARK_FACTORS[home_team].
    """
    pass


def test_advanced_features():
    """FEAT-06: SIERA diff, xwOBA diff, SP recent form, Log5 probability, bullpen FIP diff.
    Verify: columns sp_siera_diff, xwoba_diff, sp_recent_era, log5_home_wp, bullpen_fip_diff exist.
    """
    pass


def test_tbd_starters_excluded():
    """FEAT-07 (partial): Games with TBD starters are excluded.
    Verify: no rows where home_probable_pitcher or away_probable_pitcher is None.
    """
    pass


def test_output_schema():
    """FEAT-08: Output has required columns: game_date, home_team, away_team, season, home_win,
    plus all differential feature columns, plus kalshi_yes_price (NaN for pre-2025).
    """
    pass


def test_season_column_present():
    """FEAT-08: season column present for walk-forward splitting in Phase 3."""
    pass


def test_game_date_column_present():
    """FEAT-08: game_date column present for temporal ordering."""
    pass
