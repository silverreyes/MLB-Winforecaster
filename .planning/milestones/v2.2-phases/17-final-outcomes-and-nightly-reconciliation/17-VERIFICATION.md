---
phase: 17-final-outcomes-and-nightly-reconciliation
verified: 2026-03-31T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "FINAL game card renders score and outcome marker in browser"
    expected: "A completed game card shows 'Away X - Home Y' final score with a green check or red X beside it"
    why_human: "CSS rendering, visual layout, and color contrast cannot be verified programmatically"
  - test: "Nightly reconciliation job fires at 6:00 AM ET in a live scheduler"
    expected: "APScheduler CronTrigger fires nightly_reconciliation_job at 06:00 US/Eastern and reconcile_outcomes runs against yesterday's date"
    why_human: "Requires a running scheduler process; cannot fire a CronTrigger in a unit test"
---

# Phase 17: Final Outcomes and Nightly Reconciliation — Verification Report

**Phase Goal:** Final game outcomes are persisted (score, win/loss) and surfaced to users on completed game cards; a nightly reconciliation job catches any outcomes missed by the live poller.
**Verified:** 2026-03-31
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Nightly reconciliation job fills in actual_winner and prediction_correct for Final games not written by live poller | VERIFIED | `reconcile_outcomes()` in db.py: INNER JOIN game_logs on predictions WHERE actual_winner IS NULL; delegates to `write_game_outcome()` per row |
| 2 | Reconciliation is idempotent — running twice on same date returns 0 on second call | VERIFIED | `WHERE actual_winner IS NULL` guard in both `write_game_outcome` (line 197) and the SELECT query; `test_idempotent_second_run` passes |
| 3 | Postponed games (no game_logs entry) are silently skipped | VERIFIED | INNER JOIN means no game_logs row = no result row; `test_skips_postponed_no_game_logs` passes |
| 4 | Nightly job runs at 6:00 AM ET, reconciling yesterday's games | VERIFIED | `CronTrigger(hour=6, minute=0, timezone="US/Eastern")` at scheduler.py line 211; job computes `date.today() - timedelta(days=1)` |
| 5 | Completed game cards display the final score (away X - home Y) | VERIFIED | GameCard.tsx line 139–143: `game_status === 'FINAL' && game.home_final_score !== null` renders score; game_logs enrichment via `_fetch_final_scores` |
| 6 | Completed game cards display the model's ensemble win probability | VERIFIED | PredictionResponse passes through `ensemble_prob`; existing prediction body renders it for FINAL games (no regression) |
| 7 | Completed game cards display an outcome marker (check for correct, X for incorrect) | VERIFIED | GameCard.tsx lines 147–149: `'\u2713'` / `'\u2717'` with `styles.outcomeCorrect` / `styles.outcomeIncorrect` |
| 8 | Historical dates show FINAL game scores from game_logs | VERIFIED | `_fetch_final_scores(pool, date_str)` queries `game_logs WHERE game_date = %(date)s`; called unconditionally in route handler for all dates |
| 9 | API models carry actual_winner and prediction_correct from DB through to frontend | VERIFIED | PredictionResponse lines 35–36; GameResponse lines 109–110; `_build_prediction_response` passes both via `row.get()`; TypeScript types extended at types.ts lines 21–22, 85–88 |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/db.py` | `reconcile_outcomes()` function | VERIFIED | Exists at line 210; substantive SQL with VARCHAR::INTEGER cast, INNER JOIN, idempotency guard; calls `write_game_outcome()` for each row |
| `src/pipeline/scheduler.py` | `nightly_reconciliation_job` + CronTrigger registration | VERIFIED | Function at line 139; `CronTrigger(hour=6, minute=0, timezone="US/Eastern")` at line 211; `id="nightly_reconciliation"`, `misfire_grace_time=3600` at lines 213, 215 |
| `tests/test_pipeline/test_reconciliation.py` | Unit tests for reconciliation | VERIFIED | 11 tests: `TestReconcileOutcomes` (7) + `TestNightlyReconciliationJob` (4); all pass |
| `api/models.py` | GameResponse and PredictionResponse with outcome fields | VERIFIED | `home_final_score`, `away_final_score`, `actual_winner`, `prediction_correct` on GameResponse (lines 107–110); `actual_winner`, `prediction_correct` on PredictionResponse (lines 35–36) |
| `api/routes/games.py` | `_fetch_final_scores` + `build_games_response` enrichment | VERIFIED | `_fetch_final_scores` at line 169 with `FROM game_logs` and `game_id::INTEGER`; `final_scores` parameter in `build_games_response`; route handler calls at line 303 |
| `frontend/src/api/types.ts` | TypeScript types with outcome fields | VERIFIED | `home_final_score`, `away_final_score`, `actual_winner`, `prediction_correct` on both `PredictionResponse` and `GameResponse` |
| `frontend/src/components/GameCard.tsx` | Outcome row for FINAL game cards | VERIFIED | `finalRow` div with score text, `finalLabel`, and `\u2713`/`\u2717` markers conditional on `game_status === 'FINAL'` |
| `frontend/src/components/GameCard.module.css` | CSS classes for FINAL outcome row | VERIFIED | `.finalRow`, `.finalScoreText`, `.finalLabel`, `.outcomeCorrect` (`#22c55e`), `.outcomeIncorrect` (`#ef4444`) all present |
| `tests/test_api/test_games_final.py` | Unit tests for FINAL game display | VERIFIED | 9 tests: `TestFinalScoreDisplay` (4), `TestFinalPredictionDisplay` (2), `TestOutcomeMarker` (3); all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/pipeline/db.py` | `game_logs + predictions` tables | `INNER JOIN on game_logs.game_id::INTEGER = predictions.game_id` | WIRED | `gl.game_id::INTEGER` cast present at lines 223, 228; `INNER JOIN predictions p` at line 227 |
| `src/pipeline/scheduler.py` | `src/pipeline/db.py` | `from src.pipeline.db import reconcile_outcomes` | WIRED | Line 24: `from src.pipeline.db import reconcile_outcomes, write_game_outcome`; `reconcile_outcomes(pool, yesterday)` called at line 151 |
| `api/routes/games.py` | `game_logs` table | `_fetch_final_scores` SQL query | WIRED | `SELECT game_id::INTEGER AS game_id_int, home_score, away_score ... FROM game_logs WHERE game_date = %(date)s` at line 176–179 |
| `api/routes/games.py` | `api/models.py` | `GameResponse.home_final_score, away_final_score` assignment | WIRED | `game_resp.home_final_score = score_data["home_score"]` at line 251; `game_resp.away_final_score = score_data["away_score"]` at line 252 |
| `frontend/src/components/GameCard.tsx` | `frontend/src/api/types.ts` | `game.home_final_score`, `game.prediction_correct` | WIRED | GameCard.tsx references `game.home_final_score`, `game.away_final_score`, `game.prediction_correct` at lines 139–149; TypeScript types match |
| `api/routes/games.py` | `predictions` table | `_build_prediction_response` passes `actual_winner`, `prediction_correct` | WIRED | `actual_winner=row.get("actual_winner")` and `prediction_correct=row.get("prediction_correct")` at lines 132–133; SELECT * in `_fetch_predictions_for_date` includes these columns |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FINL-01 | 17-02-PLAN.md | Completed game cards display the final score | SATISFIED | `_fetch_final_scores` + `build_games_response` enrichment + GameCard finalRow; `test_final_game_has_scores` passes |
| FINL-02 | 17-02-PLAN.md | Completed game cards display the model's win probability prediction | SATISFIED | PredictionResponse `ensemble_prob` passed through; FINAL games render prediction body; `test_final_game_shows_ensemble_prob` passes |
| FINL-03 | 17-02-PLAN.md | Completed game cards display an outcome marker (check/X) | SATISFIED | GameCard renders `\u2713`/`\u2717` with `outcomeCorrect`/`outcomeIncorrect` CSS; `test_prediction_correct_true_in_response` and `test_prediction_correct_false_in_response` pass |
| FINL-04 | 17-01-PLAN.md | Nightly reconciliation job stamps Final games not written by live poller | SATISFIED | `reconcile_outcomes()` in db.py; `nightly_reconciliation_job` in scheduler at 6 AM ET; 11 tests pass covering idempotency, type cast, postponed-skip, error handling |

**Note on REQUIREMENTS.md traceability table:** Lines 99–102 assign FINL-01 through FINL-04 to "Phase 16" which appears to be a documentation error — these requirements are implemented in Phase 17 (plans 17-01 and 17-02). The implementation itself is correct; the traceability row in REQUIREMENTS.md should read "Phase 17." This is a documentation inconsistency only, not a code gap.

No orphaned FINL requirements: all four are claimed by a Phase 17 plan and verified in the codebase.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/pipeline/db.py` | 128 | `placeholders` variable name | Info | SQL parameterization syntax, not a stub — false positive on keyword scan |

