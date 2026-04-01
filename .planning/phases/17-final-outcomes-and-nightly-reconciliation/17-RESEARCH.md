# Phase 17: Final Outcomes & Nightly Reconciliation - Research

**Researched:** 2026-03-31
**Domain:** Backend reconciliation + frontend outcome display
**Confidence:** HIGH

## Summary

Phase 17 has two distinct workstreams: (1) a backend nightly reconciliation job that catches any Final games whose outcomes were not written by the live poller (Phase 15), and (2) frontend changes to display final scores, the model's prediction, and a correctness marker on completed game cards.

The backend side is straightforward. The existing `write_game_outcome()` function in `db.py` already handles the outcome write logic (actual_winner, prediction_correct, reconciled_at) and is idempotent via `WHERE actual_winner IS NULL`. The reconciliation job needs to query game_logs for Final games on a target date, cross-reference against predictions rows missing actual_winner, and call `write_game_outcome()` for each. The job should be registered as a CronTrigger in scheduler.py to run nightly (e.g., 6:00 AM ET), after even the latest West Coast games have finished.

The frontend side requires surfacing outcome data that already flows through the existing `/games/{date}` endpoint. Currently, `_fetch_predictions_for_date()` uses `SELECT *` which already includes the `actual_winner` and `prediction_correct` columns -- but these fields are not yet exposed in `PredictionResponse` or the TypeScript types. The GameCard needs a new "outcome row" for FINAL games showing final score, the ensemble probability, and a check/X marker.

**Primary recommendation:** Implement as 2 plans: (1) Backend reconciliation function + nightly cron job + tests; (2) API model additions + frontend outcome display on FINAL cards.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FINL-01 | Completed game cards display the final score | GameResponse already carries game_status='FINAL'; need to add score data from game_logs to the /games/{date} response for FINAL games |
| FINL-02 | Completed game cards display the model's win probability prediction | PredictionResponse already carries ensemble_prob; just needs to be visually surfaced on FINAL cards (currently hidden behind same layout as PRE_GAME) |
| FINL-03 | Completed game cards display an outcome marker indicating whether the model called it correctly | prediction_correct column exists in DB; needs to be added to PredictionResponse and TypeScript types, then rendered as check/X |
| FINL-04 | A nightly reconciliation job stamps any Final games not yet written by the live poller | Existing write_game_outcome() is idempotent; need reconcile_outcomes() function + CronTrigger in scheduler.py |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg / psycopg_pool | 3.x (existing) | DB writes for reconciliation | Already in use throughout db.py |
| APScheduler | 3.x (existing) | Nightly cron trigger for reconciliation | Already configures all scheduled jobs in scheduler.py |
| statsapi | existing | Fetch schedule data for reconciliation | Already used by live_poller_job and sync_game_logs |
| FastAPI / Pydantic | existing | API model updates | Already used for all response models |
| React + CSS Modules | existing | Frontend outcome display | Project-wide frontend pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Unit tests for reconciliation | Test reconciliation logic without real DB |
| unittest.mock | stdlib | Mock pool, API, and DB functions | All unit tests in this phase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler CronTrigger | systemd timer / cron | APScheduler already manages all jobs; adding external cron creates a split-brain scheduler problem |
| game_logs join for scores | MLB API re-fetch for scores | game_logs already has final scores; no need for additional API calls |

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
  db.py                    # Add reconcile_outcomes() function
  scheduler.py             # Add nightly_reconciliation_job() + CronTrigger
api/
  models.py                # Add outcome fields to PredictionResponse + GameResponse
  routes/games.py          # Populate score/outcome fields for FINAL games
frontend/src/
  api/types.ts             # Add outcome fields to TypeScript types
  components/GameCard.tsx   # Add outcome row for FINAL cards
  components/GameCard.module.css  # Outcome row styles
```

### Pattern 1: Reconciliation via game_logs Cross-Reference
**What:** Query game_logs for all Final games on a date range, join against predictions where actual_winner IS NULL, and call write_game_outcome() for each unreconciled game.
**When to use:** Nightly reconciliation job.
**Example:**
```python
def reconcile_outcomes(pool: ConnectionPool, target_date: str) -> int:
    """Reconcile unwritten outcomes for Final games on a given date.

    Queries game_logs for completed games, cross-references against
    predictions missing actual_winner, writes outcomes via
    write_game_outcome(). Idempotent -- safe to re-run.

    Returns total prediction rows updated.
    """
    # Step 1: Find game_ids with predictions but no actual_winner
    sql = """
        SELECT DISTINCT p.game_id
        FROM predictions p
        WHERE p.game_date = %(date)s
          AND p.actual_winner IS NULL
          AND p.game_id IS NOT NULL
    """
    # Step 2: For each, look up final score in game_logs
    # CRITICAL: game_logs.game_id is VARCHAR, predictions.game_id is INTEGER
    # Must cast: game_logs.game_id = p.game_id::TEXT
    # OR: Join via p.game_id::TEXT = gl.game_id

    # Step 3: Call write_game_outcome() for each match
