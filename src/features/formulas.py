"""Sabermetric formula functions for MLB Win Probability model.

Pure functions with no side effects -- safe to call from any context.

Functions:
    log5_probability: Bill James Log5 matchup probability
    pythagorean_win_pct: Pythagorean expected winning percentage
    get_park_factor: Park run factor lookup by team code
"""

# 3-year average park run factors (2022-2024 estimates), source: FanGraphs Guts
# Normalized to 100 = league average. Values > 100 = hitter-friendly.
# Uses canonical 3-letter team codes from src.data.team_mappings.
# Note: pybaseball has no park_factors function (GitHub issue #409).
# Static dict is intentional -- park factors change slowly.
PARK_FACTORS = {
    "COL": 116, "ARI": 107, "TEX": 106, "CIN": 105, "BOS": 104,
    "CHC": 103, "KCR": 102, "MIL": 102, "PHI": 101, "BAL": 101,
    "ATL": 100, "MIN": 100, "NYY": 100, "DET": 100, "CHW": 100,
    "HOU": 99,  "LAA": 99,  "STL": 99,  "TOR": 99,  "WSN": 99,
    "SFG": 98,  "NYM": 98,  "PIT": 98,  "CLE": 97,  "LAD": 97,
    "SDP": 97,  "TBR": 96,  "SEA": 96,  "MIA": 95,  "OAK": 95,
}


def log5_probability(p_home: float, p_away: float) -> float:
    """Compute Log5 win probability for home team.

    Formula: P(home wins) = pA*(1-pB) / (pA*(1-pB) + (1-pA)*pB)
    where pA = home team win%, pB = away team win%.

    Both inputs should be winning percentages (0-1 range).
    Returns probability that home team wins (0-1 range).

    If denominator is zero (both teams at 0% or both at 100%),
    returns 0.5 (degenerate case -- no information to differentiate).

    Source: Bill James, 1981 Baseball Abstract.
    Equivalent to Bradley-Terry model / Elo rating system.
    """
    numerator = p_home * (1 - p_away)
    denominator = p_home * (1 - p_away) + (1 - p_home) * p_away
    if denominator == 0:
        return 0.5
    return numerator / denominator


def pythagorean_win_pct(
    runs_scored: float, runs_allowed: float, exponent: float = 1.83
) -> float:
    """Compute Pythagorean expected winning percentage.

    Formula: W% = RS^exp / (RS^exp + RA^exp)

    Default exponent 1.83 is the Baseball-Reference standard,
    more accurate than the original exponent of 2.

    Returns 0.5 if both runs_scored and runs_allowed are <= 0
    (degenerate case -- no games played).

    Source: Bill James, refined by Baseball-Reference.com
    """
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0.5
    rs_exp = runs_scored ** exponent
    ra_exp = runs_allowed ** exponent
    if rs_exp + ra_exp == 0:
        return 0.5
    return rs_exp / (rs_exp + ra_exp)


def get_park_factor(team: str) -> int:
    """Return park run factor for team's home park.

    Looks up team in PARK_FACTORS dict using canonical 3-letter code.
    Returns 100 (league average / neutral) if team not found.

    Args:
        team: Canonical 3-letter team code (e.g., 'COL', 'NYY').

    Returns:
        Integer park factor. 100 = neutral, >100 = hitter-friendly,
        <100 = pitcher-friendly.
    """
    return PARK_FACTORS.get(team, 100)
