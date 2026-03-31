# Pitfalls Research

**Domain:** Adding game lifecycle features (live scores, outcome reconciliation, date navigation) to an existing MLB win probability dashboard
**Researched:** 2026-03-30
**Confidence:** HIGH (pitfalls derived from direct codebase analysis + MLB Stats API documentation + PostgreSQL concurrency literature)

---

## Critical Pitfalls

### Pitfall 1: Doubleheader Collision on Prediction Unique Constraint

**What goes wrong:**
The predictions table unique constraint is `(game_date, home_team, away_team, prediction_version, is_latest)`. When the same two teams play a doubleheader (same date, same home/away), the second game's prediction UPSERT silently overwrites the first game's prediction. The reconciliation step then writes `actual_winner` for game 2 but game 1's outcome is lost. The history page reports incorrect accuracy because half the doubleheader data is destroyed.

**Why it happens:**
The original schema was designed for a single-game-per-matchup-per-day model, which is correct for ~95% of the season. Doubleheaders are scheduled only ~10-15 times per season (split or straight), so the bug never appears in early-season testing. The `game_id` (gamePk) field exists in the `games` table but is NOT part of the predictions table or its unique constraint.

**How to avoid:**
Add `game_id INTEGER` (the MLB `gamePk`) to the predictions table as a new column. Modify the unique constraint to include it: `UNIQUE (game_date, home_team, away_team, prediction_version, is_latest, game_id)`. This is an additive-only schema change (new column, new constraint name). The pipeline already has `game_id` in the game dict from `LiveFeatureBuilder.get_today_games()` -- it just is not passed through to `insert_prediction()`. The schedule endpoint provides `game_num` (1 or 2) and `doubleheader` ('Y'/'S'/'N') fields as well.

**Warning signs:**
- Two prediction rows for the same matchup on the same date where one has suspiciously different SP assignments
- Accuracy calculations that show impossible results on doubleheader days
- `INSERT ... ON CONFLICT` rowcount returning 0 unexpectedly during game 2 of a doubleheader

**Phase to address:**
Schema migration phase (before live polling or reconciliation are added). This must be the FIRST schema change because all downstream features (live score writes, reconciliation, history) depend on being able to uniquely identify a prediction for a specific game.

---

### Pitfall 2: Status Filter Bug Cascade -- Hiding Games Also Hides Their Reconciliation

**What goes wrong:**
The current system fetches predictions from Postgres with `WHERE game_date = CURRENT_DATE AND is_latest = TRUE`. The frontend groups predictions by `(home_team, away_team)`. If the status filter bug is "fixed" by simply showing all statuses but the `is_latest` flag handling is not updated, two problems emerge: (1) games that were re-predicted by the confirmation run at 5pm ET may show stale pre_lineup data alongside fresh confirmation data, and (2) the `actual_winner` and `prediction_correct` columns (once added) will only be populated on rows where `is_latest = TRUE`, so if `is_latest` was toggled incorrectly during the confirmation run's `mark_not_latest()` call, the reconciled outcome becomes invisible.

**Why it happens:**
The existing `mark_not_latest()` function sets `is_latest = FALSE` on old prediction_version rows when an SP change is detected. But the new reconciliation writer will write `actual_winner` to the `is_latest = TRUE` row. If the pipeline's confirmation run fires AFTER the poller already wrote `actual_winner` to the post_lineup row, and then `mark_not_latest()` flips that row to `is_latest = FALSE`, the reconciled outcome disappears from the API response.

**How to avoid:**
1. Reconciliation writes (`actual_winner`, `prediction_correct`) should target ALL prediction rows for a game (all versions), not just `is_latest = TRUE` rows. Use `WHERE game_date = X AND home_team = Y AND away_team = Z AND game_id = G` without filtering on `is_latest`.
2. The frontend should display outcome data from ANY version row that has it, even if `is_latest = FALSE`.
3. The API endpoint for date-specific predictions should return reconciliation columns from all rows, not just latest.

**Warning signs:**
- Games showing predictions but no outcome marker even though the game is Final
- `prediction_correct` column being NULL on rows where `actual_winner` is populated on a sibling row
- Dashboard showing "awaiting result" on games that finished hours ago

**Phase to address:**
Status filter fix phase AND reconciliation phase. The filter fix must account for the reconciliation data flow, so these two concerns should be designed together even if implemented in separate milestones.

---