```

### Pattern 2: Final Score Display via game_logs Enrichment
**What:** When building the /games/{date} response for historical/FINAL games, enrich GameResponse with final score data from game_logs.
**When to use:** Any time a FINAL game card is rendered.
**Example:**
```python
# In build_games_response(), for FINAL games:
# Option A: Add final_score fields to GameResponse model
# Option B: Reuse live_score fields (away_score, home_score) for FINAL games too
```

### Pattern 3: Outcome Marker on Frontend
**What:** A check mark (correct) or X mark (incorrect) displayed on FINAL game cards alongside the ensemble probability.
**When to use:** When game_status === 'FINAL' and prediction_correct is not null.
**Example:**
```tsx
// In GameCard.tsx, for FINAL games with outcome data:
{game_status === 'FINAL' && primary?.prediction_correct !== null && (
  <div className={styles.outcomeRow}>
    <span className={primary.prediction_correct ? styles.correct : styles.incorrect}>
      {primary.prediction_correct ? '\u2713' : '\u2717'}
    </span>
    <span>Model: {formatProb(primary.ensemble_prob)}</span>
  </div>
)}
```

### Anti-Patterns to Avoid
- **Re-fetching MLB API for final scores:** game_logs already has all Final game scores. The reconciliation job should NOT call statsapi; it should query game_logs directly.
- **Reconciling only is_latest=TRUE rows:** Per STATE.md carry-forward: "Reconciliation must target ALL prediction rows for a game_id, not just is_latest = TRUE." The existing write_game_outcome() already does this correctly.
- **Including reconciliation columns in pipeline UPSERT:** The `_PREDICTION_UPDATE_COLS` deliberately excludes actual_winner, prediction_correct, reconciled_at. This is correct and must not change.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Outcome write logic | Custom SQL per call site | Existing `write_game_outcome()` in db.py | Already handles actual_winner computation, prediction_correct calculation, idempotency (WHERE actual_winner IS NULL), and targets ALL prediction rows for a game_id |
| Final score lookup | MLB API re-fetch | game_logs table query | game_logs already has home_score/away_score for all Final games; querying it avoids API rate limits and latency |
| Job scheduling | OS-level cron or systemd timer | APScheduler CronTrigger in scheduler.py | All other jobs already use APScheduler; consistency and single-process management |
| Score display layout | New component hierarchy | Extend existing GameCard score display | FINAL score follows same visual pattern as LIVE score but without expand/collapse |

**Key insight:** Nearly all the backend infrastructure for Phase 17 already exists. `write_game_outcome()` handles the hard part (actual_winner computation, prediction_correct via ensemble probability, idempotency). `game_logs` has all the scores. The reconciliation job is just glue code connecting these two existing pieces.

## Common Pitfalls

### Pitfall 1: game_id Type Mismatch Between Tables
**What goes wrong:** game_logs.game_id is VARCHAR; predictions.game_id is INTEGER. A naive JOIN fails or produces no matches.
**Why it happens:** Phase 13 added game_id as INTEGER to predictions; Phase 16 created game_logs with VARCHAR game_id (because statsapi returns string game_ids).
**How to avoid:** Always cast when joining: `game_logs.game_id::INTEGER = predictions.game_id` OR `predictions.game_id::TEXT = game_logs.game_id`. This is documented in STATE.md carry-forward decisions.
**Warning signs:** Reconciliation job reports 0 rows updated despite Final games existing.

### Pitfall 2: Reconciliation Running Before Games Finish
**What goes wrong:** If the nightly job runs too early (e.g., 11 PM ET), West Coast games may still be in progress.
**Why it happens:** West Coast late games can end past midnight ET.
**How to avoid:** Schedule the reconciliation job for 6:00 AM ET or later, when all games from the previous day are guaranteed Final. The job should reconcile yesterday's games, not today's.
**Warning signs:** Games missing outcomes that were actually Final by the time the dashboard is checked the next morning.

### Pitfall 3: Postponed Games Causing False Reconciliation Attempts
**What goes wrong:** Postponed games have no scores in game_logs but may have prediction rows. Attempting to reconcile them would produce incorrect results.
**Why it happens:** The reconciliation logic finds predictions without actual_winner and tries to write outcomes for every one.
**How to avoid:** Only reconcile game_ids that exist in game_logs (which only contains Final regular-season games). A LEFT JOIN from predictions to game_logs, filtering to WHERE game_logs.game_id IS NOT NULL, naturally excludes postponed games.
**Warning signs:** Errors or incorrect outcomes for postponed games.

### Pitfall 4: Prediction Rows Without game_id
**What goes wrong:** Early predictions (before Phase 13 migration backfilled game_id) may have game_id = NULL. These can never be reconciled by game_id.
**Why it happens:** Legacy prediction rows pre-dating the Phase 13 migration.
**How to avoid:** The reconciliation query filters on `game_id IS NOT NULL`. Rows without game_id are unreachable by design -- this is acceptable because very early rows have no matching game context anyway.
**Warning signs:** Non-zero count of never-reconciled predictions for dates where all games are Final.

### Pitfall 5: Frontend Score Display Missing for Historical Dates
**What goes wrong:** Users browsing historical dates see FINAL game cards but no scores, because the /games/{date} response doesn't include score data for FINAL games.
**Why it happens:** The current live_score field is only populated for LIVE games in the 'live' view_mode. FINAL games in 'historical' view_mode get no score enrichment.
**How to avoid:** For FINAL games, enrich GameResponse with final score data. Two approaches: (A) add new fields (home_final_score, away_final_score) to GameResponse, or (B) query game_logs in build_games_response and populate new dedicated fields. Option (A) is cleaner because it keeps the live_score model strictly for in-progress data.
**Warning signs:** FINAL game cards render without any score information.

## Code Examples

### Existing write_game_outcome (db.py -- already implemented)
```python
# Source: src/pipeline/db.py lines 169-207
def write_game_outcome(pool, game_id, home_team, away_team, home_score, away_score) -> int:
    actual_winner = home_team if home_score > away_score else away_team
    sql = """
        UPDATE predictions
        SET actual_winner = %(actual_winner)s,
            prediction_correct = (...),
            reconciled_at = %(reconciled_at)s
        WHERE game_id = %(game_id)s
          AND actual_winner IS NULL
    """
    # Returns count of rows updated. Idempotent -- skips already-reconciled rows.
