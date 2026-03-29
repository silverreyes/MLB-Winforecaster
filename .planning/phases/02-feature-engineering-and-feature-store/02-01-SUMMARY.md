---
phase: 02-feature-engineering-and-feature-store
plan: 01
subsystem: features
tags: [sabermetrics, log5, pythagorean, park-factors, game-logs, pybaseball, rate-limiting, tdd]

# Dependency graph
requires:
  - phase: 01-data-ingestion-and-raw-cache
    provides: "cache.py (is_cached, save_to_cache, read_cached), team_mappings.py (canonical team codes)"
provides:
  - "log5_probability, pythagorean_win_pct, get_park_factor pure functions"
  - "PARK_FACTORS dict with 30 canonical team entries"
  - "fetch_team_game_log, fetch_all_team_game_logs with rate-limited caching"
  - "ALL_TEAMS canonical team list (30 entries)"
  - "Wave 0 test stubs for FeatureBuilder (10 stubs) and leakage detection (4 stubs)"
affects: [02-02-PLAN, 02-03-PLAN, phase-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED-GREEN for pure formula functions"
    - "Rate-limited batch fetching with failure accumulation (returns list of failed tuples)"
    - "Module-level importorskip for Wave 0 test stubs"

key-files:
  created:
    - src/features/__init__.py
    - src/features/formulas.py
    - src/features/game_logs.py
    - tests/test_formulas.py
    - tests/test_feature_builder.py
    - tests/test_leakage.py
  modified: []

key-decisions:
  - "Used RESEARCH.md park factor estimates (2022-2024 FanGraphs Guts approximations) since FanGraphs was inaccessible for live verification"
  - "fetch_all_team_game_logs returns list[tuple[int, str]] of failures for caller surfacing without log inspection"
  - "Wave 0 stubs use module-level importorskip (entire module skipped) rather than per-test skip decorators"

patterns-established:
  - "Pure formula functions: no side effects, no imports beyond stdlib, fully unit-testable"
  - "Rate-limited batch fetching: RATE_LIMIT_DELAY constant, 2x backoff on error, cached calls skip delay"
  - "Mock-friendly pybaseball aliases: import X as pybaseball_X for clean test patching"

requirements-completed: [FEAT-03, FEAT-05, FEAT-06, FEAT-07]

# Metrics
duration: 4min
completed: 2026-03-29
---

# Phase 2 Plan 01: Formulas, Game Logs, and Wave 0 Stubs Summary

**Log5/Pythagorean/park-factor pure functions with TDD, rate-limited per-game batting log loader, and 14 Wave 0 test stubs defining the FeatureBuilder testing contract**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-29T03:36:52Z
- **Completed:** 2026-03-29T03:41:38Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Implemented three sabermetric formula functions (Log5, Pythagorean with 1.83 exponent, park factors) with 14 passing unit tests via TDD
- Built rate-limited per-game batting log loader with cache-aware batch fetching and failure accumulation
- Created 14 Wave 0 test stubs (10 FeatureBuilder + 4 leakage) that skip cleanly via importorskip

## Task Commits

Each task was committed atomically:

1. **Task 1: Sabermetric formulas module and formula tests (TDD)**
   - `3d4218c` (test: TDD RED - failing tests)
   - `20af3d2` (feat: TDD GREEN - formulas implemented, 14 tests pass)
2. **Task 2: Per-game batting log loader with rate-limited caching** - `59326e0` (feat)
3. **Task 3: Wave 0 test stubs for FeatureBuilder and leakage detection** - `3b190f2` (test)

## Files Created/Modified
- `src/features/__init__.py` - Package marker for features module
- `src/features/formulas.py` - Log5, Pythagorean win%, park factor functions with PARK_FACTORS dict (30 teams)
- `src/features/game_logs.py` - Per-game batting log loader with 2.0s rate limiting, 4.0s error backoff, 30-team ALL_TEAMS list
- `tests/test_formulas.py` - 14 formula correctness tests (Log5 edge cases, Pythagorean exponent, park factor coverage)
- `tests/test_feature_builder.py` - 10 FeatureBuilder stubs for FEAT-01 through FEAT-08
- `tests/test_leakage.py` - 4 temporal safety stubs for FEAT-07

## Decisions Made
- Used RESEARCH.md park factor estimates (2022-2024 FanGraphs Guts approximations) since FanGraphs was inaccessible for live verification. Values are approximate but adequate for v1 -- Phase 3 can test sensitivity.
- fetch_all_team_game_logs returns list[tuple[int, str]] of failed (season, team) pairs so notebooks can surface failures without requiring log inspection.
- Wave 0 stubs use module-level importorskip (entire module skipped when feature_builder does not exist) rather than per-test skip decorators. This produces exit code 5 (no tests collected) when run standalone, but integrates cleanly with full test suite (shows as "2 skipped").

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Formula functions ready for FeatureBuilder to import (Plan 02)
- game_logs loader ready for per-game ingestion notebook (Plan 02/03)
- Wave 0 stubs define the testing contract -- Plan 02 fills in assertions as FeatureBuilder methods are implemented
- Full test suite: 70 passed, 2 skipped -- no regressions from Phase 1

## Self-Check: PASSED

All 6 created files verified on disk. All 4 task commits verified in git log.

---
*Phase: 02-feature-engineering-and-feature-store*
*Completed: 2026-03-29*
