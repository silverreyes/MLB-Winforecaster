---
phase: 13-schema-migration-and-game-visibility
verified: 2026-03-31T00:00:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 13: Schema Migration and Game Visibility Verification Report

**Phase Goal:** Schema migration for game_id and reconciliation columns, plus full game visibility — the dashboard shows all scheduled games (not just predicted ones) with status badges and stub cards.
**Verified:** 2026-03-31
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | predictions table has a game_id INTEGER column after migration | VERIFIED | `migration_001.sql` line 5: `ALTER TABLE predictions ADD COLUMN IF NOT EXISTS game_id INTEGER` |
| 2 | predictions table has actual_winner TEXT, prediction_correct BOOLEAN, reconciled_at TIMESTAMPTZ columns after migration | VERIFIED | `migration_001.sql` lines 14-16: all three ADD COLUMN IF NOT EXISTS statements present |
| 3 | unique constraint uq_prediction includes game_id | VERIFIED | `migration_001.sql` lines 9-11: DROP + ADD CONSTRAINT with `UNIQUE (game_date, home_team, away_team, prediction_version, is_latest, game_id)` |
| 4 | pipeline UPSERT inserts game_id without error | VERIFIED | `db.py` line 90: `"game_id"` in `_PREDICTION_COLS`; all 4 runner.py `insert_prediction` calls at lines 174, 217, 256, 320 include `"game_id": game.get("game_id")` |
| 5 | reconciliation columns NOT in the UPSERT update set | VERIFIED | `db.py` lines 94-101: `_PREDICTION_UPDATE_COLS` does not contain actual_winner, prediction_correct, or reconciled_at; Python assertion confirmed at runtime |
| 6 | GET /api/v1/games/{date} returns all scheduled games including those without predictions | VERIFIED | `api/routes/games.py` line 169: `@router.get("/games/{date}")` merges schedule with predictions; 15 tests pass including `test_stub_cards_for_unpredicted_games` and `test_mixed_stub_and_prediction_cards` |
| 7 | Games without predictions have prediction: null (stub cards) | VERIFIED | `api/routes/games.py` line 196: `_build_prediction_group` returns None for empty rows; test `test_stub_cards_for_unpredicted_games` confirms `prediction is None` |
| 8 | game_status correctly mapped: Preview->PRE_GAME, Live->LIVE, Final->FINAL, codedGameState D->POSTPONED | VERIFIED | `mlb_schedule.py` lines 144-166: `map_game_status()` checks coded=='D' first; runtime assertions confirmed all 5 mapping cases |
| 9 | Postponed games return POSTPONED status, not FINAL | VERIFIED | `map_game_status` line 158: `if coded == 'D': return 'POSTPONED'` executes before Final check; `test_postponed_detection` passes |
| 10 | Schedule data cached with 75s TTL | VERIFIED | `mlb_schedule.py` line 140: `_CACHE_TTL_SECONDS = 75`; `get_schedule_cached` implements thread-safe check with `threading.Lock` |
| 11 | Dashboard fetches from /games/{date} instead of /predictions/today | VERIFIED | `frontend/src/App.tsx` line 2: `import { useGames } from './hooks/useGames'`; no import of `usePredictions` present |
| 12 | All scheduled games appear on the dashboard including stub cards | VERIFIED | `GameCardGrid.tsx` maps over `GameResponse[]` from `useGames()`; `GameCard` renders header for all games; `hasPrediction` gates the prediction body |
| 13 | Every game card displays a status badge | VERIFIED | `GameCard.tsx` lines 60-62: `<StatusBadge status={game_status} />` rendered unconditionally in headerRow |
| 14 | React key uses game_id instead of team pair | VERIFIED | `GameCardGrid.tsx` line 15: `key={game.game_id}` |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/migration_001.sql` | Idempotent DDL for game_id and reconciliation columns | VERIFIED | All required DDL present; 21 lines including index |
| `src/pipeline/db.py` | apply_schema with migration, game_id in COLS, reconciliation excluded | VERIFIED | _MIGRATION_DIR constant, apply_schema executes migration_001.sql after schema.sql |
| `src/pipeline/runner.py` | game_id passed through all insert_prediction calls | VERIFIED | 4 occurrences of `game.get("game_id")` at lines 174, 217, 256, 320 |
| `tests/test_pipeline/test_schema.py` | TestMigration class with 6 tests | VERIFIED | TestMigration class present with all 6 required test methods |
| `tests/test_pipeline/conftest.py` | sample_prediction_data includes game_id: 718520 | VERIFIED | Line 82: `"game_id": 718520` present |
| `src/data/mlb_schedule.py` | fetch_schedule_for_date, map_game_status, get_schedule_cached with TTL | VERIFIED | All 3 functions present; uses statsapi.get() for raw status fields |
| `api/models.py` | PredictionGroup, GameResponse, GamesDateResponse | VERIFIED | All 3 models present with correct field types including Literal status |
| `api/routes/games.py` | GET /games/{date} with schedule+prediction merge | VERIFIED | get_games_for_date, build_games_response, _fetch_predictions_for_date all present |
| `api/main.py` | games router registered under /api/v1 | VERIFIED | Line 15: import; line 45: include_router with prefix="/api/v1" |
| `tests/test_api/test_games.py` | TestStatusMapping, TestBuildGamesResponse, TestGamesEndpoint | VERIFIED | All 3 classes present; 15 tests; all pass |
| `frontend/src/api/types.ts` | GameStatus, PredictionGroup, GameResponse, GamesDateResponse | VERIFIED | All 4 types added at lines 45-64; GameGroup preserved for backward compat |
| `frontend/src/hooks/useGames.ts` | useGames() hook with 60s polling | VERIFIED | Fetches /games/{date}; refetchInterval: 60_000; today default |
| `frontend/src/components/StatusBadge.tsx` | StatusBadge with STATUS_CLASS_MAP | VERIFIED | All 4 variants mapped; STATUS_DISPLAY maps PRE_GAME -> 'PRE-GAME' etc. |
| `frontend/src/components/StatusBadge.module.css` | .badge, .preGame, .live, .final, .postponed | VERIFIED | All 5 rules present with correct color variables |
| `frontend/src/components/GameCard.tsx` | GameResponse prop, StatusBadge rendered, hasPrediction gate | VERIFIED | Imports GameResponse; StatusBadge unconditional; prediction body guarded by hasPrediction |
| `frontend/src/components/GameCard.module.css` | .statusBadge | VERIFIED | Line 76: .statusBadge present |
| `frontend/src/components/GameCardGrid.tsx` | GameResponse[], game_id as key | VERIFIED | key={game.game_id} |
| `frontend/src/App.tsx` | useGames instead of usePredictions | VERIFIED | useGames imported and called; no usePredictions reference |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/pipeline/db.py` | `src/pipeline/migration_001.sql` | apply_schema reads and executes migration SQL | WIRED | db.py line 72: `_MIGRATION_DIR / "migration_001.sql"` with `migration_path.read_text()` and `conn.execute()` |
| `src/pipeline/runner.py` | `src/pipeline/db.py` | insert_prediction calls include game_id | WIRED | 4 calls confirmed; each includes `"game_id": game.get("game_id")` |
| `api/routes/games.py` | `src/data/mlb_schedule.py` | get_schedule_cached() called for schedule data | WIRED | games.py line 22: import; line 188: `get_schedule_cached(date)` |
| `api/routes/games.py` | `api/models.py` | returns GamesDateResponse containing GameResponse list | WIRED | games.py imports all 4 models; endpoint returns GamesDateResponse |
| `api/main.py` | `api/routes/games.py` | include_router registers /games/{date} route | WIRED | main.py line 15: import; line 45: `app.include_router(games_router, prefix="/api/v1")` |
| `frontend/src/hooks/useGames.ts` | `/api/v1/games/{date}` | fetchJson call to games endpoint | WIRED | useGames.ts line 19: `fetchJson<GamesDateResponse>(\`/games/${date}\`)` |
| `frontend/src/App.tsx` | `frontend/src/hooks/useGames.ts` | useGames() hook usage | WIRED | App.tsx line 2: import; line 18: destructured call |
| `frontend/src/components/GameCard.tsx` | `frontend/src/components/StatusBadge.tsx` | StatusBadge rendered in headerRow | WIRED | GameCard.tsx line 5: import; lines 60-62: unconditional render |
| `frontend/src/components/GameCardGrid.tsx` | `frontend/src/components/GameCard.tsx` | GameCard rendered with game_id key | WIRED | GameCardGrid.tsx line 14-17: map with `key={game.game_id}` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCHM-01 | 13-01-PLAN.md | predictions table gains game_id column; unique constraint updated to include game_id | SATISFIED | migration_001.sql: ADD COLUMN game_id INTEGER; DROP/ADD CONSTRAINT uq_prediction with game_id included; Python assertion passes |
| SCHM-02 | 13-01-PLAN.md | predictions table gains actual_winner, prediction_correct, reconciled_at — applied via idempotent migration | SATISFIED | migration_001.sql: all 3 ADD COLUMN IF NOT EXISTS statements; explicitly excluded from _PREDICTION_COLS and _PREDICTION_UPDATE_COLS |
| VIBL-01 | 13-02-PLAN.md, 13-03-PLAN.md | All games scheduled for the selected date remain visible regardless of status | SATISFIED | /games/{date} endpoint driven by schedule (not predictions); stub cards for games without predictions; 15 API tests pass |
| VIBL-02 | 13-02-PLAN.md, 13-03-PLAN.md | Each game card displays a status badge (PRE-GAME / LIVE / FINAL / POSTPONED) | SATISFIED | StatusBadge component renders unconditionally in GameCard headerRow; 4 color variants per UI-SPEC; TypeScript compiles clean |