```

### Reconciliation Function Pattern
```python
def reconcile_outcomes(pool: ConnectionPool, target_date: str) -> int:
    """Reconcile outcomes for all Final games on target_date.

    Joins predictions (WHERE actual_winner IS NULL) against game_logs
    (which only contains Final games) to find unreconciled game_ids,
    then calls write_game_outcome() for each.
    """
    sql = """
        SELECT DISTINCT gl.game_id::INTEGER AS game_id_int,
               gl.home_team, gl.away_team,
               gl.home_score, gl.away_score
        FROM game_logs gl
        INNER JOIN predictions p
            ON p.game_id = gl.game_id::INTEGER
        WHERE gl.game_date = %(date)s
          AND p.actual_winner IS NULL
          AND p.game_id IS NOT NULL
    """
    # For each row, call write_game_outcome(pool, game_id_int, ...)
```

### Nightly Job Registration Pattern
```python
# In scheduler.py create_scheduler():
scheduler.add_job(
    nightly_reconciliation_job,
    CronTrigger(hour=6, minute=0, timezone="US/Eastern"),
    args=[pool],
    id="nightly_reconciliation",
    name="Nightly outcome reconciliation (6am ET)",
    misfire_grace_time=3600,  # Allow 1-hour grace for missed fires
)
```

### GameResponse Model Extension
```python
# In api/models.py -- add outcome fields to GameResponse:
class GameResponse(BaseModel):
    # ...existing fields...
    home_final_score: int | None = None
    away_final_score: int | None = None
    actual_winner: str | None = None
    prediction_correct: bool | None = None
