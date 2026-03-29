"""Unit tests for SP ID bridge (SP-02).

Tests the two-tier Chadwick + accent-strip ID matching approach,
manual overrides, and the resolve_sp_to_fg_id helper.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.data.sp_id_bridge import (
    strip_accents,
    build_mlb_to_fg_bridge,
    resolve_sp_to_fg_id,
    MANUAL_OVERRIDES,
)


# ---------------------------------------------------------------------------
# strip_accents
# ---------------------------------------------------------------------------

def test_strip_accents():
    """Accent diacriticals are removed; plain ASCII is unchanged."""
    # Jose Berrios (accented i: \u00ed)
    assert strip_accents("Jos\u00e9 Berr\u00edos") == "Jose Berrios"
    # Carlos Rodon (accented o: \u00f3)
    assert strip_accents("Carlos Rod\u00f3n") == "Carlos Rodon"
    # Pablo Lopez (accented o: \u00f3)
    assert strip_accents("Pablo L\u00f3pez") == "Pablo Lopez"
    # Plain ASCII unchanged
    assert strip_accents("Plain Name") == "Plain Name"


# ---------------------------------------------------------------------------
# MANUAL_OVERRIDES
# ---------------------------------------------------------------------------

def test_manual_overrides_exist():
    """Required manual override entries are present."""
    assert "Louie Varland" in MANUAL_OVERRIDES
    assert "Luis L. Ortiz" in MANUAL_OVERRIDES
    assert MANUAL_OVERRIDES["Louie Varland"] == "Louis Varland"
    assert MANUAL_OVERRIDES["Luis L. Ortiz"] == "Luis Ortiz"


# ---------------------------------------------------------------------------
# build_mlb_to_fg_bridge -- Tier 1 (Chadwick)
# ---------------------------------------------------------------------------

@patch("src.data.sp_id_bridge.is_cached", return_value=False)
@patch("src.data.sp_id_bridge.save_to_cache")
@patch("src.data.sp_id_bridge.chadwick_register")
def test_build_bridge_tier1_chadwick(mock_chad, mock_save, mock_cached):
    """Tier 1: Chadwick register maps key_mlbam -> key_fangraphs correctly.
    Invalid (-1) rows are excluded."""
    mock_chad.return_value = pd.DataFrame({
        "key_mlbam": [100, 200, 300, -1],
        "key_fangraphs": [1001, 2002, 3003, -1],
        "mlb_played_last": [2024, 2024, 2024, 2024],
        "name_first": ["A", "B", "C", "D"],
        "name_last": ["One", "Two", "Three", "Four"],
    })

    fg_df = pd.DataFrame({
        "Name": ["A One", "B Two", "C Three"],
        "IDfg": [1001, 2002, 3003],
    })

    bridge = build_mlb_to_fg_bridge(2024, fg_df)

    # 3 valid mappings
    assert bridge[100] == 1001
    assert bridge[200] == 2002
    assert bridge[300] == 3003
    # -1 row excluded
    assert -1 not in bridge


# ---------------------------------------------------------------------------
# build_mlb_to_fg_bridge -- Tier 2 (accent-strip fallback)
# ---------------------------------------------------------------------------

@patch("src.data.sp_id_bridge.is_cached", return_value=False)
@patch("src.data.sp_id_bridge.save_to_cache")
@patch("src.data.sp_id_bridge.chadwick_register")
def test_build_bridge_tier2_accent_fallback(mock_chad, mock_save, mock_cached):
    """Tier 2: Accent-normalized name matching resolves accented MLB names
    to ASCII FanGraphs entries when Chadwick has no match."""
    # Empty Chadwick (no Tier 1 matches)
    mock_chad.return_value = pd.DataFrame({
        "key_mlbam": pd.Series(dtype="int64"),
        "key_fangraphs": pd.Series(dtype="int64"),
        "mlb_played_last": pd.Series(dtype="int64"),
    })

    # FanGraphs uses ASCII names
    fg_df = pd.DataFrame({
        "Name": ["Jose Berrios", "Carlos Rodon"],
        "IDfg": [12345, 67890],
    })

    # MLB Stats API uses accented names
    pitcher_id_map = {
        "Jos\u00e9 Berr\u00edos": 543210,
        "Carlos Rod\u00f3n": 987654,
    }

    bridge = build_mlb_to_fg_bridge(2024, fg_df, pitcher_id_map=pitcher_id_map)

    assert bridge[543210] == 12345, "Accented Berrios should map to FG ID 12345"
    assert bridge[987654] == 67890, "Accented Rodon should map to FG ID 67890"


# ---------------------------------------------------------------------------
# resolve_sp_to_fg_id
# ---------------------------------------------------------------------------

def test_resolve_sp_to_fg_id():
    """resolve_sp_to_fg_id tries bridge, then name, then override."""
    bridge = {100: 1001}
    fg_name_to_id = {
        "jose berrios": 12345,
        "louis varland": 99999,
    }

    # Tier 1: bridge hit
    assert resolve_sp_to_fg_id("Any Name", 100, bridge, fg_name_to_id) == 1001

    # Tier 2: accent-strip name fallback
    assert resolve_sp_to_fg_id("Jos\u00e9 Berr\u00edos", None, bridge, fg_name_to_id) == 12345

    # Tier 3: manual override name
    assert resolve_sp_to_fg_id("Louie Varland", None, bridge, fg_name_to_id) == 99999

    # No match
    assert resolve_sp_to_fg_id("Unknown Pitcher", None, bridge, fg_name_to_id) is None
    assert resolve_sp_to_fg_id("Unknown Pitcher", 999, bridge, fg_name_to_id) is None
