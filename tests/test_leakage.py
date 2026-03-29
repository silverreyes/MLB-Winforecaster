"""Wave 0 test stubs for temporal safety / leakage detection (FEAT-07).

These stubs define the leakage testing contract. Each stub uses
pytest.importorskip so stubs SKIP (not FAIL) until FeatureBuilder is
implemented in Plan 02.

Stub bodies are `pass` -- Plan 02 fills them in with real assertions.
"""

import pytest

fb_mod = pytest.importorskip(
    "src.features.feature_builder", reason="FeatureBuilder not yet implemented"
)


def test_shift1_prevents_current_game_leakage():
    """FEAT-07: Rolling features use shift(1). Verify that a mid-season game's
    rolling features are computed from games BEFORE it, not including itself.
    Test method: Build features for season 2023. Pick game at index 500.
    Confirm rolling_ops_10 for that game equals the mean of the 10 games
    immediately preceding it (shifted by 1).
    """
    pass


def test_season_boundary_reset():
    """FEAT-07: Rolling windows reset at season boundaries. Verify that game 1
    of season N+1 has NaN rolling features, not carry-over from season N.
    """
    pass


def test_no_leakage_on_outcome_removal():
    """FEAT-07: Remove a game's outcome from source data and rebuild using manual masking.
    Build features with full mock data. Pick a mid-season game. Set winning_team=None
    for that game (mask the outcome). Rebuild features. The feature values for that game
    must be identical -- rolling features depend only on prior game logs, not the outcome.
    Implementation: manual data masking only (no FeatureBuilder.build_excluding() method).
    """
    pass


def test_early_season_nan():
    """FEAT-07: Games 1-9 of each season have NaN rolling features (incomplete
    10-game window). Not imputed, not partially filled.
    """
    pass
