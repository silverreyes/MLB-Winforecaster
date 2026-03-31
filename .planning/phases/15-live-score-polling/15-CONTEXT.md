# Phase 15: Live Score Polling - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

In-progress game cards show real-time score + inning + outs on the card face, updated every 90 seconds. Users can expand a LIVE card to see a bases diamond, pitch count (balls/strikes/outs), current batter with AVG/OPS, and on-deck batter. When the live poller detects a game transition to Final, it immediately writes `actual_winner` and `prediction_correct` to the Postgres predictions table.

Phase 15 is strictly live score display and outcome writes. Final card outcome rendering (FINL-01/02/03) and nightly reconciliation (FINL-04) are Phase 16. History route is Phase 17.

</domain>

<decisions>
## Implementation Decisions

### Live score endpoint design
- Live score fields (score, inning, runners, batter, pitch count) are **embedded in the existing `/games/{date}` response** — not a separate endpoint.
- `GameResponse` grows with optional live score fields (null when game is PRE_GAME or FINAL).
- The existing schedule cache (`get_schedule_cached`) stays at 75s TTL for schedule data. The API handler adds a separate per-game linescore cache (90s TTL) to prevent MLB API amplification from multiple browser tabs.
- `useGames` refetchInterval changes from 60s to 90s — but only when **both** conditions are met: (1) `viewMode === 'live'` (today selected) AND (2) at least one game has `game_status === 'LIVE'`. The `refetchInterval` callback checks `query.state.data?.games.some(g => g.game_status === 'LIVE')`. When today is selected but all games are PRE_GAME or FINAL, `refetchInterval` returns `false` (no polling). This is stricter than the current 60s-when-viewMode-is-live behavior.

### Live poller backend (LIVE-08)
- A new recurring APScheduler job in the **worker container** (alongside the 10am/1pm/5pm pipeline jobs).
- Runs every 90s, 24/7. Within the job body, it fetches the day's schedule first; only makes linescore API calls when at least one game has `abstractGameState === 'Live'`. When no live games exist, the job exits immediately (cheap schedule call only).
- `max_instances=1` on the job to prevent concurrent execution alongside pipeline jobs.
- **Error handling:** on MLB Stats API 503 or timeout, the poller **silently skips** that cycle — logs the error, does nothing. The next 90s tick retries naturally. The 15-minute pipeline retry logic (added in fix 14.5-03 for prediction jobs) does NOT apply to the live poller — applying it would leave scores stale for 15 minutes mid-game.
- When the poller detects `abstractGameState === 'Final'` for a game it hasn't yet written: queries `predictions` for all rows matching that `game_id` (not just `is_latest = TRUE` per STATE.md carry-forward), writes `actual_winner` and `prediction_correct` to all matching rows.

### Card face live layout (LIVE-01)
- A **score row** is inserted between the header row and the prediction body, visible only when `game_status === 'LIVE'`.
- Score row content: `{away_team} {away_score} – {home_team} {home_score} • {top|bot} {inning} • {outs} out(s)` — e.g., "NYY 3 – BOS 1 • Top 7th • 2 outs".
- Visual treatment: amber text on dark background, using `--color-accent` CSS custom property. No pulsing animation.
- The prediction body (pre/post-lineup columns) remains visible below the score row — scores do NOT replace predictions.

### Expanded live card UX (LIVE-03–07)
- Score row doubles as the **expand/collapse trigger** — clicking it toggles the expanded section below via `useState` (or `<details>`/`<summary>` if the score row can serve as `<summary>`).
- **Expanded view is ONLY available on LIVE cards.** The score row (which is the only expand trigger) is not rendered for PRE_GAME, FINAL, or POSTPONED cards. This is a hard constraint — no expand affordance on non-LIVE cards.
- Expanded area uses a **two-column layout** within the expanded section:
  - Left (~40%): bases diamond SVG
  - Right (~60%): balls/strikes/outs • current batter name + season AVG/OPS • on-deck batter name
- On-deck batter shows name only (no stats — LIVE-07 spec).

### Bases diamond (LIVE-04)
- **Inline SVG** — four diamond-shaped paths (not CSS positioned divs).
- Occupied base: **solid amber fill** using `--color-accent`.
- Empty base: **dark outline only** using `--color-border` or `--color-bg-card`.
- Diamond is compact, self-contained within the left column of the expanded section.

