---
phase: 01-data-ingestion-and-raw-cache
plan: 01
subsystem: data
tags: [pandas, pyarrow, pytest, parquet, caching, team-normalization]

# Dependency graph
requires: []
provides:
  - "requirements.txt with pinned dependencies for all Phase 1 work"
  - "src/data/cache.py: shared cache-check-then-fetch infrastructure (Parquet + JSON manifest)"
  - "src/data/team_mappings.py: canonical team name normalization for all 30 MLB teams"
  - "pyproject.toml: editable install support and pytest configuration"
  - "Wave 0 test stubs for DATA-01 through DATA-06"
affects: [01-02-PLAN, 01-03-PLAN, 02-feature-engineering]

# Tech tracking
tech-stack:
  added: [pandas 2.2.3, pyarrow, pybaseball, MLB-StatsAPI, scikit-learn, xgboost, matplotlib, seaborn, pytest, python-dotenv]
  patterns: [cache-check-then-fetch with JSON manifest, Parquet with snappy compression, importorskip for Wave 0 stubs]

key-files:
  created:
    - requirements.txt
    - pyproject.toml
    - .gitignore
    - .env.example
    - src/__init__.py
    - src/data/__init__.py
    - src/data/cache.py
    - src/data/team_mappings.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_cache.py
    - tests/test_team_batting.py
    - tests/test_sp_stats.py
    - tests/test_statcast.py
    - tests/test_mlb_schedule.py
    - tests/test_kalshi.py
    - notebooks/.gitkeep
  modified: []

key-decisions:
  - "Upgraded pyarrow from 14.0.2 to >=15.0.0 due to numpy 2.x incompatibility"
  - "Anchored /data/ in .gitignore to avoid matching src/data/"
  - "Created full cache.py in Task 1 instead of stub because verification required importable functions"

patterns-established:
  - "Cache pattern: save_to_cache() writes Parquet + updates JSON manifest; read_cached() reads by key"
  - "Test isolation: mock_cache_dir fixture patches CACHE_DIR and MANIFEST_PATH to tmp_path"
  - "Loader test stubs: importorskip at module level, mock external APIs, verify columns and caching"

requirements-completed: []  # Scaffolding only -- loaders implemented in Plans 02/03

# Metrics
duration: 9min
completed: 2026-03-28
---

# Phase 1 Plan 01: Scaffolding Summary

**Python project scaffolding with pandas 2.2.x pin, Parquet cache infrastructure, 114-entry team name normalization, and Wave 0 test stubs for all 6 data requirements**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-28T21:16:43Z
- **Completed:** 2026-03-28T21:25:59Z
- **Tasks:** 3
- **Files modified:** 17

## Accomplishments

- Installable Python project with editable install (`pip install -e .`) and all Phase 1+3 dependencies
- Cache module with 7 public functions and JSON manifest tracking, backed by 15 passing unit tests
- Team name normalization covering 114 variants across all 30 MLB teams (abbreviations, full names, historical names)
- Wave 0 test stubs (29 test functions across 5 loader files) defining expected interfaces for Plans 02 and 03

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding** - `1db215e` (feat)
2. **Task 2: Cache module and team mappings** - `42ae75e` (feat)
3. **Task 3: Wave 0 test stubs** - `69474f8` (test)

## Files Created/Modified

- `requirements.txt` - Pinned dependencies: pandas 2.2.x, pybaseball, MLB-StatsAPI, ML libs, pytest
- `pyproject.toml` - Editable install config with setuptools package discovery and pytest settings
- `.gitignore` - Ignores /data/, __pycache__/, .env, IDE files
- `.env.example` - Documents optional KALSHI_API_KEY
- `src/data/cache.py` - Cache infrastructure: load/save manifest, is_cached, save_to_cache, read_cached
- `src/data/team_mappings.py` - TEAM_MAP (114 entries) and normalize_team() for all 30 MLB teams
- `tests/test_cache.py` - 15 unit tests for cache module with tmp_path isolation
- `tests/conftest.py` - Shared mock_cache_dir fixture
- `tests/test_team_batting.py` - 5 test stubs for DATA-02 (columns, 2020 flag, caching)
- `tests/test_sp_stats.py` - 5 test stubs for DATA-03 (FIP, starter filter, caching)
- `tests/test_statcast.py` - 4 test stubs for DATA-04 (xwoba, 2020 flag, caching)
- `tests/test_mlb_schedule.py` - 6 test stubs for DATA-01 (pitchers, teams, 2025 support)
- `tests/test_kalshi.py` - 9 test stubs for DATA-06 (prices, voided markets, KXMLB filter)

## Decisions Made

1. **pyarrow version upgraded from 14.0.2 to >=15.0.0** - pyarrow 14.0.2 is compiled against NumPy 1.x and crashes with NumPy 2.4.3 installed in the environment. Upgraded to latest compatible version (23.0.1 resolved).
2. **Anchored .gitignore data/ path** - The unanchored `data/` pattern matched `src/data/`, preventing git from tracking source files. Changed to `/data/` to only ignore the top-level data cache directory.
3. **Full cache.py in Task 1** - Plan had cache.py split across Task 1 (stub) and Task 2 (full), but Task 1 verification required `from src.data.cache import load_manifest` to succeed with an editable install. Wrote complete implementation in Task 1 to satisfy verification.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyarrow 14.0.2 incompatible with NumPy 2.x**
- **Found during:** Task 1 (dependency installation)
- **Issue:** pyarrow 14.0.2 was compiled with NumPy 1.x; importing pandas or pyarrow crashed with `_ARRAY_API not found` on NumPy 2.4.3
- **Fix:** Updated requirements.txt to `pyarrow>=15.0.0` and installed 23.0.1
- **Files modified:** requirements.txt
- **Verification:** `import pandas; import pyarrow` both succeed without errors
- **Committed in:** 1db215e (Task 1 commit)

**2. [Rule 1 - Bug] .gitignore `data/` matched `src/data/`**
- **Found during:** Task 1 (git add)
- **Issue:** Unanchored `data/` pattern in .gitignore ignored all directories named data, including `src/data/` which contains source code
- **Fix:** Changed to `/data/` (anchored to repo root)
- **Files modified:** .gitignore
- **Verification:** `git add src/data/*.py` succeeds without ignore warnings
- **Committed in:** 1db215e (Task 1 commit)

**3. [Rule 3 - Blocking] pandas 2.3.3 installed despite <2.3 constraint**
- **Found during:** Task 1 (dependency installation)
- **Issue:** pip resolved pandas 2.3.3 from another package's dependency, ignoring the requirements.txt constraint
- **Fix:** Explicitly ran `pip install pandas==2.2.3` to force correct version
- **Files modified:** None (runtime environment fix)
- **Verification:** `python -c "import pandas; assert pandas.__version__.startswith('2.2')"` passes
- **Committed in:** N/A (environment fix, not a file change)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All fixes necessary for basic functionality. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Cache infrastructure ready for all loaders (Plans 02 and 03)
- Team mappings ready for normalization in all data ingestion
- Test stubs define expected interfaces -- Plan 02 loaders must make them pass
- pandas 2.2.3 confirmed compatible with pyarrow, pybaseball, and all dependencies

## Self-Check: PASSED

- 17/17 files found
- 3/3 commits found (1db215e, 42ae75e, 69474f8)
- 15 cache tests passing, 5 loader test modules skipped (importorskip)

---
*Phase: 01-data-ingestion-and-raw-cache*
*Plan: 01*
*Completed: 2026-03-28*
