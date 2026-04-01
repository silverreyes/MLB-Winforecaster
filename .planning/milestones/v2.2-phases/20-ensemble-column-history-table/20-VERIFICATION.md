---
phase: 20-ensemble-column-history-table
verified: 2026-04-01T14:15:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
---

# Phase 20: Ensemble Column in History Table — Verification Report

**Phase Goal:** Add ensemble_prob column to the history table to close the HIST-03 partial gap from the v2.2 milestone audit.
**Verified:** 2026-04-01T14:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | History page table displays an Ensemble% column showing the mean of LR/RF/XGB probabilities for each game | VERIFIED | `HistoryPage.tsx` line 126: `<th className={styles.thNum}>Ens%</th>`; line 143: `<td className={styles.tdNum}>{formatProb(g.ensemble_prob)}</td>` |
| 2 | Ensemble% column appears between XGB% and the outcome checkmark column | VERIFIED | Column ordering in `thead`/`tbody`: XGB% at line 125/142, Ens% at line 126/143, outcome at line 127/144 |
| 3 | API /history response includes ensemble_prob field in each game row | VERIFIED | `HistoryRow` Pydantic model (models.py line 137) and TypeScript interface (types.ts line 108) both declare `ensemble_prob`; route passes `ensemble_prob=r.get("ensemble_prob")` (routes/history.py line 108); SQL computes column in CTE |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Provides | Status | Evidence |
|----------|----------|--------|----------|
| `api/models.py` | HistoryRow with ensemble_prob field | VERIFIED | Line 137: `ensemble_prob: float \| None = None` — placed after `xgb_prob`, before `prediction_correct` |
| `src/pipeline/db.py` | get_history SQL computing ensemble_prob | VERIFIED | Lines 525-528: CASE/ROUND CTE expression; line 546: `r.ensemble_prob` in outer SELECT; docstring updated (line 518) |
| `api/routes/history.py` | Route handler passing ensemble_prob to HistoryRow | VERIFIED | Line 108: `ensemble_prob=r.get("ensemble_prob")`; `_compute_accuracy` includes `"ensemble"` key (line 33) with correct/total tracking (lines 60-62) |
| `frontend/src/api/types.ts` | TypeScript HistoryRow interface with ensemble_prob | VERIFIED | Line 108: `ensemble_prob: number \| null;` |
| `frontend/src/components/HistoryPage.tsx` | Ensemble% table column rendering | VERIFIED | Header "Ens%" at line 126; cell `formatProb(g.ensemble_prob)` at line 143; accuracy strip maps over `['lr', 'rf', 'xgb', 'ensemble']` at line 63 with `ENS` label at line 65 |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `src/pipeline/db.py` | `api/routes/history.py` | `get_history` returns dict with `ensemble_prob` key | WIRED | SQL CTE `AS ensemble_prob` (db.py line 528); docstring return key list includes `ensemble_prob` (line 518); route calls `r.get("ensemble_prob")` |
| `api/routes/history.py` | `api/models.py` | HistoryRow constructor receives ensemble_prob | WIRED | `ensemble_prob=r.get("ensemble_prob")` (history.py line 108) matches `ensemble_prob: float \| None = None` in HistoryRow (models.py line 137) |
| `frontend/src/api/types.ts` | `frontend/src/components/HistoryPage.tsx` | `HistoryRow.ensemble_prob` rendered in table cell | WIRED | `g.ensemble_prob` at HistoryPage.tsx line 143; type `HistoryRow` imported via `useHistory` hook which uses `HistoryResponse` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HIST-03 | 20-01-PLAN.md | History page shows a table of past predictions vs actual outcomes within the selected range (including ensemble probability column) | SATISFIED | Ensemble% column rendered in HistoryPage.tsx; ensemble_prob in API response; REQUIREMENTS.md line 127 marks as Complete for Phase 20 |

No orphaned requirements: REQUIREMENTS.md maps HIST-03 to Phase 20, matching the plan's `requirements: [HIST-03]`.

---

### Test Coverage

| Test | Status | Evidence |
|------|--------|----------|
| All 16 history tests | PASSING | `python -m pytest tests/test_api/test_history.py -x -v` → 16 passed in 0.89s |
| `test_sql_computes_ensemble_prob` | PASSING | Verifies `AS ensemble_prob` in generated SQL |
| `test_history_row_validates_all_fields` | PASSING | Asserts `row.ensemble_prob == 0.5767` |
| `test_route_returns_valid_response` | PASSING | Asserts `data["games"][0]["ensemble_prob"] == 0.5767` |
| `test_route_empty_history` | PASSING | Checks `"ensemble"` key in accuracy dict |
| `test_empty_rows_returns_zero_totals` | PASSING | Iterates `("lr", "rf", "xgb", "ensemble")` |
| TypeScript compilation | PASSING | `npx tsc --noEmit` from `frontend/` exits 0 (no output) |

---

### Commit Verification

| Hash | Description | Status |
|------|-------------|--------|
| `8da9a24` | feat(20-01): add ensemble_prob to history backend (SQL, model, route, tests) | VERIFIED in git log |
| `10fa489` | feat(20-01): add Ensemble% column to history frontend and accuracy strip | VERIFIED in git log |
| `4d8eb49` | docs(20-01): complete ensemble column in history table plan | VERIFIED in git log |

---

### Anti-Patterns Found

None. The single match on "placeholder" in db.py line 128 is a Python variable name (`placeholders`) used for SQL parameterization — unrelated to this phase and not a stub pattern.

---

### Human Verification Required

One item benefits from manual inspection, though automated checks pass:

**Test: Ensemble% column visual placement and ENS accuracy strip**
- **Test:** Load the history page in a browser and verify (a) Ens% column appears between XGB% and the checkmark column, and (b) the accuracy strip shows "ENS: XX.X% (N/M)" alongside LR, RF, XGB entries.
- **Expected:** Four accuracy entries visible; Ens% column properly aligned under the header with formatted percentages.
- **Why human:** Column ordering and CSS alignment cannot be verified programmatically; React rendering requires a browser.

---

### Summary

Phase 20 fully achieves its goal. All five backend and frontend artifacts exist, are substantive (not stubs), and are correctly wired end-to-end:

- The SQL CTE computes `ensemble_prob` via `ROUND(((lr + rf + xgb) / 3.0)::numeric, 4)` with a NULL guard.
- The Pydantic `HistoryRow` carries the field through the API serialization boundary.
- The route handler passes `r.get("ensemble_prob")` from the DB dict to the model constructor.
- The TypeScript `HistoryRow` interface declares `ensemble_prob: number | null`.
- `HistoryPage.tsx` renders it as `formatProb(g.ensemble_prob)` under the `Ens%` header in the correct column position.
- The accuracy strip extends to four models (`lr`, `rf`, `xgb`, `ensemble`) with `ENS` label.
- All 16 history tests pass, TypeScript compiles cleanly, and all three task commits are present in git history.

HIST-03 is fully closed.

---

_Verified: 2026-04-01T14:15:00Z_
_Verifier: Claude (gsd-verifier)_