### Pitfall 3: UTC/ET Date Boundary Mismatch Between Postgres and Pipeline

**What goes wrong:**
The Postgres Docker container runs in UTC (default for `postgres:16-bookworm`). `CURRENT_DATE` in SQL returns the UTC date. The Python worker container also has no `TZ` set, so `date.today()` returns UTC date. APScheduler cron triggers use `US/Eastern`. During the crossover period (midnight UTC = 8pm ET in winter / 7pm ET in summer), a West Coast game starting at 7:10pm PT (10:10pm ET = 2:10am UTC next day) would exhibit a mismatch: the pipeline stored `game_date` as the UTC date when the 5pm ET run fires at 9pm UTC (still the same UTC day). But a live poller running at 1am UTC (9pm PT, same ET evening) would call `date.today()` and get the NEXT UTC day, creating a lookup failure.

The `/predictions/today` endpoint uses `CURRENT_DATE` in Postgres (UTC), so after midnight UTC (~8pm ET), it returns zero games because `CURRENT_DATE` has rolled over but `game_date` was stored as the earlier UTC date.

**Why it happens:**
The existing system avoids this because it only runs at 10am/1pm/5pm ET -- all comfortably within the same UTC day. A live poller running at 90-second intervals through midnight UTC will cross the boundary. No `TZ` environment variable is set in the Dockerfile or docker-compose.yml; only `tzdata` is installed.

**How to avoid:**
1. Standardize on the MLB API's `officialDate` field for all date storage. The MLB API assigns each game an official date that does not change regardless of when the game actually finishes.
2. For the `/predictions/today` endpoint, compute the ET date server-side rather than using `CURRENT_DATE`:
   ```python
   from zoneinfo import ZoneInfo
   today_et = datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
   ```
3. Set `TZ=America/New_York` on the worker and API containers so `date.today()` and `CURRENT_DATE` match ET. Simpler but less precise than using `officialDate`.
4. For date navigation, the API should accept explicit dates from the client, never relying on `CURRENT_DATE`.

**Warning signs:**
- Predictions or live scores disappearing after ~8pm ET
- `/predictions/today` returning empty during late West Coast games
- Nightly reconciliation job failing to find rows for games it knows finished

**Phase to address:**
Date navigation phase. Must be resolved before any polling or reconciliation feature is built, because both depend on correct date lookups.

---

### Pitfall 4: Live Poller and Pipeline Runner Race Condition on Postgres Writes

**What goes wrong:**
The 90-second live poller detects a game going Final and writes `actual_winner = 'NYY'` and `prediction_correct = TRUE` to the predictions row. Seconds later, the 5pm confirmation pipeline run fires, re-runs the prediction for that game, and does an `INSERT ... ON CONFLICT DO UPDATE SET prediction_status = ..., created_at = NOW()`. If `actual_winner` was added to `_PREDICTION_UPDATE_COLS` (for "completeness"), the UPSERT overwrites it with NULL. Even if not, the `created_at = NOW()` reset makes the row look freshly written, confusing "reconcile rows older than X" logic.

**Why it happens:**
The existing UPSERT in `db.py` explicitly lists `_PREDICTION_UPDATE_COLS`. Adding reconciliation columns to the table creates a latent race unless they are carefully excluded from the UPSERT's update list. The confirmation run at 5pm ET overlaps with when early-start games (1pm ET) go Final.

**How to avoid:**
1. Explicitly exclude `actual_winner`, `prediction_correct`, and `reconciled_at` from `_PREDICTION_UPDATE_COLS` in db.py. Document this with a comment.
2. Use a separate, dedicated function for reconciliation writes: `reconcile_prediction(pool, game_id, actual_winner)` using `UPDATE ... SET actual_winner = X, prediction_correct = Y, reconciled_at = NOW() WHERE game_id = Z AND actual_winner IS NULL`. The `WHERE actual_winner IS NULL` guard prevents re-reconciliation and makes the operation idempotent.
3. The pipeline should skip games whose status is any terminal state -- no value in re-predicting a completed game.

**Warning signs:**
- `reconciled_at` being set but `actual_winner` being NULL (write-then-overwrite)
- Nightly reconciliation finding games it already reconciled as "un-reconciled"
- Inconsistent `prediction_correct` values between prediction versions for the same game

**Phase to address:**
Reconciliation phase (write function design). Must be designed before the live poller is implemented.

---

### Pitfall 5: APScheduler max_instances Collision Between Poller and Pipeline Jobs

