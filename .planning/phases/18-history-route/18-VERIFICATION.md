---
phase: 18-history-route
verified: 2026-04-01T07:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 18: History Route Verification Report

**Phase Goal:** Users can review their prediction track record over any date range with accuracy metrics per model
**Verified:** 2026-04-01T07:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths — Plan 01 (Backend)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/v1/history?start=...&end=... returns JSON with games and accuracy | VERIFIED | Route handler exists, 200 confirmed via test `test_route_returns_valid_response` |
| 2 | Only rows with prediction_correct IS NOT NULL are returned | VERIFIED | SQL in `get_history()` contains `AND p.prediction_correct IS NOT NULL`; test `test_only_prediction_correct_not_null` passes |
| 3 | Post-lineup prediction preferred; pre-lineup fallback | VERIFIED | SQL uses `ROW_NUMBER() OVER (PARTITION BY p.game_id ORDER BY CASE p.prediction_version WHEN 'post_lineup' THEN 1 ...)`; tests confirm |
| 4 | Per-model accuracy percentages computed from rows in the date range | VERIFIED | `_compute_accuracy()` in `api/routes/history.py`; 3 accuracy tests pass including split-model disagreement case |
| 5 | Default 400 response on invalid date format | VERIFIED | `datetime.strptime(val, "%Y-%m-%d")` raises HTTPException(400); tests `test_invalid_start_date_returns_400` and `test_invalid_end_date_returns_400` pass |

### Observable Truths — Plan 02 (Frontend)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | User can navigate to #/history from AccuracyStrip "View History" link | VERIFIED | `AccuracyStrip.tsx` line 30: `<a href="#/history" className={styles.historyLink}>` |
| 7 | User can navigate back to main dashboard from history page | VERIFIED | `HistoryPage.tsx` line 56: `<a href="#/" className={styles.backLink}>` and `Header.tsx` line 37: `<a href="#/" className={styles.titleLink}>` |
| 8 | User can select a start date and end date to filter history results | VERIFIED | `HistoryPage.tsx` renders two `<input type="date">` controls with `onChange` handlers that update `startDate`/`endDate` state; `useHistory` hook re-queries on state change |
| 9 | User sees a table of past predictions with Date, Matchup, Score, LR%, RF%, XGB%, and check/X columns | VERIFIED | `HistoryPage.tsx` table thead has all 7 columns; tbody renders per-game rows with `formatProb()` for probs and unicode check/cross markers |
| 10 | User sees per-model accuracy percentages above the table | VERIFIED | Accuracy summary strip renders LR/RF/XGB labels + `acc.pct` values from `useHistory()` hook |
| 11 | When no completed games exist in range, user sees "No completed games in this range" message | VERIFIED | `HistoryPage.tsx` line 110: `<h3>No completed games in this range</h3>` in `games.length === 0` branch |

