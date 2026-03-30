"""Feature column definitions for model training.

Defines feature sets for v1 backward compatibility, v2 team-only (pre-lineup),
and v2 SP-enhanced (post-lineup) model training.
"""

# --- v1 Feature Set (preserved for apples-to-apples comparison) ---
V1_FULL_FEATURE_COLS = [
    'sp_fip_diff',        # FanGraphs SP stats (83.1% coverage)
    'sp_xfip_diff',       # FanGraphs SP stats (83.1% coverage)
    'sp_k_pct_diff',      # v1 used K% diff; v2 replaced with K-BB%
    'sp_siera_diff',      # FanGraphs SP stats (83.1% coverage)
    'team_woba_diff',     # FanGraphs team batting (100% coverage)
    'team_ops_diff',      # FanGraphs team batting (100% coverage)
    'pyth_win_pct_diff',  # Derived from schedule (100% coverage)
    'rolling_ops_diff',   # Game logs (100% after NaN-row drop)
    'bullpen_era_diff',   # FanGraphs pitching (100% coverage)
    'bullpen_fip_diff',   # FanGraphs pitching (100% coverage)
    'is_home',            # Always 1 (100% coverage)
    'park_factor',        # Static lookup (100% coverage)
    'sp_recent_era_diff', # MLB Stats API game logs (89.4% coverage)
    'log5_home_wp',       # Derived from win records (100% coverage)
]

# --- v2 Team-Only Feature Set (pre-lineup: no SP-specific columns) ---
TEAM_ONLY_FEATURE_COLS = [
    'team_woba_diff',
    'team_ops_diff',
    'pyth_win_pct_diff',
    'rolling_ops_diff',
    'bullpen_era_diff',
    'bullpen_fip_diff',
    'is_home',
    'park_factor',
    'log5_home_wp',
]

# --- v2 SP-Enhanced Feature Set (post-lineup: includes all new SP columns) ---
SP_ENHANCED_FEATURE_COLS = [
    'sp_fip_diff',
    'sp_xfip_diff',
    'sp_siera_diff',
    'sp_k_bb_pct_diff',         # NEW: replaces sp_k_pct_diff
    'sp_whip_diff',              # NEW
    'sp_era_diff',               # NEW: season-to-date rolling
    'sp_recent_era_diff',
    'sp_recent_fip_diff',        # NEW: 30-day rolling FIP
    'sp_pitch_count_last_diff',  # NEW: pitch count from last start
    'sp_days_rest_diff',         # NEW: days since last start
    'xwoba_diff',                # Fixed in v2 (was 100% NaN in v1)
    'team_woba_diff',
    'team_ops_diff',
    'pyth_win_pct_diff',
    'rolling_ops_diff',
    'bullpen_era_diff',
    'bullpen_fip_diff',
    'is_home',
    'park_factor',
    'log5_home_wp',
]

# --- v2 SP-Enhanced Pruned Feature Set (post VIF/SHAP analysis from Plan 06-01) ---
# Removed: is_home (constant=inf VIF), team_woba_diff (VIF=163), sp_siera_diff (VIF=18)
SP_ENHANCED_PRUNED_COLS = [
    'sp_fip_diff',
    'sp_xfip_diff',
    'sp_k_bb_pct_diff',
    'sp_whip_diff',
    'sp_era_diff',
    'sp_recent_era_diff',
    'sp_recent_fip_diff',
    'sp_pitch_count_last_diff',
    'sp_days_rest_diff',
    'xwoba_diff',
    'team_ops_diff',
    'pyth_win_pct_diff',
    'rolling_ops_diff',
    'bullpen_era_diff',
    'bullpen_fip_diff',
    'park_factor',
    'log5_home_wp',
]

# Backward-compatible aliases (FULL_FEATURE_COLS = V1 for existing code)
FULL_FEATURE_COLS = V1_FULL_FEATURE_COLS
CORE_FEATURE_COLS = [c for c in V1_FULL_FEATURE_COLS if c != 'sp_recent_era_diff']

# Target column (binary: 1 = home win, 0 = away win)
TARGET_COL = 'home_win'

# Join keys preserved for Kalshi comparison
JOIN_KEYS = ['game_date', 'home_team', 'away_team']

# Metadata columns needed for splitting and result tracking
META_COLS = ['season', 'home_win', 'game_date', 'home_team', 'away_team']