**What goes wrong:**
APScheduler 3.x applies `max_instances` at the **function** level, not the job ID level. If the 90-second interval poller and the three cron pipeline jobs all call `run_pipeline()` or share any common callable, APScheduler skips the poller execution when a pipeline cron job is running (or vice versa), because the default `max_instances=1`. Live score updates freeze for the duration of the pipeline run (~2-5 minutes).

**Why it happens:**
APScheduler counts running instances per callable, not per job ID. Even if poller and pipeline have different job IDs, sharing a callable triggers the limit. Additionally, BlockingScheduler's default ThreadPoolExecutor has only 10 threads. If the pipeline occupies threads processing 15 games, the poller cannot acquire a thread.

**How to avoid:**
1. The live poller MUST be a completely separate function from `run_pipeline()` with a distinct callable (e.g., `poll_live_scores()`).
2. Set `max_instances=1` on each job explicitly. Different callables will not collide.
3. Use `misfire_grace_time=90` on the poller (equal to the interval) so missed polls are silently skipped rather than queuing up.
4. Consider increasing the connection pool `max_size` from 10 to 15 in the worker, or creating a separate pool (size 2) for the poller.

**Warning signs:**
- Log: "Execution of job skipped: maximum number of running instances reached (1)"
- Live scores freezing at exactly 10am, 1pm, or 5pm ET for several minutes
- Poller missing Final transitions during pipeline windows

**Phase to address:**
Live polling phase. Must be considered when adding the interval job to the existing scheduler.

---

### Pitfall 6: MLB Stats API Game Status Zoo -- 127 Statuses, Not Just "Final"

**What goes wrong:**
The poller checks `status == "Final"` to trigger reconciliation. But the MLB Stats API has **127 distinct game statuses** (verified via `https://statsapi.mlb.com/api/v1/gameStatus`). A game can be "Final: Rain" (FR), "Game Over: Rain" (OR), "Completed Early: Mercy" (OM), "Final: Tied" (FT), or "Forfeit" (Q/R-prefix). Each needs reconciliation, but string-matching on `"Final"` misses them. Worse, "Suspended: Rain" (TR) means the game is NOT final -- it resumes on a future date. Writing `actual_winner` for a suspended game is incorrect.

**Why it happens:**
Developers test against `"Final"` because it is the most common terminal status. The `statsapi` Python wrapper returns `detailedState` in its `status` field, not `abstractGameState`. The full taxonomy is available only from the `/api/v1/gameStatus` meta endpoint.

**How to avoid:**
1. Use `abstractGameState` from the raw API. The abstract states are: `Preview`, `Live`, `Final`. A game with `abstractGameState == "Final"` is definitively over regardless of detailed reason.
2. If using `statsapi` wrapper, call `statsapi.get("game", {"gamePk": id})` to access raw JSON and extract `abstractGameState`, or build an allowlist (54 "Final" abstract-state status codes use F, O, Q, or R prefixes).
3. For **suspended** games (T/U prefixes): do NOT write `actual_winner`. Track as suspended; let nightly reconciliation check later.
4. For **postponed** games (D prefix): do NOT write `actual_winner`. The game gets a new `gamePk` on its rescheduled date. The original prediction is orphaned. Show as "Postponed" in history, not "Incorrect".

**Warning signs:**
- Games stuck as "In Progress" after they ended (rain-shortened)
- `actual_winner IS NULL` for clearly finished games
- Reconciliation re-processing the same suspended game nightly

**Phase to address:**
Live polling phase (status detection) AND reconciliation phase (write logic). Status taxonomy must be mapped before implementation.

---

### Pitfall 7: Tomorrow-Mode Predictions with Stale Starting Pitcher Data

**What goes wrong:**
Date navigation allows viewing "tomorrow's" games. The pipeline only runs for TODAY. For tomorrow, the system either shows no predictions (confusing card layout) or attempts predictions with tomorrow's probable pitchers, which change 30-50% of the time between evening-before announcement and game day.

**Why it happens:**
MLB teams announce probable pitchers 1-3 days in advance, but late changes are common. The pipeline's temporal safety (`as_of_date=today`) would produce incorrect features for tomorrow's games -- today's results are missing from rolling averages.

**How to avoid:**
1. Tomorrow mode: schedule-only data (teams, times, probable pitchers), NO model predictions. Clear "Predictions available on game day" message.
2. Future dates (2+ days): schedule only, "TBD" for unannounced pitchers.
3. Do NOT run the prediction pipeline for non-today dates.

