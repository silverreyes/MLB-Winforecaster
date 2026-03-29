"""SP ID bridge: MLB Stats API player_id <-> FanGraphs IDfg cross-reference.

Two-tier matching approach:
  1. Chadwick Register: key_mlbam -> key_fangraphs (covers ~83% of active SPs)
  2. Accent-normalized name matching as fallback (covers remaining ~17%)

Plus a manual override dict for edge cases where both tiers fail.
"""

import unicodedata
import logging
import pandas as pd
from pybaseball.playerid_lookup import chadwick_register
from src.data.cache import is_cached, save_to_cache, read_cached

logger = logging.getLogger(__name__)

# Edge cases where Chadwick + accent-strip both fail
MANUAL_OVERRIDES: dict[str, str] = {
    "Louie Varland": "Louis Varland",   # MLB API: Louie, FG: Louis
    "Luis L. Ortiz": "Luis Ortiz",      # MLB API has middle initial, FG doesn't
}


def strip_accents(s: str) -> str:
    """Remove diacritical marks for name normalization."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def build_mlb_to_fg_bridge(
    season: int,
    fg_df: pd.DataFrame,
    pitcher_id_map: dict[str, int] | None = None,
) -> dict[int, int]:
    """Build {mlb_player_id: fangraphs_id} cross-reference.

    Two-tier approach:
    1. Chadwick Register: key_mlbam -> key_fangraphs (covers ~83% of SPs)
    2. Accent-normalized name matching as fallback (covers remaining ~17%)

    Args:
        season: MLB season year (used to filter Chadwick to active players)
        fg_df: FanGraphs pitching_stats DataFrame with columns 'Name' and 'IDfg'
        pitcher_id_map: Optional {fullName: mlb_player_id} from MLB Stats API.
            If None, Tier 2 only uses Chadwick-based MLB IDs.

    Returns:
        dict mapping MLB Stats API player_id (int) to FanGraphs IDfg (int)
    """
    id_bridge: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Tier 1: Chadwick Register (key_mlbam -> key_fangraphs)
    # ------------------------------------------------------------------
    cache_key = "chadwick_register"
    try:
        if is_cached(cache_key):
            chad_df = read_cached(cache_key)
        else:
            chad_df = chadwick_register()
            if chad_df is not None and not chad_df.empty:
                save_to_cache(chad_df, cache_key, "reference/chadwick_register.parquet", season)
    except Exception as e:
        logger.warning("Failed to load Chadwick register: %s", e)
        chad_df = pd.DataFrame()

    if chad_df is not None and not chad_df.empty:
        # Filter to rows with valid IDs
        valid = chad_df[
            (chad_df["key_mlbam"].notna())
            & (chad_df["key_fangraphs"].notna())
            & (chad_df["key_mlbam"] != -1)
            & (chad_df["key_fangraphs"] != -1)
        ].copy()

        # Optionally filter to recently active players
        if "mlb_played_last" in valid.columns:
            valid = valid[valid["mlb_played_last"] >= season - 5]

        id_bridge = dict(
            zip(valid["key_mlbam"].astype(int), valid["key_fangraphs"].astype(int))
        )
        logger.info("Tier 1 (Chadwick): %d MLB->FG mappings", len(id_bridge))

    # ------------------------------------------------------------------
    # Tier 2: Accent-normalized name fallback
    # ------------------------------------------------------------------
    # Build FanGraphs name -> IDfg lookup (accent-stripped, lowercase)
    fg_name_to_id: dict[str, int] = {}
    if fg_df is not None and not fg_df.empty:
        for _, row in fg_df.iterrows():
            name = row.get("Name", "")
            idfg = row.get("IDfg")
            if name and idfg is not None:
                normalized = strip_accents(str(name)).lower()
                fg_name_to_id[normalized] = int(idfg)

    # Build MLB name -> player_id lookup (accent-stripped, lowercase)
    mlb_name_to_id: dict[str, int] = {}
    if pitcher_id_map:
        for name, pid in pitcher_id_map.items():
            normalized = strip_accents(str(name)).lower()
            mlb_name_to_id[normalized] = int(pid)

    # Apply MANUAL_OVERRIDES first
    for mlb_name, fg_name in MANUAL_OVERRIDES.items():
        mlb_norm = strip_accents(mlb_name).lower()
        fg_norm = strip_accents(fg_name).lower()
        mlb_pid = mlb_name_to_id.get(mlb_norm)
        fg_id = fg_name_to_id.get(fg_norm)
        if mlb_pid is not None and fg_id is not None and mlb_pid not in id_bridge:
            id_bridge[mlb_pid] = fg_id

    # For any MLB player_id not yet in bridge, try accent-strip match
    tier2_count = 0
    for norm_name, mlb_pid in mlb_name_to_id.items():
        if mlb_pid not in id_bridge:
            fg_id = fg_name_to_id.get(norm_name)
            if fg_id is not None:
                id_bridge[mlb_pid] = fg_id
                tier2_count += 1

    if tier2_count > 0:
        logger.info("Tier 2 (accent-strip): %d additional mappings", tier2_count)

    # Log unmatched
    if pitcher_id_map:
        matched = sum(1 for pid in pitcher_id_map.values() if pid in id_bridge)
        total = len(pitcher_id_map)
        unmatched = total - matched
        if unmatched > 0:
            logger.info("ID bridge: %d/%d matched, %d unmatched", matched, total, unmatched)

    return id_bridge


def resolve_sp_to_fg_id(
    pitcher_name: str,
    pitcher_mlb_id: int | None,
    bridge: dict[int, int],
    fg_name_to_id: dict[str, int],
) -> int | None:
    """Resolve a single pitcher to their FanGraphs ID.

    Tries: (1) MLB ID via bridge, (2) accent-strip name, (3) MANUAL_OVERRIDES name.
    Returns FanGraphs ID or None.
    """
    # Tier 1: Direct bridge lookup
    if pitcher_mlb_id is not None:
        fg_id = bridge.get(pitcher_mlb_id)
        if fg_id is not None:
            return fg_id

    # Tier 2: Accent-stripped name lookup
    if pitcher_name:
        normalized = strip_accents(pitcher_name).lower()
        fg_id = fg_name_to_id.get(normalized)
        if fg_id is not None:
            return fg_id

        # Tier 3: Manual override name, then re-lookup
        override_name = MANUAL_OVERRIDES.get(pitcher_name)
        if override_name:
            override_norm = strip_accents(override_name).lower()
            fg_id = fg_name_to_id.get(override_norm)
            if fg_id is not None:
                return fg_id

    return None