### Claude's Discretion
- Exact SVG coordinates and dimensions for the bases diamond
- Per-game linescore cache implementation detail (module-level dict + timestamp, separate from schedule cache)
- How the `statsapi.get('game', ...)` linescore response is parsed to extract runners on base (1B/2B/3B flags), current batter batting average/OPS, and on-deck batter name
- Whether the expanded section uses `<details>`/`<summary>` (native) or `useState` + CSS height transition (controlled)
- APScheduler time window for the live poller job (if time-gating proves cleaner than always-on with early-exit)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §LIVE-01 through LIVE-08 — full live score requirements (score display, polling gate, bases diamond, batter stats, outcome write)

### Carry-forward decisions (locked)
- `.planning/STATE.md` §Carry-Forward Decisions — critical prior decisions including:
  - "Live poller uses `statsapi.get()` not `statsapi.schedule()` to preserve linescore data"
  - "`abstractGameState` (3 values) not `detailedState` (127 values) for status detection"
  - "Reconciliation must target ALL prediction rows for a game_id, not just is_latest = TRUE rows"
  - "Reconciliation columns excluded from pipeline UPSERT to prevent overwrite race condition"

### Current backend
- `api/routes/games.py` — `/games/{date}` handler; `GameResponse` model and `build_games_response()` extend here
- `api/models.py` — `GameResponse`, `GamesDateResponse` Pydantic models; add live score fields here
- `src/data/mlb_schedule.py` — `get_schedule_cached()` (schedule cache); linescore cache follows same pattern
- `src/pipeline/scheduler.py` — existing APScheduler setup; new live poller job added here

### Current frontend
- `frontend/src/hooks/useGames.ts` — `refetchInterval` callback logic to update for 90s live-only polling gate
- `frontend/src/components/GameCard.tsx` — card structure; score row inserted here
- `frontend/src/components/GameCard.module.css` — CSS custom properties in use (must use `--color-accent`, `--color-border`, etc.)
- `frontend/src/api/types.ts` — `GameResponse` TypeScript interface; add live score fields

### Existing retry pattern
- Recent commit `bc91dc3` (fix 14.5-03) — pipeline job retry on 503/timeout; explicitly NOT applied to live poller

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_schedule_cached()` (`src/data/mlb_schedule.py`) — module-level dict + `threading.Lock` + TTL pattern; linescore cache follows the exact same structure
- `useGames.ts` `refetchInterval` callback — already reads `query.state.data?.view_mode`; extend to also check `games.some(g => g.game_status === 'LIVE')`
- `GameCard.tsx` — existing card structure with clear insertion point between `headerRow` and `predictionBody`
- CSS custom properties (`--color-accent`, `--color-border`, `--color-bg-card`) — amber + dark palette already defined; use these for diamond SVG fills

### Established Patterns
- Sync `def` handlers in FastAPI (not async) — new live score route follows same pattern
- `abstractGameState` for game status detection — already used in `map_game_status()` in `mlb_schedule.py`
- `game_id` (gamePk) always non-nullable in `GameResponse` — established in Phase 13; live poller uses it to query `statsapi.get('game', params={'gamePk': game_id})`
- `max_instances=1` pattern for APScheduler jobs — check `src/pipeline/scheduler.py` for existing job configs

### Integration Points
- `api/models.py` `GameResponse` → add optional live score fields (null when not LIVE)
- `api/routes/games.py` `build_games_response()` → inject live score data for LIVE games; add per-game linescore cache
- `frontend/src/api/types.ts` `GameResponse` → add live score fields (matching API model)
- `frontend/src/components/GameCard.tsx` → render score row + accordion expand section for LIVE cards
- `src/pipeline/scheduler.py` → register new `live_poller_job` with 90s interval, `max_instances=1`

</code_context>

<specifics>
## Specific Requirements

- **90s polling gate is strict:** `refetchInterval` in `useGames` returns `false` unless BOTH: today is selected AND at least one game is `game_status === 'LIVE'`. Document this condition explicitly in the hook.
- **Expanded view constraint is hard:** The score row (accordion trigger) must only render for `game_status === 'LIVE'`. Planner should add an explicit check so the expand affordance cannot accidentally appear on PRE_GAME/FINAL/POSTPONED cards.
- **Live poller error policy:** 503 or timeout → log + silent skip. Do NOT wrap in the 15-minute retry used by pipeline jobs. Stale for one 90s cycle is acceptable; stale for 15 minutes is not.
- **Reconciliation write targets ALL rows:** When writing `actual_winner`/`prediction_correct`, the poller updates all prediction rows for the `game_id` (not just `is_latest = TRUE`). This is pre-decided in STATE.md and must be reflected in the SQL UPDATE.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 15-live-score-polling*
*Context gathered: 2026-03-31*