**Warning signs:**
- Users seeing prediction changes between evening and morning
- SP names on tomorrow's cards not matching actual starters
- History showing predictions that were never meant to be final

**Phase to address:**
Date navigation phase. Frontend and API must agree on data availability per date category.

---

### Pitfall 8: Nightly Reconciliation Job Missing Late West Coast Games

**What goes wrong:**
Nightly reconciliation at 1am ET queries MLB API, finds a West Coast game still in progress (7pm PT start = 10pm ET, ~1am ET finish for typical game). Job skips it. Game ends at 1:15am ET. Next reconciliation is 24 hours later. That game has no outcome for a full day.

**Why it happens:**
MLB game durations average ~3 hours. A 7:10pm PT first pitch means earliest Final ~10:10pm PT (1:10am ET). Extra innings push later.

**How to avoid:**
1. Schedule reconciliation at **3am ET** (midnight PT). Even extra-inning West Coast games finish by then.
2. Better: run TWICE -- 1am ET (East/Central) and 4am ET (everything).
3. Best: the live poller is the PRIMARY reconciliation mechanism. The nightly job is a safety net for missed polls.
4. Nightly job should query `WHERE game_date >= CURRENT_DATE - INTERVAL '3 days' AND actual_winner IS NULL` to catch suspended games that resumed.

**Warning signs:**
- West Coast games missing outcomes until the next evening
- Reconciliation `games_processed` count lower than expected

**Phase to address:**
Reconciliation phase. Job schedule must account for MLB's actual game time distribution.

---

### Pitfall 9: Live Poller Memory Pressure in the 1536M Worker Container

**What goes wrong:**
The worker container is capped at 1536M. `LiveFeatureBuilder.initialize()` loads two seasons of data (~500MB). If the poller shares the worker process, it holds state alongside the pipeline's feature matrix. During pipeline run + active polling, memory peaks and OOM kills the container. BlockingScheduler has no persistence -- poller misses Final transitions during restart.

**Why it happens:**
`LiveFeatureBuilder` loads the full feature matrix per pipeline run. In a long-lived process with a coexisting poller, the reference may persist between runs.

**How to avoid:**
1. The poller should NOT import `LiveFeatureBuilder`. It only needs `statsapi.schedule()` or `statsapi.get()` for scores.
2. Consider a separate lightweight container (new docker-compose service, 256M cap) for the poller.
3. If keeping poller in worker: ensure `LiveFeatureBuilder` is garbage-collected after each run. Do not keep the feature matrix resident.
4. Monitor RSS after each pipeline run. Alert if exceeding 1200M.

**Warning signs:**
- Worker restarting during 1pm pipeline run (heaviest)
- Poller intervals stretching beyond 90s (restart + cold start = 30-60s)
- Docker logs showing `Killed` followed by restart

**Phase to address:**
Live polling infrastructure. Memory budget must be planned before adding the poller.

---

### Pitfall 10: Frontend Schedule Lookup and Grouping Fails for Doubleheaders

**What goes wrong:**
The API builds `dict[(home_team, away_team), game_datetime]`. For doubleheaders, the second game overwrites the first. The frontend groups by `${pred.home_team}-${pred.away_team}` -- doubleheader predictions collapse into one GameCard.

**Why it happens:**
`_build_schedule_lookup()` in `api/routes/predictions.py` uses `(home, away)` tuple as dict key. The frontend `groupPredictions()` in `usePredictions.ts` uses `${home_team}-${away_team}` as Map key. Both are 1:1 lookups that assume one game per matchup per day.

**How to avoid:**
1. Use `game_id` (gamePk) as the lookup key, not team tuple.
2. Include `game_id`, `game_num`, and `doubleheader` in PredictionResponse.
3. Frontend grouping key: `game_id` or `${home_team}-${away_team}-${game_num}`.

**Warning signs:**
- Only one GameCard for a doubleheader day
- Wrong game time on first game's card
- React key collision warnings in console

**Phase to address:**
Schema migration (add game_id) and date navigation (API/frontend). Coordinated with Pitfall 1.

---

### Pitfall 11: Live Score Proxy Endpoint Creates Per-User MLB API Amplification

