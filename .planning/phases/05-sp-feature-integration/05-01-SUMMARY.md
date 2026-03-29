---
phase: 05-sp-feature-integration
plan: 01
subsystem: features
tags: [statcast, fangraphs, chadwick, xwoba, id-bridge, unicode, name-matching]

# Dependency graph
requires:
  - phase: v1-foundation
    provides: FeatureBuilder class, fetch_statcast_pitcher, fetch_sp_stats, cache infrastructure
provides:
  - sp_id_bridge.py module with MLB-to-FanGraphs ID cross-reference
  - Fixed xwOBA feature extraction (est_woba column, merged name column parsing)
  - Multi-tier SP name resolution (exact, override, accent-strip, ID bridge, FG name)
  - test_xwoba_fix verifying non-NaN xwoba_diff
affects: [05-02, 05-03, 05-04, 06-model-retrain]

# Tech tracking
tech-stack:
  added: [pybaseball.chadwick_register, unicodedata]
  patterns: [two-tier ID bridge, accent-normalized name matching, multi-tier resolve chain]

key-files:
  created:
    - src/data/sp_id_bridge.py
    - tests/test_sp_id_bridge.py
  modified:
    - src/features/feature_builder.py
    - tests/test_feature_builder.py

key-decisions:
  - "5-tier SP name resolution chain: exact -> override -> accent-strip -> ID bridge -> FG name lookup"
  - "Chadwick register cached via existing cache infrastructure (reference/chadwick_register.parquet)"
  - "resolve_sp_to_fg_id helper for per-pitcher resolution; _resolve_sp_stats for per-game stats lookup"

patterns-established:
  - "ID bridge pattern: build_mlb_to_fg_bridge(season, fg_df, pitcher_id_map) returns {mlb_id: fg_id}"
  - "Accent normalization: unicodedata.normalize('NFKD') + combining char filter"
  - "Manual override dict for edge cases (Louie/Louis Varland, Luis L. Ortiz)"

requirements-completed: [SP-01, SP-02]

# Metrics
duration: 8min
completed: 2026-03-29
---

# Phase 5 Plan 1: xwOBA Bug Fix and SP ID Bridge Summary

**Fixed 100% NaN xwOBA bug (est_woba column, merged name parsing) and built two-tier Chadwick + accent-strip SP ID cross-reference**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-29T20:19:23Z
- **Completed:** 2026-03-29T20:27:27Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Fixed the v1 xwOBA 100% NaN bug: `est_woba` column (not `xwoba`), `"last_name, first_name"` merged column (not separate columns), proper "Last, First" -> "First Last" reversal
- Built `src/data/sp_id_bridge.py` with Chadwick Register Tier 1 (~83% coverage) and accent-normalized name matching Tier 2 (~17% fallback) plus manual override dict
- Wired multi-tier SP name resolution into `_add_sp_features()` with 5-level fallback chain
- All 20 tests pass (5 sp_id_bridge + 11 feature_builder + 4 leakage)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test stubs and sp_id_bridge module** - `93a5d54` (feat)
2. **Task 2: Fix xwOBA bug and wire ID bridge into SP matching** - `f0420d6` (fix)

## Files Created/Modified
- `src/data/sp_id_bridge.py` - Two-tier MLB-to-FanGraphs ID cross-reference with Chadwick register and accent normalization
- `tests/test_sp_id_bridge.py` - 5 unit tests covering strip_accents, manual overrides, tier1 Chadwick, tier2 accent fallback, resolve helper
- `src/features/feature_builder.py` - Fixed _add_advanced_features xwOBA section, added _resolve_sp_stats helper, wired ID bridge into _add_sp_features
- `tests/test_feature_builder.py` - Added test_xwoba_fix verifying non-NaN xwoba_diff with correct est_woba column and merged name parsing

## Decisions Made
- Used a 5-tier resolution chain (exact -> manual override -> accent-strip -> ID bridge -> FG name lookup) to maximize SP match rate while keeping exact-match as the fast path
- Cached Chadwick register via existing cache infrastructure rather than downloading every time
- Added `_resolve_sp_stats` as a method on FeatureBuilder rather than a standalone function since it needs access to multiple per-season lookups
- Used `_get_pitcher_id_map` from `sp_recent_form` (already cached) for MLB name->ID mapping in the bridge, avoiding duplicate API calls

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ID bridge and xwOBA fix are foundation for all subsequent SP feature work (Plans 02-04)
- `_resolve_sp_stats` method is ready for season-to-date rolling SP features (Plan 02)
- Existing v1 test suite fully passes -- no regressions

## Self-Check: PASSED

- All 5 created/modified files exist on disk
- Commit 93a5d54 (Task 1) verified in git log
- Commit f0420d6 (Task 2) verified in git log
- 20/20 tests pass (test_sp_id_bridge: 5, test_feature_builder: 11, test_leakage: 4)

---
*Phase: 05-sp-feature-integration*
*Completed: 2026-03-29*