```

### TypeScript Types Extension
```typescript
// In frontend/src/api/types.ts -- extend GameResponse:
export interface GameResponse {
  // ...existing fields...
  home_final_score: number | null;
  away_final_score: number | null;
  actual_winner: string | null;
  prediction_correct: boolean | null;
}
```

### Frontend Outcome Row Pattern
```tsx
// In GameCard.tsx -- outcome display for FINAL games:
{game_status === 'FINAL' && game.home_final_score !== null && (
  <div className={styles.outcomeRow}>
    <div className={styles.finalScore}>
      {away_team} {game.away_final_score} - {home_team} {game.home_final_score}
    </div>
    {game.prediction_correct !== null && (
      <span className={game.prediction_correct ? styles.correct : styles.incorrect}>
        {game.prediction_correct ? '\u2713' : '\u2717'}
      </span>
    )}
  </div>
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No outcome tracking | Live poller writes outcomes on FINAL transition | Phase 15 (2026-03-31) | Most outcomes written in real-time; nightly job is safety net only |
| No game_logs table | game_logs stores all Final game scores | Phase 16 (2026-04-01) | Reconciliation can query scores locally instead of re-fetching from API |
| No game_id on predictions | game_id column on predictions table | Phase 13 (2026-03-31) | Enables reliable game-level joins for reconciliation |

**Key insight:** The infrastructure built in Phases 13, 15, and 16 means Phase 17 is largely assembly work, not new infrastructure.

## Open Questions

1. **Should the reconciliation job reconcile multiple dates or just yesterday?**
   - What we know: The live poller covers today's games. Late West Coast games could finish past midnight ET.
   - What's unclear: Should the nightly job sweep the last N days to catch any stragglers?
   - Recommendation: Reconcile yesterday's date by default, with an optional parameter for sweeping a range (useful for recovery after extended poller downtime). Keeping it to yesterday keeps the query small and fast.

2. **How should FINAL game scores reach the frontend for historical dates?**
   - What we know: For today's LIVE games, scores come from the linescore cache. For historical dates, game_logs has the scores.
   - What's unclear: Should we query game_logs in the /games/{date} route, or should we add score columns to the predictions table?
   - Recommendation: Query game_logs in build_games_response() for FINAL games. This avoids schema changes to predictions and leverages the existing game_logs data source. The join can use the game_id match.

3. **Where should outcome data (prediction_correct) be surfaced on the card?**
   - What we know: The card already has a score row layout (from LIVE games) and a prediction body.
   - What's unclear: Should the outcome marker appear in the score row, the prediction body, or a new section?
   - Recommendation: Add a new "outcome row" between the score display and the prediction body, similar in visual weight to the LIVE score row but with a different background color. The check/X marker should be prominent. Alternatively, add the check/X inline next to the ensemble probability in the prediction column.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_pipeline/test_reconciliation.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FINL-01 | FINAL game cards display final score | unit | `python -m pytest tests/test_api/test_games_final.py::TestFinalScoreDisplay -x` | No -- Wave 0 |
| FINL-02 | FINAL game cards display model win probability | unit | `python -m pytest tests/test_api/test_games_final.py::TestFinalPredictionDisplay -x` | No -- Wave 0 |
| FINL-03 | FINAL game cards display outcome marker (check/X) | unit | `python -m pytest tests/test_api/test_games_final.py::TestOutcomeMarker -x` | No -- Wave 0 |
| FINL-04 | Nightly reconciliation stamps Final games not written by poller | unit | `python -m pytest tests/test_pipeline/test_reconciliation.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_pipeline/test_reconciliation.py tests/test_api/test_games_final.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline/test_reconciliation.py` -- covers FINL-04 (reconcile_outcomes function, nightly job, idempotency)
- [ ] `tests/test_api/test_games_final.py` -- covers FINL-01, FINL-02, FINL-03 (GameResponse with final scores, outcome marker)

## Sources

### Primary (HIGH confidence)
- `src/pipeline/db.py` -- Existing write_game_outcome() implementation, prediction columns, game_logs CRUD
- `src/pipeline/scheduler.py` -- Existing live_poller_job and APScheduler CronTrigger patterns
- `src/pipeline/migration_001.sql` -- Schema: actual_winner, prediction_correct, reconciled_at columns
- `src/pipeline/migration_002.sql` -- Schema: game_logs table with home_score, away_score
- `api/models.py` -- Existing Pydantic response models
- `api/routes/games.py` -- Existing build_games_response() and _fetch_predictions_for_date()
- `frontend/src/components/GameCard.tsx` -- Existing card layout with LIVE score row pattern
- `frontend/src/api/types.ts` -- Existing TypeScript types
- `.planning/STATE.md` -- Carry-forward decisions (game_id type mismatch, reconciliation targets all rows)

### Secondary (MEDIUM confidence)
- `.planning/phases/15-live-score-polling/15-UI-SPEC.md` -- Visual patterns for score display that Phase 17 extends

### Tertiary (LOW confidence)
- None -- all findings sourced from codebase inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies needed
- Architecture: HIGH -- pattern is direct extension of existing Phase 15 live poller + Phase 16 game_logs
- Pitfalls: HIGH -- type mismatch documented in STATE.md; other pitfalls identified from codebase analysis

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable -- no external dependencies changing)