**What goes wrong:**
If the API container forwards each client's 90-second score poll directly to the MLB Stats API, then 10 concurrent users generate 10 upstream API calls per 90 seconds. During peak hours (7-10pm ET with 15 games live), this amplifies to potentially hundreds of calls per minute. The MLB Stats API has undocumented rate limits and may respond with 429 or connection resets.

**Why it happens:**
The natural approach is a simple proxy: client requests `/api/v1/scores`, API calls `statsapi.schedule(...)`, returns results. Without caching, every client request triggers an upstream call.

**How to avoid:**
1. **Server-side cache with 30-second TTL.** The API process caches the parsed schedule response. All requests within 30 seconds get cached data; only one upstream call per 30 seconds.
2. **Better: the worker (not the API) polls the MLB API on an interval and writes scores to Postgres.** The API serves scores from the database, not from upstream calls. This decouples client count from upstream API load entirely.
3. Shape the response: extract only needed fields (score, inning, bases, game_status) rather than forwarding the full MLB API response.

**Warning signs:**
- HTTP 429 responses from MLB Stats API in logs
- Score data intermittently returning empty/stale
- API container response latency spiking during peak game hours

**Phase to address:**
Live polling architecture. Choose between API-proxy-with-cache and worker-writes-to-DB pattern early.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Polling MLB API from the same worker process as pipeline | No new container, simpler deployment | OOM risk, shared memory pressure, no independent restart | Only if poller is carefully isolated from feature builder memory; monitor closely |
| Using `status == "Final"` string match | Quick to implement, works for 95% of games | Misses rain-shortened, suspended, forfeited games | Never in production; use abstractGameState or allowlist |
| Storing `game_date` from `date.today()` instead of MLB `officialDate` | No API change needed | UTC/ET boundary bugs for late games, breaks date navigation | Never -- officialDate is always available |
| Writing `actual_winner` only to `is_latest = TRUE` rows | Simpler UPDATE query | Outcome data lost when `mark_not_latest()` runs | Never -- reconciliation must target all rows for a game_id |
| Skipping `game_id` in predictions unique constraint | Avoids schema migration | Doubleheader data corruption | Never -- doubleheaders occur ~10-15 times per season |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| MLB Stats API schedule endpoint | Caching for the whole day | Re-fetch on each poll cycle. Games get postponed/suspended mid-day. Cache 2-5 minutes max. |
| MLB Stats API live feed | Calling `/game/{gamePk}/feed/live` for every game | Use schedule with `hydrate=linescore` for all games in one call. Only call live feed for expanded view. |
| MLB Stats API rate limiting | Assuming no rate limit (public API) | Undocumented limits exist. Add 200ms delay between per-game requests. |
| Postgres UPSERT with new columns | Adding reconciliation cols to `_PREDICTION_UPDATE_COLS` | Reconciliation columns EXCLUDED from UPSERT. Separate UPDATE function. |
| APScheduler BlockingScheduler | Assuming interval jobs run independently of cron jobs | Jobs share thread pool (default 10). Pipeline can exhaust threads, blocking poller. |
| statsapi.schedule() date format | Passing YYYY-MM-DD | statsapi expects MM/DD/YYYY. ISO format silently returns empty results. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling ALL games every 90s including Final/Scheduled | Unnecessary API calls, potential rate limiting | Only poll "Live" abstractGameState games | Day 1 -- wastes ~80% of calls |
| `/predictions/today` calling `fetch_today_schedule()` per request | N users x 60s poll = N upstream calls/minute | Server-side cache (5-min TTL) or worker writes to DB | 10+ concurrent users |
| Full `SELECT *` on predictions for history page | Slow queries, large responses | Select needed columns only. Paginate (LIMIT/OFFSET). | Full-season queries (~7,200 rows) |
| LiveFeatureBuilder re-init per pipeline run | 30-60s load, ~500MB RAM, 3x daily | Cache in worker process; reinit at midnight only | Every pipeline run |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "In Progress" with no score | Users leave for a real score site | Show score + inning minimum: "NYY 3, BOS 1 -- Top 7" |
| Tomorrow predictions with no staleness indicator | User trusts stale prediction | No predictions for tomorrow, or prominent "Preliminary" badge |
| Empty cards for future dates | Looks broken | "Predictions available on game day" with schedule-only layout |
| Final game with pre-game card layout | User does not notice game ended | Transform card: prominent score, checkmark/X correctness marker, dimmed probabilities |
| History page with no range limits | 30+ second loads for full season | Default 7 days, max 30 days, paginate |

