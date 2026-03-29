"""Tests for sabermetric formula functions (Log5, Pythagorean, park factors).

Covers: log5_probability, pythagorean_win_pct, get_park_factor, PARK_FACTORS dict.
"""

import pytest
from src.features.formulas import (
    log5_probability,
    pythagorean_win_pct,
    get_park_factor,
    PARK_FACTORS,
)


# --- Log5 tests ---


def test_log5_equal_teams():
    """log5_probability(0.5, 0.5) == 0.5 -- equal teams get coin-flip."""
    assert log5_probability(0.5, 0.5) == pytest.approx(0.5)


def test_log5_strong_home():
    """log5_probability(0.7, 0.3) > 0.8 -- strong home team dominates."""
    result = log5_probability(0.7, 0.3)
    assert result > 0.8


def test_log5_degenerate_both_zero():
    """log5_probability(0.0, 0.0) == 0.5 -- degenerate: both 0%."""
    assert log5_probability(0.0, 0.0) == pytest.approx(0.5)


def test_log5_degenerate_both_one():
    """log5_probability(1.0, 1.0) == 0.5 -- degenerate: both 100%."""
    assert log5_probability(1.0, 1.0) == pytest.approx(0.5)


def test_log5_range():
    """Result always in [0, 1] for valid inputs."""
    test_cases = [
        (0.0, 0.5),
        (0.5, 0.0),
        (1.0, 0.5),
        (0.5, 1.0),
        (0.3, 0.7),
        (0.9, 0.1),
        (0.01, 0.99),
    ]
    for p_home, p_away in test_cases:
        result = log5_probability(p_home, p_away)
        assert 0.0 <= result <= 1.0, (
            f"log5_probability({p_home}, {p_away}) = {result} out of [0, 1]"
        )


def test_log5_symmetry():
    """log5_probability(a, b) + log5_probability(b, a) == 1.0 for non-degenerate inputs."""
    result_home = log5_probability(0.6, 0.4)
    result_swap = log5_probability(0.4, 0.6)
    assert result_home + result_swap == pytest.approx(1.0)


# --- Pythagorean tests ---


def test_pythagorean_equal():
    """pythagorean_win_pct(700, 700) == 0.5 -- equal runs = .500."""
    assert pythagorean_win_pct(700, 700) == pytest.approx(0.5)


def test_pythagorean_dominant():
    """pythagorean_win_pct(900, 600, 1.83) > 0.65 -- dominant offense."""
    result = pythagorean_win_pct(900, 600, 1.83)
    assert result > 0.65


def test_pythagorean_zero_both():
    """pythagorean_win_pct(0, 0) == 0.5 -- degenerate: no runs."""
    assert pythagorean_win_pct(0, 0) == pytest.approx(0.5)


def test_pythagorean_exponent_183():
    """Default exponent is 1.83 (Baseball-Reference standard, NOT 2.0).

    With exponent 2.0: 800^2/(800^2 + 600^2) = 640000/1000000 = 0.64
    With exponent 1.83: result should differ from 0.64.
    """
    result_default = pythagorean_win_pct(800, 600)
    result_2 = pythagorean_win_pct(800, 600, exponent=2.0)
    # Default should use 1.83, not 2.0, so values should differ
    assert result_default != pytest.approx(result_2, abs=1e-6)
    # And the default should still be > 0.5 for runs_scored > runs_allowed
    assert result_default > 0.5


def test_pythagorean_result_range():
    """Result always in [0, 1] for non-negative inputs."""
    test_cases = [(800, 600), (600, 800), (100, 900), (900, 100), (0, 500)]
    for rs, ra in test_cases:
        result = pythagorean_win_pct(rs, ra)
        assert 0.0 <= result <= 1.0, (
            f"pythagorean_win_pct({rs}, {ra}) = {result} out of [0, 1]"
        )


# --- Park factor tests ---


def test_park_factor_coors():
    """get_park_factor('COL') == 116 -- Coors Field is most hitter-friendly."""
    assert get_park_factor("COL") == 116


def test_park_factor_all_30_teams():
    """PARK_FACTORS has exactly 30 entries, one for each canonical team code."""
    assert len(PARK_FACTORS) == 30

    expected_teams = {
        "ARI", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE", "COL", "DET",
        "HOU", "KCR", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "OAK",
        "PHI", "PIT", "SDP", "SEA", "SFG", "STL", "TBR", "TEX", "TOR", "WSN",
    }
    assert set(PARK_FACTORS.keys()) == expected_teams


def test_park_factor_unknown():
    """get_park_factor('UNKNOWN') == 100 -- unknown team defaults to neutral."""
    assert get_park_factor("UNKNOWN") == 100
