"""Canonical team name normalization shared by all data loaders.

Maps every known abbreviation, variant, and full name to a single canonical
3-letter abbreviation per MLB.com convention.
"""

# Canonical 3-letter codes (MLB.com standard):
# ARI, ATL, BAL, BOS, CHC, CHW, CIN, CLE, COL, DET,
# HOU, KCR, LAA, LAD, MIA, MIL, MIN, NYM, NYY, OAK,
# PHI, PIT, SDP, SFG, SEA, STL, TBR, TEX, TOR, WSN

TEAM_MAP = {
    # === Canonical codes (self-mapping) ===
    "ARI": "ARI",
    "ATL": "ATL",
    "BAL": "BAL",
    "BOS": "BOS",
    "CHC": "CHC",
    "CHW": "CHW",
    "CIN": "CIN",
    "CLE": "CLE",
    "COL": "COL",
    "DET": "DET",
    "HOU": "HOU",
    "KCR": "KCR",
    "LAA": "LAA",
    "LAD": "LAD",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NYM": "NYM",
    "NYY": "NYY",
    "OAK": "OAK",
    "PHI": "PHI",
    "PIT": "PIT",
    "SDP": "SDP",
    "SFG": "SFG",
    "SEA": "SEA",
    "STL": "STL",
    "TBR": "TBR",
    "TEX": "TEX",
    "TOR": "TOR",
    "WSN": "WSN",

    # === Common abbreviation variants ===
    # Washington
    "WSH": "WSN",
    "WAS": "WSN",
    # Chicago White Sox
    "CWS": "CHW",
    # San Diego
    "SD": "SDP",
    # San Francisco
    "SF": "SFG",
    # Tampa Bay
    "TB": "TBR",
    # Kansas City
    "KC": "KCR",
    # Arizona (Baseball Reference)
    "AZ": "ARI",
    # Angels (old abbreviation)
    "ANA": "LAA",
    "CAL": "LAA",
    # Kalshi ticker-specific codes (KXMLBGAME series uses these internally)
    "KAN": "KCR",   # Kansas City (Kalshi uses KAN, not KC)
    "FLA": "MIA",   # Miami/Florida (Kalshi uses FLA, old Marlins name)
    "ATH": "OAK",   # Las Vegas Athletics (rebranded from Oakland in 2025)

    # === Full team names (MLB Stats API format) ===
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Cleveland Indians": "CLE",  # Pre-2022 name
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP",
    "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSN",

    # === Shortened/informal names ===
    "Diamondbacks": "ARI",
    "D-backs": "ARI",
    "Braves": "ATL",
    "Orioles": "BAL",
    "Red Sox": "BOS",
    "Cubs": "CHC",
    "White Sox": "CHW",
    "Reds": "CIN",
    "Guardians": "CLE",
    "Indians": "CLE",
    "Rockies": "COL",
    "Tigers": "DET",
    "Astros": "HOU",
    "Royals": "KCR",
    "Angels": "LAA",
    "Dodgers": "LAD",
    "Marlins": "MIA",
    "Brewers": "MIL",
    "Twins": "MIN",
    "Mets": "NYM",
    "Yankees": "NYY",
    "Athletics": "OAK",
    "A's": "OAK",
    "Phillies": "PHI",
    "Pirates": "PIT",
    "Padres": "SDP",
    "Giants": "SFG",
    "Mariners": "SEA",
    "Cardinals": "STL",
    "Rays": "TBR",
    "Rangers": "TEX",
    "Blue Jays": "TOR",
    "Nationals": "WSN",

    # === pybaseball / FanGraphs / Baseball Reference variants ===
    "Diamondbacks": "ARI",
    "WhiteSox": "CHW",
    "RedSox": "BOS",
    "BlueJays": "TOR",

    # === Additional historical names ===
    "Florida Marlins": "MIA",  # Pre-2012
    "Anaheim Angels": "LAA",
    "Los Angeles Angels of Anaheim": "LAA",
    "Montreal Expos": "WSN",  # Pre-2005
    "Tampa Bay Devil Rays": "TBR",  # Pre-2008

    # === St. Louis variants ===
    "St Louis Cardinals": "STL",
    "Saint Louis Cardinals": "STL",
}

# Build case-insensitive lookup (lowercase keys)
_TEAM_MAP_LOWER = {k.lower(): v for k, v in TEAM_MAP.items()}


def normalize_team(name: str) -> str:
    """Normalize any team name/abbreviation to canonical 3-letter code.

    Performs case-insensitive matching against all known team names,
    abbreviations, and variants.

    Args:
        name: Team name, abbreviation, or variant string.

    Returns:
        Canonical 3-letter team code (e.g., 'NYY', 'LAD', 'WSN').

    Raises:
        ValueError: If the team name is not recognized.
    """
    cleaned = name.strip()

    # Try case-insensitive match
    lookup = cleaned.lower()
    if lookup in _TEAM_MAP_LOWER:
        return _TEAM_MAP_LOWER[lookup]

    raise ValueError(
        f"Unrecognized team name: '{name}'. "
        f"Known canonical codes: ARI, ATL, BAL, BOS, CHC, CHW, CIN, CLE, "
        f"COL, DET, HOU, KCR, LAA, LAD, MIA, MIL, MIN, NYM, NYY, OAK, "
        f"PHI, PIT, SDP, SFG, SEA, STL, TBR, TEX, TOR, WSN"
    )