## "Looks Done But Isn't" Checklist

- [ ] **Live score display:** Often missing runner-on-base state -- verify expanded card shows bases, pitcher, batter
- [ ] **Outcome reconciliation:** Often only computes ensemble correctness -- verify per-model (lr, rf, xgb) correctness is tracked
- [ ] **Date navigation "today":** Often resolves to UTC date -- verify ET-relative date, especially after midnight UTC
- [ ] **History accuracy:** Often uses simple win% -- verify denominator excludes postponed, suspended, no-prediction games
- [ ] **Reconciliation idempotency:** Often re-reconciles already-done games -- verify `WHERE actual_winner IS NULL`
- [ ] **Status filter fix:** Often shows all prediction rows separately -- verify grouping into one card per game
- [ ] **Doubleheader handling:** Often shows one card for two games -- verify game_num in grouping key
- [ ] **Poller shutdown:** Often polls after all games Final -- verify poller stops/sleeps when no Live games remain

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Doubleheader data corruption | MEDIUM | SQL script to find affected dates, re-reconcile via MLB API gamePk |
| UTC/ET date mismatch | LOW | Fix date computation, re-run reconciliation for affected range |
| Pipeline overwrites reconciliation | MEDIUM | Re-run nightly reconciliation; idempotent if using `WHERE actual_winner IS NULL` |
| OOM crash during polling | LOW | Container auto-restarts; nightly job catches missed Finals |
| Wrong actual_winner for suspended game | HIGH | NULL out actual_winner/prediction_correct; re-reconcile after game completes (days/weeks) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Doubleheader collision (1) | Schema migration (first) | Insert two predictions same matchup same date; both persist |
| Status filter cascade (2) | Filter fix + reconciliation | Toggle is_latest after reconciliation; outcome still visible |
| UTC/ET boundary (3) | Date navigation + infra | /predictions/today at 11pm ET returns today's ET games |
| Pipeline/poller race (4) | Reconciliation design | Simultaneous pipeline + poller writes; actual_winner survives |
| APScheduler collision (5) | Live polling | Pipeline during active polling; both complete without skip |
| Status zoo (6) | Live polling | Test Final (F), Final:Rain (FR), Suspended:Rain (TR), Postponed (DR) |
| Tomorrow stale SP (7) | Date navigation | Tomorrow view shows schedule only, no probabilities |
| Late West Coast (8) | Reconciliation | 7pm PT game reconciled by 4am ET backup run |
| Worker memory (9) | Polling infrastructure | RSS during pipeline + polling stays under 1400M |
| Frontend doubleheader (10) | Date navigation + frontend | Two distinct cards for doubleheader with correct times |
| API amplification (11) | Polling architecture | 10 concurrent users generate 1 upstream call per 30s |

## Sources

- [MLB Stats API Game Status Endpoint](https://statsapi.mlb.com/api/v1/gameStatus) -- 127 status codes verified via direct API call (HIGH confidence)
- [toddrob99/MLB-StatsAPI Wiki: schedule function](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-schedule) -- fields: doubleheader, game_num, game_datetime (HIGH confidence)
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) -- max_instances, BlockingScheduler (HIGH confidence)
- [APScheduler Issue #423: max_instances per function](https://github.com/agronholm/apscheduler/issues/423) -- function-level instance counting (HIGH confidence)
- [PostgreSQL Race Conditions](https://oneuptime.com/blog/post/2026-01-25-postgresql-race-conditions/view) -- concurrent UPDATE (HIGH confidence)
- [GUMBO Documentation](https://bdata-research-blog-prod.s3.amazonaws.com/uploads/2019/03/GUMBOPDF3-29.pdf) -- abstractGameState vs detailedState (MEDIUM confidence)
- Direct codebase analysis: `src/pipeline/schema.sql` (unique constraint), `src/pipeline/db.py` (_PREDICTION_UPDATE_COLS), `src/pipeline/runner.py` (pipeline flow), `src/pipeline/scheduler.py` (APScheduler config), `api/routes/predictions.py` (CURRENT_DATE, schedule lookup), `frontend/src/hooks/usePredictions.ts` (grouping key), `docker-compose.yml` (memory limits, no TZ), `Dockerfile` (no TZ env) -- all HIGH confidence

---
*Pitfalls research for: MLB Win Forecaster v2.2 -- Game Lifecycle, Live Scores & Historical Accuracy*
*Researched: 2026-03-30*
