---
phase: 01-data-ingestion-and-raw-cache
plan: 02
subsystem: data
tags: [pybaseball, statsapi, fangraphs, statcast, parquet, caching]

# Dependency graph
requires:
  - phase: 01-data-ingestion-and-raw-cache
    plan: 01
    provides: "cache.py (is_cached, save_to_cache, read_cached), team_mappings.py (normalize_team), test stubs"
provides:
  - "fetch_team_batting(season) -- FanGraphs team batting stats with cache"
  - "fetch_sp_stats(season, min_gs) -- FanGraphs starting pitcher stats filtered to starters"
  - "fetch_statcast_pitcher(season) / fetch_statcast_batter(season) -- Statcast expected stats"
  - "fetch_schedule(season) -- MLB Stats API schedule with probable pitchers and normalized team names"
affects: [02-feature-engineering, 04-kalshi-market-comparison]

# Tech tracking
tech-stack:
  added: [pybaseball, statsapi]
  patterns: [cache-check-then-fetch with Parquet, 2020 short-season flagging, module-level import aliasing for testability]

key-files:
  created:
    - src/data/team_batting.py
    - src/data/sp_stats.py
    - src/data/statcast.py
    - src/data/mlb_schedule.py
  modified:
    - tests/test_sp_stats.py

key-decisions:
  - "Import aliases match test mock targets (pybaseball_team_batting, pybaseball_pitching_stats, etc.) for clean mock patching"
  - "Cache key for sp_stats includes min_gs suffix (sp_stats_{season}_mings{min_gs}) to prevent stale data across different filter thresholds"
  - "Statcast cache key uses statcast_pitcher_{season} (not statcast_pitcher_expected_{season}) for brevity"
  - "MLB schedule filters to Final games only; 2025 included for Phase 4 Kalshi join"
  - "Probable pitcher empty/TBD values normalized to None to prevent join failures in Phase 2"

patterns-established:
  - "Import aliasing: pybaseball functions aliased as pybaseball_{name} at module level for deterministic mock targets"
  - "Season flagging: every loader adds is_shortened_season, season_games, season columns"
  - "Cache key convention: {source}_{datatype}_{season}[_{params}]"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05]

# Metrics
duration: 3min
completed: 2026-03-28
---

# Phase 01 Plan 02: Data Loaders Summary

**Four pybaseball/statsapi data loaders with Parquet caching, 2020 short-season flags, and MLB schedule team normalization via normalize_team**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-28T21:30:19Z
- **Completed:** 2026-03-28T21:33:07Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Implemented team_batting, sp_stats, and statcast loaders using pybaseball with cache-check-then-fetch pattern
- Implemented MLB schedule loader using statsapi with team name normalization and probable pitcher columns
- All 20 test stubs from Plan 01 now pass (14 pybaseball + 6 schedule)
- Every loader adds is_shortened_season/season_games/season columns for downstream use

## Task Commits

Each task was committed atomically:

1. **Task 1: pybaseball loaders -- team_batting.py, sp_stats.py, statcast.py** - `349ad1d` (feat)
2. **Task 2: MLB Stats API schedule loader -- mlb_schedule.py** - `d4d0c5a` (feat)

## Files Created/Modified
- `src/data/team_batting.py` - FanGraphs team batting loader with fetch_team_batting(season)
- `src/data/sp_stats.py` - FanGraphs starting pitcher stats loader with fetch_sp_stats(season, min_gs), starter filtering via GS >= min_gs
- `src/data/statcast.py` - Statcast expected stats with fetch_statcast_pitcher and fetch_statcast_batter, raises ValueError for pre-2015
- `src/data/mlb_schedule.py` - MLB Stats API schedule loader with normalize_team on team columns, SEASON_DATES for 2015-2025, Final-only filtering
- `tests/test_sp_stats.py` - Fixed cache key assertion to include _mings1 suffix

## Decisions Made
- Used module-level import aliases (e.g., `from pybaseball import team_batting as pybaseball_team_batting`) to match test mock targets established in Plan 01 stubs
- Cache key for sp_stats includes `_mings{min_gs}` suffix per plan spec, preventing stale data when different min_gs values are used
- MLB schedule loader uses `from statsapi import schedule as statsapi_schedule` to match test mock path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed sp_stats test cache key mismatch**
- **Found during:** Task 1 (pybaseball loaders)
- **Issue:** Test stub from Plan 01 asserted `is_cached("sp_stats_2023")` but Plan 02 spec requires cache key `sp_stats_{season}_mings{min_gs}` to prevent stale data
- **Fix:** Updated test assertion to check `is_cached("sp_stats_2023_mings1")`
- **Files modified:** tests/test_sp_stats.py
- **Verification:** pytest tests/test_sp_stats.py passes
- **Committed in:** 349ad1d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Test stub from Plan 01 had wrong cache key; fixed to match Plan 02 specification. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All four data loaders are importable and tested
- Phase 2 FeatureBuilder can import fetch_team_batting, fetch_sp_stats, fetch_statcast_pitcher, fetch_statcast_batter, and fetch_schedule
- Phase 4 can use fetch_schedule(2025) for Kalshi market join
- Plan 01-03 (Kalshi loader) is the remaining Phase 1 plan

## Self-Check: PASSED

All created files verified on disk. All commit hashes found in git log.

---
*Phase: 01-data-ingestion-and-raw-cache*
*Completed: 2026-03-28*
