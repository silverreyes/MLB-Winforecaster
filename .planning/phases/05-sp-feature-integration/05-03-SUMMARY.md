---
phase: 05-sp-feature-integration
plan: 03
subsystem: features
tags: [cumsum, shift, rolling, era, whip, k-bb-pct, cold-start, temporal-safety, game-log-v2]

# Dependency graph
requires:
  - phase: 05-sp-feature-integration (plan 01)
    provides: SP ID bridge, multi-tier name resolution, xwOBA bug fix
  - phase: 05-sp-feature-integration (plan 02)
    provides: v2 game log extraction (K/BB/HR/pitchCount/GS), FIP/pitch-count bulk functions
provides:
  - Season-to-date rolling SP features via cumsum+shift(1) for ERA and K-BB rate
  - sp_era_diff, sp_k_bb_pct_diff, sp_whip_diff new differential columns
  - Cold-start imputation (previous-season FanGraphs -> league-average constants)
  - sp_k_pct_diff removed (replaced by sp_k_bb_pct_diff)
  - Temporal safety tests verifying shift(1) per-game value correctness
affects: [05-04, 06-model-retrain, feature_sets.py constants]

# Tech tracking
tech-stack:
  added: []
  patterns: [cumsum-shift1-rolling, cold-start-imputation-cascade, league-avg-constants]

key-files:
  created: []
  modified:
    - src/features/feature_builder.py
    - tests/test_feature_builder.py
    - tests/test_leakage.py

key-decisions:
  - "Season-to-date ERA and K-BB rate use cumsum+shift(1) from v2 game logs (temporally safe)"
  - "WHIP and SIERA kept from FanGraphs season-level (hits not in game log v2, SIERA not computable)"
  - "Cold-start cascade: rolling -> prev-season FanGraphs -> league-average constants"
  - "K-BB rate computed per 9 IP for scale: ((cumK - cumBB) * 9) / cumIP"
  - "Six league-average constants added at module level for cold-start imputation"

patterns-established:
  - "Cold-start cascade pattern: rolling -> prev_season_stats -> LEAGUE_AVG_* constants"
  - "Per-pitcher per-season groupby with cumsum+shift(1) for temporal safety"
  - "Game log iteration via _fetch_pitcher_game_log_v2 per pitcher per season"

requirements-completed: [SP-03, SP-04, SP-05, SP-06, SP-10]

# Metrics
duration: 9min
completed: 2026-03-29
---

# Phase 5 Plan 3: Season-to-Date Rolling SP Features Summary

**Cumsum+shift(1) rolling for ERA and K-BB rate, FanGraphs WHIP/SIERA, cold-start imputation via previous-season and league-average fallback**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-29T20:36:39Z
- **Completed:** 2026-03-29T20:46:32Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Refactored _add_sp_features() to use per-game season-to-date rolling for ERA and K-BB rate via cumsum+shift(1), eliminating temporal leakage from season-aggregate lookups
- Added three new differential columns: sp_era_diff, sp_k_bb_pct_diff, sp_whip_diff
- Removed sp_k_pct_diff (replaced by sp_k_bb_pct_diff which is a stronger signal)
- Implemented cold-start cascade: rolling -> previous-season FanGraphs -> league-average constants (6 constants: ERA 4.25, K-BB% 0.10, WHIP 1.30, SIERA 4.15, FIP 4.15, xFIP 4.10)
- Added 7 new tests covering K-BB% diff, WHIP diff, ERA diff values, cold-start fallback, temporal safety with per-game verification, and no-leakage std > 0 assertion
- All 22 tests pass (16 feature_builder + 6 leakage)

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor _add_sp_features to season-to-date rolling + new differentials** - `6e05c17` (feat)
2. **Task 2: Add test coverage for rolling SP features, cold-start, temporal safety** - `046b648` (test)

## Files Created/Modified
- `src/features/feature_builder.py` - Refactored _add_sp_features with cumsum+shift(1) rolling, cold-start cascade, league-average constants, new imports
- `tests/test_feature_builder.py` - Added test_k_bb_pct_diff, test_whip_diff, test_era_diff, test_cold_start, test_feature_set_constants; updated all mocks with IDfg, K-BB%, pitcher_id_map, game_log_v2
- `tests/test_leakage.py` - Added test_sp_std_no_leakage, test_sp_temporal_safety; updated mocks and _build_with_mocks

## Decisions Made
- Used cumsum+shift(1) pattern from v1 _compute_cumulative_win_pct for season-to-date ERA and K-BB rate (proven temporal safety pattern)
- K-BB rate computed as ((cumK - cumBB) * 9) / cumIP (per 9 IP scale) because BF is not in game log v2; scale cancels in differentials
- WHIP and SIERA remain FanGraphs season-level because hits are not in game log v2 and SIERA is not computable from game logs
- Cold-start fallback uses fetch_sp_stats(season-1) for previous-season stats; falls through to league-average constants for rookies
- FIP and xFIP also use cold-start cascade (FG season -> prev_season -> league_avg) for consistency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All SP differential columns ready for feature_sets.py constant updates (Plan 04)
- feature_store_v2.parquet can now include sp_era_diff, sp_k_bb_pct_diff, sp_whip_diff
- Temporal safety proven by test_sp_temporal_safety with per-game expected value assertions
- Cold-start handling covers both first-start-of-season and rookie pitchers

## Self-Check: PASSED

- [x] src/features/feature_builder.py exists and contains cumsum+shift(1) pattern
- [x] tests/test_feature_builder.py exists with 5 new test functions
- [x] tests/test_leakage.py exists with 2 new test functions
- [x] Commit 6e05c17 (Task 1) verified in git log
- [x] Commit 046b648 (Task 2) verified in git log
- [x] All 22 tests pass (16 feature_builder + 6 leakage)

---
*Phase: 05-sp-feature-integration*
*Completed: 2026-03-29*