**Score:** 11/11 truths verified

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/db.py` | `get_history()` function | VERIFIED | Lines 504-551; full CTE SQL with ROW_NUMBER, LEFT JOIN game_logs, `game_id::INTEGER` cast |
| `api/models.py` | `HistoryRow`, `ModelAccuracy`, `HistoryResponse` Pydantic models | VERIFIED | Lines 126-154; all three models present with correct fields |
| `api/routes/history.py` | GET /history route handler | VERIFIED | `def get_history_route(` at line 69; `def _compute_accuracy(` at line 19; `router = APIRouter(tags=["history"])` at line 16 |
| `api/main.py` | History router registration | VERIFIED | Line 18: `from api.routes.history import router as history_router`; Line 52: `app.include_router(history_router, prefix="/api/v1")` |
| `tests/test_api/test_history.py` | History endpoint tests (min 80 lines, 10+ test functions) | VERIFIED | 299 lines, 15 test functions, all 15 pass |

### Plan 02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/api/types.ts` | `HistoryRow`, `ModelAccuracy`, `HistoryResponse` TypeScript interfaces | VERIFIED | Lines 99, 111, 117 confirm all three interfaces exported |
| `frontend/src/hooks/useHistory.ts` | `useHistory` TanStack Query hook | VERIFIED | `export function useHistory` calls `fetchJson<HistoryResponse>('/history?start=...')` |
| `frontend/src/components/HistoryPage.tsx` | Full history page component | VERIFIED | 158 lines; all required sections present (header, accuracy strip, date picker, table, empty state) |
| `frontend/src/components/HistoryPage.module.css` | History page styles (min 40 lines) | VERIFIED | 180 lines; uses design tokens, includes `.container`, `.correct`, `.incorrect` |
| `frontend/src/App.tsx` | Hash-based routing | VERIFIED | `useState(window.location.hash)`, `hashchange` event listener, `isHistoryPage` conditional render |
| `frontend/src/components/AccuracyStrip.tsx` | "View History" navigation link | VERIFIED | `href="#/history"` with `.historyLink` style |
| `frontend/src/components/Header.tsx` | Title as home link | VERIFIED | `href="#/"` wrapping h1 text with `.titleLink` style |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `api/routes/history.py` | `src/pipeline/db.py` | `get_history(pool, start, end)` | WIRED | Line 90: `rows = get_history(pool, start, end)`; pool obtained from `request.app.state.pool` |
| `api/main.py` | `api/routes/history.py` | `include_router` with `/api/v1` prefix | WIRED | Line 18 import + Line 52 registration confirmed |
| `frontend/src/hooks/useHistory.ts` | `/api/v1/history` | `fetchJson` in `useQuery` | WIRED | `fetchJson<HistoryResponse>('/history?start=${startDate}&end=${endDate}')` |
| `frontend/src/App.tsx` | `frontend/src/components/HistoryPage.tsx` | hash-based conditional render | WIRED | `import { HistoryPage }` + `isHistoryPage ? <HistoryPage /> : ...` |
| `frontend/src/components/AccuracyStrip.tsx` | `#/history` | anchor tag href | WIRED | `href="#/history"` confirmed |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HIST-01 | 18-01, 18-02 | `/history` route accessible from main dashboard | SATISFIED | Route registered in `api/main.py`; `AccuracyStrip.tsx` provides "View History" link to `#/history`; `App.tsx` renders `<HistoryPage />` on hash match |
| HIST-02 | 18-02 | User can select a date range on the history page | SATISFIED | `HistoryPage.tsx` has two native `<input type="date">` controls with state-managed `startDate`/`endDate` |
| HIST-03 | 18-01, 18-02 | History page shows table of past predictions vs actual outcomes | SATISFIED | Backend returns `prediction_correct` per game; frontend renders check/X markers in table |
| HIST-04 | 18-01, 18-02 | History page shows rolling model accuracy over selected range | SATISFIED | `_compute_accuracy()` computes per-model LR/RF/XGB percentages; `HistoryPage.tsx` renders accuracy summary strip |

**Note on traceability:** `REQUIREMENTS.md` traceability table (lines 103-106) incorrectly lists HIST-01 through HIST-04 as "Phase 17". The ROADMAP (`Phase 18` entry at line 154) correctly assigns these requirements to Phase 18, and both PLANs declare them. This is a stale documentation entry — no gap in implementation.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Scanned: `api/routes/history.py`, `src/pipeline/db.py`, `api/models.py`, `api/main.py`, `tests/test_api/test_history.py`, `frontend/src/hooks/useHistory.ts`, `frontend/src/components/HistoryPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/AccuracyStrip.tsx`, `frontend/src/components/Header.tsx`. No TODO/FIXME/placeholder/stub patterns found.

---

## Human Verification Required

### 1. Date range picker interaction

**Test:** Navigate to `#/history` in browser. Change start date to a date with known completed games. Verify table updates to show those games.
**Expected:** Table refreshes showing games in the new range; accuracy percentages update to reflect only the filtered games.
**Why human:** TanStack Query re-fetch on state change requires a running browser + API.

### 2. Navigation round-trip

**Test:** Click "View History" in AccuracyStrip. Verify history page appears. Click "Back to Today" or header title. Verify main dashboard reappears with date navigator and game cards.
**Expected:** Seamless hash-based navigation with no page reload; Header always visible on both views.
**Why human:** Hash routing behavior requires a running browser.

### 3. Empty state display

**Test:** Select a date range with no completed games (e.g., far future or a gap in historical data).
**Expected:** "No completed games in this range" message displayed instead of table.
**Why human:** Requires a running API with the actual database.

---

## Test Run

```
platform win32 -- Python 3.11.9, pytest-8.1.1
tests/test_api/test_history.py -- 15 passed in 0.81s
```

```
cd frontend && npx tsc --noEmit -- 0 errors
cd frontend && npx vite build -- built in 152ms (108 modules)
```

---

## Summary

Phase 18 goal is fully achieved. All 11 observable truths are verified against the actual codebase, not just SUMMARY claims. The backend delivers a working `GET /api/v1/history` endpoint with correct SQL (post_lineup preference via ROW_NUMBER, `prediction_correct IS NOT NULL` filter, `game_logs` LEFT JOIN with `game_id::INTEGER` cast, 400 on invalid dates). The frontend delivers a complete history page with hash routing, date range picker, per-model accuracy summary, predictions table, and empty state. All 15 Python tests pass. TypeScript compiles with zero errors. Vite production build succeeds.

HIST-01 through HIST-04 are fully satisfied. The only note is a stale traceability entry in `REQUIREMENTS.md` (lists Phase 17 instead of Phase 18) — documentation only, no implementation impact.

---

_Verified: 2026-04-01T07:00:00Z_
_Verifier: Claude (gsd-verifier)_