All 4 requirements fully satisfied. No orphaned requirements — REQUIREMENTS.md traceability table shows SCHM-01, SCHM-02, VIBL-01, VIBL-02 mapped to Phase 13.

### Anti-Patterns Found

No blockers or warnings detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

Scan covered: migration_001.sql, db.py, runner.py, mlb_schedule.py, api/routes/games.py, api/models.py, api/main.py, frontend TypeScript and CSS files. No TODO/FIXME/PLACEHOLDER comments found. No stub implementations (empty return, console.log only, no-op handlers). The `placeholders` grep hit in db.py is a SQL string template variable name, not a placeholder marker.

### Human Verification Required

The following behaviors require visual or browser-level confirmation and cannot be verified programmatically:

#### 1. Status Badge Visual Rendering

**Test:** Open the dashboard in a browser on a day with at least one LIVE game. Inspect a game card.
**Expected:** Badge reads "LIVE" with a green background (rgba 34, 197, 94 at 12% opacity) and green text (--color-edge-green).
**Why human:** CSS custom property values (--color-edge-green, --color-accent-muted) are defined in a global stylesheet; correctness requires visual inspection.

#### 2. Stub Card Layout

**Test:** View the dashboard before the pipeline runs for the day (before ~10am ET), or mock a game without a prediction.
**Expected:** Card shows matchup, time, status badge, and "SP TBD" markers on both sides. No probability percentages, no Kalshi section, no edge signal row.
**Why human:** Conditional rendering logic (`hasPrediction`) is correct in code but the actual rendered layout gap can only be confirmed visually.

#### 3. POSTPONED Badge vs FINAL Badge

**Test:** If a postponed game is available in the schedule, verify it shows the amber "POSTPONED" badge rather than the gray "FINAL" badge.
**Expected:** codedGameState "D" games show amber badge reading "POSTPONED".
**Why human:** Requires an actual postponed game in the MLB schedule API response to exercise the production code path end-to-end.

### Gaps Summary

None. All 14 observable truths are verified, all 18 artifacts pass all three levels (exists, substantive, wired), all 9 key links are confirmed wired, all 4 requirements (SCHM-01, SCHM-02, VIBL-01, VIBL-02) are fully satisfied.

Test evidence:
- `python -m pytest tests/test_api/ -q` — 28 passed, 0 failed
- `python -m pytest tests/test_pipeline/test_schema.py::TestMigration::test_reconciliation_excluded_from_upsert -x -q` — 1 passed
- `npx tsc --noEmit` in frontend/ — exit code 0, no errors
- All 6 git commits documented in summaries are confirmed in git log (3424da8, 94c1c35, 2e849b3, 43d2904, 04dd272, b797a0b)

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
