"""Feature column definitions for model training.

Defines the full and core (Statcast-safe) feature sets, target column,
join keys for Phase 4 integration, and metadata columns for splitting.

Note: xwoba_diff is excluded entirely -- it is 100% NaN in the feature matrix
(Statcast xwOBA join failed; see Phase 2 research). The "full" vs "core"
comparison isolates sp_recent_era_diff as the differentiating feature.
"""

# All differential feature columns used by models
# 14 columns total -- xwoba_diff intentionally excluded (0% coverage)
FULL_FEATURE_COLS = [
    'sp_fip_diff',        # FanGraphs SP stats (83.1% coverage)
    'sp_xfip_diff',       # FanGraphs SP stats (83.1% coverage)
    'sp_k_pct_diff',      # FanGraphs SP stats (83.1% coverage)
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

# Core feature set: excludes sp_recent_era_diff (Statcast-derived)
# 13 columns -- near-zero NaN after rolling_ops_diff filtering
CORE_FEATURE_COLS = [c for c in FULL_FEATURE_COLS if c != 'sp_recent_era_diff']

# Target column (binary: 1 = home win, 0 = away win)
TARGET_COL = 'home_win'

# Join keys preserved for Phase 4 Kalshi comparison
JOIN_KEYS = ['game_date', 'home_team', 'away_team']

# Metadata columns needed for splitting and result tracking
META_COLS = ['season', 'home_win', 'game_date', 'home_team', 'away_team']