No blocking or warning anti-patterns found. No TODO/FIXME/PLACEHOLDER comments, no empty implementations, no stub returns in Phase 17 modified files.

---

### Human Verification Required

#### 1. FINAL Game Card Visual Rendering

**Test:** Navigate to any historical date that has FINAL games (e.g., a past MLB game date). Verify that completed game cards show the final score in "Away X - Home Y" format, with a "Final" label, and a green check mark or red X depending on prediction correctness.
**Expected:** Score row visible on FINAL cards; check mark is green (#22c55e), X is red (#ef4444); layout mirrors the LIVE scoreRow; no visual overflow or misalignment.
**Why human:** CSS layout, color rendering, and visual alignment cannot be verified programmatically.

#### 2. Nightly Reconciliation CronTrigger Firing

**Test:** Start the scheduler and observe logs at 6:00 AM ET. Confirm the `nightly_reconciliation_job` fires and logs either "X prediction rows updated" or "no unreconciled games."
**Expected:** Job fires at 06:00 US/Eastern; reconciles any missed outcomes; does not crash scheduler on DB error.
**Why human:** Requires a live scheduler process and a real PostgreSQL database; CronTrigger timing cannot be verified with unit tests.

---

### Gaps Summary

No gaps. All must-haves verified. Both plans (17-01 nightly reconciliation and 17-02 FINAL game outcome display) are fully implemented, wired, and tested.

Pre-existing test failures in `test_feature_builder.py::test_rolling_ops` and `test_leakage.py` (3 tests) were documented in `deferred-items.md` before Phase 17 began and are confirmed unrelated to Phase 17 changes. The 288 tests directly covering Phase 17 and adjacent layers all pass.

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
