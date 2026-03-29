---
phase: 02-feature-engineering-and-feature-store
plan: 02
subsystem: features
tags: [feature-engineering, sabermetrics, rolling-windows, temporal-safety, shift1, pandas, pitching-stats-range]

# Dependency graph
requires:
  - phase: 01-data-ingestion-and-raw-cache
    provides: Cached Parquet files for schedule, SP stats, team batting, Statcast, Kalshi, game logs
  - phase: 02-01
    provides: formulas.py (Log5, Pythagorean, park factors), game_logs.py (per-game team batting loader)
provides:
  - FeatureBuilder class with build() method producing game-level feature DataFrame
  - sp_recent_form.py with cached 30-day ERA window via pitching_stats_range()
  - 14 differential feature columns plus outcome label and Kalshi price
  - Full unit tests (10 FeatureBuilder + 4 leakage) with mocked data loaders
affects: [02-03, 03-model-training, 04-kalshi-comparison]

# Tech tracking
tech-stack:
  added: [pybaseball.pitching_stats_range]
  patterns: [shift(1)-with-groupby-season for temporal safety, dict-lookup-then-map for feature joins, bulk-fetch-with-cache for date-range API calls]

key-files:
  created:
    - src/features/feature_builder.py
    - src/features/sp_recent_form.py
  modified:
    - tests/test_feature_builder.py
    - tests/test_leakage.py

key-decisions:
  - "SP recent form uses pitching_stats_range() for 30-day ERA window per CONTEXT.md locked decision, not season-level ERA"
  - "Bullpen relievers identified by GS < 3 AND IP >= 5 (excludes position players who pitched in blowouts)"
  - "Log5 win probability derived from game-by-game cumulative win% with shift(1), not season-level W-L"
  - "Pythagorean win% uses schedule-derived runs (home_score/away_score aggregation per team per season)"
  - "Statcast xwOBA joined via first_name + last_name concatenation to match schedule pitcher names"

patterns-established:
  - "dict-lookup pattern: Build {(season, name): stats} from loader, then df.apply(lambda) for O(1) lookups"
  - "shift(1) + groupby(['team', 'season']) for all rolling features -- NON-NEGOTIABLE per FEAT-07"
  - "Empty DataFrame caching: always cache even empty results to avoid re-hitting API on reruns"
  - "bulk fetch pattern: deduplicate keys, check cache first, rate-limit only uncached calls"

requirements-completed: [FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-07]

# Metrics
duration: 7min
completed: 2026-03-29
---

# Phase 2 Plan 02: FeatureBuilder Summary

**FeatureBuilder class with 10-stage build() pipeline computing 14+ differential features (SP, offense, rolling OPS, bullpen, park, advanced/xwOBA/Log5/30-day ERA) with shift(1) temporal safety, plus 14 tests on mocked data**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-29T03:44:56Z
- **Completed:** 2026-03-29T03:52:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- FeatureBuilder class with complete 10-stage build() pipeline covering FEAT-01 through FEAT-07
- SP recent form loader (sp_recent_form.py) using pitching_stats_range() with caching and rate limiting per CONTEXT.md locked decision
- All rolling features enforce temporal safety via shift(1) within groupby(["team", "season"]) with season boundary reset
- 14 tests pass (10 FeatureBuilder + 4 leakage) with all data loaders mocked; full suite 84 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: SP recent form loader and FeatureBuilder class** - `e940c4b` (feat)
2. **Task 2: Flesh out test stubs with real assertions** - `14b3af5` (test)

## Files Created/Modified
- `src/features/feature_builder.py` - FeatureBuilder class with 10-stage build() pipeline, all differential feature computation
- `src/features/sp_recent_form.py` - 30-day ERA window loader via pitching_stats_range() with caching and bulk fetch
- `tests/test_feature_builder.py` - 10 tests: SP/offense/rolling/bullpen/park/advanced differentials, TBD exclusion, schema, columns
- `tests/test_leakage.py` - 4 tests: shift(1) verification, season boundary reset, outcome masking independence, early-season NaN

## Decisions Made
- SP recent form uses pitching_stats_range() for 30-day ERA window per CONTEXT.md locked decision (not season ERA)
- Bullpen relievers identified by GS < 3 AND IP >= 5 to exclude position players who pitched in blowouts
- Log5 win probability derived from game-by-game cumulative win% with shift(1), not season-level aggregate W-L
- Pythagorean win% computed from schedule-derived runs (home_score/away_score per team per season) rather than team_batting R column
- Statcast xwOBA lookup built from first_name + last_name columns to match schedule pitcher name format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- FeatureBuilder is complete and tested, ready for Plan 03 (build notebook + Parquet output)
- Plan 03 can call FeatureBuilder.build() to generate the final feature matrix file
- All 14 differential columns computed and verified via unit tests
- Temporal safety (shift(1), season boundary reset) proven by 4 dedicated leakage tests

## Self-Check: PASSED

- All 5 files exist on disk
- Both task commits (e940c4b, 14b3af5) found in git log
- 84 tests pass in full suite

---
*Phase: 02-feature-engineering-and-feature-store*
*Completed: 2026-03-29*
