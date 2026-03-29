---
phase: 05-sp-feature-integration
plan: 02
subsystem: features
tags: [mlb-stats-api, fip, pitch-count, days-rest, game-log, caching]

# Dependency graph
requires:
  - phase: 05-sp-feature-integration (plan 01)
    provides: SP ID bridge and xwOBA bug fix
provides:
  - v2 game log extraction with 8 columns (K/BB/HR/pitchCount/GS)
  - 30-day rolling raw FIP computation (compute_rolling_fip_bulk)
  - Pitch count from last start and days rest computation (compute_pitch_count_and_rest_bulk)
  - Cold-start imputation constants (LEAGUE_AVG_PITCH_COUNT=93, MAX_DAYS_REST=7)
affects: [05-sp-feature-integration plan 03, 05-sp-feature-integration plan 04, feature_builder integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [versioned-cache-key, cold-start-imputation, raw-fip-formula]

key-files:
  created:
    - tests/test_sp_recent_form.py
  modified:
    - src/features/sp_recent_form.py

key-decisions:
  - "v2 cache key (pitcher_game_log_v2_) distinct from v1 to prevent stale 3-column data reuse"
  - "Raw FIP formula (no cFIP constant) because constant cancels in home-away differentials"
  - "Cold-start imputation: 93 pitches (league average), 7 days rest (capped maximum)"

patterns-established:
  - "Versioned cache key pattern: bump suffix (_v2) when schema changes to avoid stale data"
  - "Cold-start imputation pattern: use league-average constants when no prior data exists"

requirements-completed: [SP-07, SP-08]

# Metrics
duration: 3min
completed: 2026-03-29
---

# Phase 5 Plan 2: Extended Game Log + FIP + Pitch Count Summary

**v2 game log extraction with K/BB/HR/pitchCount for 30-day rolling FIP and pitch count/days rest features**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T20:30:31Z
- **Completed:** 2026-03-29T20:33:45Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Extended pitcher game log extraction from 3 columns to 8 columns (strikeouts, base_on_balls, home_runs, number_of_pitches, games_started added)
- Implemented 30-day rolling raw FIP computation: ((13*HR) + (3*BB) - (2*K)) / IP
- Implemented pitch count from last start and days rest with cold-start imputation (93 pitches, 7-day cap)
- Comprehensive test suite with 13 tests covering all new functionality
- Original v1 _fetch_pitcher_game_log() preserved unchanged for backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test stubs and extend game log extraction** - `2fea417` (feat)

**Plan metadata:** [pending] (docs: complete plan)

## Files Created/Modified
- `src/features/sp_recent_form.py` - Extended with v2 game log, FIP bulk, pitch count/rest bulk functions
- `tests/test_sp_recent_form.py` - 13 unit tests for v2 extraction, FIP, pitch count, days rest, cold start

## Decisions Made
- Used versioned cache key (`pitcher_game_log_v2_`) to prevent stale 3-column cached data from being reused by v2 functions
- Raw FIP formula (no cFIP constant) chosen because the constant cancels out in home-away differentials
- Cold-start imputation uses league-average 93 pitches per start and 7-day max rest cap

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- v2 game log, FIP computation, and pitch count/rest functions are ready for integration into FeatureBuilder (plan 03)
- All exports match the plan's artifact spec: fetch_sp_recent_form_bulk, _fetch_pitcher_game_log_v2, compute_rolling_fip_bulk, compute_pitch_count_and_rest_bulk

## Self-Check: PASSED

- [x] src/features/sp_recent_form.py exists
- [x] tests/test_sp_recent_form.py exists
- [x] 05-02-SUMMARY.md exists
- [x] Commit 2fea417 exists
- [x] All 13 tests pass

---
*Phase: 05-sp-feature-integration*
*Completed: 2026-03-29*
