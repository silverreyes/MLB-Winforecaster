# Phase 15: Live Score Polling - Research

**Researched:** 2026-03-31
**Domain:** Live game data polling, real-time UI rendering, outcome reconciliation
**Confidence:** HIGH

## Summary

Phase 15 adds live score display to in-progress game cards, an expandable detail section with bases diamond / batter info, a backend live poller that writes game outcomes to Postgres, and a per-game linescore cache to prevent MLB API amplification. The work spans four layers: Pydantic API models (new `LiveScoreData` fields on `GameResponse`), the games route handler (linescore fetching + caching), a new APScheduler interval job in the worker container (90s live poller), and three new frontend components (`ScoreRow`, `LiveDetail`, `BasesDiamond`).

The MLB Stats API's `game` endpoint (`v1.1/game/{gamePk}/feed/live`) provides all required data in a single call when using the `fields` query parameter: linescore (inning, outs, balls, strikes), offense (current batter, on-deck batter, runners on 1st/2nd/3rd), team scores, and boxscore player season stats (AVG, OPS). This eliminates the need for multiple API calls per game. The server-side linescore cache (90s TTL, per-game_id keying) follows the identical `dict + Lock + TTL` pattern already established by `get_schedule_cached()`.

**Primary recommendation:** Build the backend (API model extension + linescore cache + games route enrichment + live poller job) first, then the frontend (types + hook update + ScoreRow + LiveDetail + BasesDiamond). The linescore cache and live poller are independent features that share the same MLB API call pattern but serve different purposes (API response enrichment vs. outcome detection).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Live score fields are **embedded in the existing `/games/{date}` response** -- not a separate endpoint. `GameResponse` grows with optional live score fields (null when not LIVE).
- Existing schedule cache (`get_schedule_cached`) stays at 75s TTL. A separate per-game linescore cache (90s TTL) prevents MLB API amplification.
- `useGames` `refetchInterval` changes from 60s to 90s, gated on BOTH: `viewMode === 'live'` AND `games.some(g => g.game_status === 'LIVE')`.
- Live poller is a new APScheduler job in the **worker container**, running every 90s with `max_instances=1`.
- Live poller on 503/timeout: silent skip + log. NOT the 15-minute retry used by pipeline jobs.
- Reconciliation writes target ALL prediction rows for a `game_id`, not just `is_latest = TRUE`.
- Score row is the expand/collapse trigger, rendered ONLY for `game_status === 'LIVE'`.
- Expand uses `useState<boolean>(false)`, NOT `<details>/<summary>`.
- Bases diamond: inline SVG, 80x80 viewBox, occupied base amber fill, empty base dark outline.
- Score row background: `rgba(245, 158, 11, 0.08)`.

### Claude's Discretion
- Exact SVG coordinates and dimensions for the bases diamond (already specified in UI-SPEC as specific coords)
- Per-game linescore cache implementation detail (module-level dict + timestamp)
- How `statsapi.get('game', ...)` response is parsed to extract runners, batter AVG/OPS, on-deck batter
- APScheduler time window for live poller (always-on with early-exit chosen per CONTEXT.md)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LIVE-01 | In-progress game cards display current score and inning on the card face | MLB API linescore structure verified; ScoreRow component spec in UI-SPEC; `GameResponse` model extension documented |
| LIVE-02 | Dashboard polls live game data every 90s only while in-progress games are present and selected date is today | TanStack Query v5 `refetchInterval` callback API verified; dual-gate condition (`viewMode === 'live'` AND live games exist) |
| LIVE-03 | User can expand an in-progress game card to view detailed live game state | `useState` expand mechanic locked in UI-SPEC; ScoreRow as trigger; conditional render for LIVE-only |
| LIVE-04 | Expanded card shows bases diamond with runners highlighted | Inline SVG spec in UI-SPEC (80x80, exact coords); MLB API `linescore.offense.first/second/third` confirmed |
| LIVE-05 | Expanded card shows current pitch count (balls/strikes/outs) | MLB API `linescore.balls`, `linescore.strikes`, `linescore.outs` verified at game feed endpoint |
| LIVE-06 | Expanded card shows current batter name and key stats | Batter name from `linescore.offense.batter.fullName`; AVG/OPS from `boxscore.teams.{side}.players[ID].seasonStats.batting.avg/ops` |
| LIVE-07 | Expanded card shows on-deck batter name | `linescore.offense.onDeck.fullName` verified in live API response |
| LIVE-08 | Live poller writes `actual_winner` and `prediction_correct` when game transitions to Final | `abstractGameState` detection via existing `map_game_status()`; SQL UPDATE targeting all rows with matching `game_id`; reconciliation columns excluded from pipeline UPSERT |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| MLB-StatsAPI | 1.9.0 | `statsapi.get('game', ...)` for linescore data | Already in requirements.txt; raw API access preserves full JSON |
| APScheduler | >=3.11.0,<4.0 | `IntervalTrigger` for 90s live poller job | Already used for 3 daily cron jobs in worker container |
| FastAPI | >=0.115.0,<1.0 | Sync route handler, Pydantic models | Existing API framework |
| psycopg | >=3.3.0,<4.0 | Reconciliation SQL UPDATE | Existing DB driver |
| React | 19.2.x | `useState` for expand state | Existing frontend framework |
| @tanstack/react-query | 5.95.x | `refetchInterval` callback for polling gate | Existing data fetching library |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | (bundled w/ FastAPI) | `LiveScoreData` nested model, `GameResponse` extension | API model definitions |
| threading.Lock | stdlib | Thread-safe linescore cache | Same pattern as schedule cache |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-game linescore cache | Expanding schedule cache | Separate concern: schedule data is per-date, linescore is per-game and only for live games |
| `statsapi.get('game')` | `statsapi.linescore()` | `linescore()` returns formatted text string, not raw JSON; `get()` returns dict we can parse |
| IntervalTrigger(seconds=90) | CronTrigger | IntervalTrigger is correct for continuous polling; CronTrigger is for time-of-day jobs |

**Installation:** No new packages required -- all dependencies already in `requirements.txt` and `frontend/package.json`.

## Architecture Patterns

### Recommended Project Structure
```
api/
  models.py              # Add LiveScoreData model, extend GameResponse
  routes/games.py        # Add linescore fetch + cache, enrich LIVE games
src/
  data/mlb_schedule.py   # Add linescore cache (parallel to schedule cache)
  pipeline/scheduler.py  # Add live_poller_job with IntervalTrigger
  pipeline/db.py         # Add write_game_outcome() function
frontend/src/
  api/types.ts           # Add LiveScoreData interface, extend GameResponse
  hooks/useGames.ts      # Update refetchInterval gate
  components/
    GameCard.tsx          # Add ScoreRow + expand state + LiveDetail render
    GameCard.module.css   # Add scoreRow, expandedDetail CSS classes
    BasesDiamond.tsx      # New: inline SVG component
    LiveDetail.tsx        # New: expanded section component
    LiveDetail.module.css # New: expanded section styles
```

### Pattern 1: Linescore Cache (mirrors schedule cache)

**What:** Module-level dict keyed by `game_id` (int), values are `(timestamp, dict)` tuples. Thread-safe via `threading.Lock`. 90s TTL. Bounded to prevent unbounded growth.

**When to use:** Every request to `/games/{date}` when `view_mode == 'live'` and at least one game has `game_status == 'LIVE'`.

**Example:**
```python
# Source: Pattern from existing get_schedule_cached() in src/data/mlb_schedule.py
import time
import threading
import statsapi

_linescore_cache: dict[int, tuple[float, dict]] = {}
_linescore_lock = threading.Lock()
_LINESCORE_TTL = 90  # seconds
_LINESCORE_MAX_ENTRIES = 20  # max concurrent live games in a day

def get_linescore_cached(game_id: int) -> dict | None:
    """Fetch live game data with 90s TTL cache."""
    now = time.monotonic()
    with _linescore_lock:
        if game_id in _linescore_cache:
            ts, data = _linescore_cache[game_id]
            if now - ts < _LINESCORE_TTL:
                return data

    # Fetch outside lock to avoid blocking
    try:
        raw = statsapi.get('game', {'gamePk': game_id})
    except Exception:
        return None

    with _linescore_lock:
        if len(_linescore_cache) >= _LINESCORE_MAX_ENTRIES and game_id not in _linescore_cache:
            oldest = min(_linescore_cache, key=lambda k: _linescore_cache[k][0])
            del _linescore_cache[oldest]
        _linescore_cache[game_id] = (now, raw)

    return raw
```

### Pattern 2: MLB API Response Parsing

**What:** Extract live score fields from the raw `statsapi.get('game')` response using defensive `.get()` chaining.

**When to use:** In the games route handler when building `GameResponse` for LIVE games.

**Example:**
```python
# Source: Verified against live MLB Stats API response (game 747009)
def parse_linescore(raw: dict, game_id: int) -> dict | None:
    """Extract live score data from raw game feed response.

    Returns dict matching LiveScoreData fields, or None if parsing fails.
    """
    live = raw.get('liveData', {})
    ls = live.get('linescore', {})
    offense = ls.get('offense', {})

    # Core score data
    home_runs = ls.get('teams', {}).get('home', {}).get('runs')
    away_runs = ls.get('teams', {}).get('away', {}).get('runs')
    if home_runs is None or away_runs is None:
        return None

    inning = ls.get('currentInning')
    inning_half_raw = ls.get('inningHalf', '')  # "Top", "Bottom", "Middle", "End"

    # Map inningHalf to top/bottom
    if inning_half_raw.lower() in ('top',):
        inning_half = 'top'
    elif inning_half_raw.lower() in ('bottom',):
        inning_half = 'bottom'
    else:
        inning_half = 'top'  # "Middle"/"End" treated as top for display

    # Count data
    outs = ls.get('outs', 0)
    balls = ls.get('balls', 0)
    strikes = ls.get('strikes', 0)

    # Runners: offense.first/second/third are present only when occupied
    runner_on_1b = 'first' in offense
    runner_on_2b = 'second' in offense
    runner_on_3b = 'third' in offense

    # Current batter
    batter_obj = offense.get('batter', {})
    batter_name = batter_obj.get('fullName')
    batter_id = batter_obj.get('id')

    # On-deck batter
    on_deck_obj = offense.get('onDeck', {})
    on_deck_name = on_deck_obj.get('fullName')

    # Batter season stats from boxscore (AVG, OPS)
    batter_avg = None
    batter_ops = None
    if batter_id:
        boxscore = live.get('boxscore', {})
        # Batter could be on either team -- check both
        for side in ('home', 'away'):
            players = boxscore.get('teams', {}).get(side, {}).get('players', {})
            player_key = f'ID{batter_id}'
            player_data = players.get(player_key, {})
            season_batting = player_data.get('seasonStats', {}).get('batting', {})
            if season_batting.get('avg'):
                batter_avg = season_batting['avg']
                batter_ops = season_batting.get('ops')
                break

    return {
        'away_score': away_runs,
        'home_score': home_runs,
        'inning': inning,
        'inning_half': inning_half,
        'outs': outs,
        'balls': balls,
        'strikes': strikes,
        'runner_on_1b': runner_on_1b,
        'runner_on_2b': runner_on_2b,
        'runner_on_3b': runner_on_3b,
        'current_batter': batter_name,
        'batter_avg': batter_avg,
        'batter_ops': batter_ops,
        'on_deck_batter': on_deck_name,
    }
```

### Pattern 3: Live Poller Job (APScheduler IntervalTrigger)

**What:** A new APScheduler job in the worker container that runs every 90 seconds, checks for live games, and writes outcomes when games transition to Final.

**When to use:** Registered alongside existing cron jobs in `create_scheduler()`.

**Example:**
```python
# Source: APScheduler 3.x docs + existing scheduler.py pattern
from apscheduler.triggers.interval import IntervalTrigger

scheduler.add_job(
    live_poller_job,
    IntervalTrigger(seconds=90),
    args=[pool],
    id="live_poller",
    name="Live score poller (90s)",
    max_instances=1,
    misfire_grace_time=30,
)
```

### Pattern 4: Reconciliation SQL

**What:** When a game transitions to Final, write `actual_winner`, `prediction_correct`, and `reconciled_at` to ALL prediction rows matching that `game_id`.

**When to use:** In the live poller job when `abstractGameState === 'Final'` is detected.

**Example:**
```python
# Source: STATE.md carry-forward decisions + migration_001.sql schema
from datetime import datetime, timezone

def write_game_outcome(pool, game_id: int, home_team: str, away_team: str,
                       home_score: int, away_score: int) -> int:
    """Write actual_winner and prediction_correct for all predictions of a game.

    Returns number of rows updated.
    """
    actual_winner = home_team if home_score > away_score else away_team

    sql = """
        UPDATE predictions
        SET actual_winner = %(actual_winner)s,
            prediction_correct = (
                CASE
                    WHEN (lr_prob + rf_prob + xgb_prob) / 3.0 >= 0.5
                    THEN %(actual_winner)s = home_team
                    ELSE %(actual_winner)s = away_team
                END
            ),
            reconciled_at = %(reconciled_at)s
        WHERE game_id = %(game_id)s
          AND actual_winner IS NULL
    """
    with pool.connection() as conn:
        cur = conn.execute(sql, {
            'game_id': game_id,
            'actual_winner': actual_winner,
            'reconciled_at': datetime.now(timezone.utc),
        })
        count = cur.rowcount
        conn.commit()
    return count
```

**Note:** The `prediction_correct` computation should compare the model's ensemble probability (avg of lr/rf/xgb) against 0.5 to determine if it predicted the home team, then check if that matches the actual winner. The exact SQL may need adjustment -- the pattern above shows the intent.

### Anti-Patterns to Avoid

- **Fetching full game feed without `fields` filter:** The full `v1.1/game/{gamePk}/feed/live` response is ~500KB-2MB. Always use the `fields` query parameter to request only needed fields (linescore, offense, boxscore player stats). This reduces response size to ~5-10KB.
- **Polling when no live games exist:** The `refetchInterval` callback MUST return `false` when no games have `game_status === 'LIVE'`, even if today is selected. Polling an endpoint that returns 15 `PRE_GAME` cards every 90 seconds wastes bandwidth.
- **Using `statsapi.schedule()` for linescore data:** The `schedule()` wrapper strips `abstractGameState`/`codedGameState` and doesn't return linescore data. Use `statsapi.get('game', ...)` which returns raw JSON.
- **Applying pipeline retry logic to live poller:** The 15-minute `RETRY_SLEEP_SECONDS` pattern in `run_pipeline_with_retry()` would leave scores stale mid-game. Live poller on error: log + silent skip. Next 90s tick retries naturally.
- **Writing `actual_winner` only to `is_latest = TRUE` rows:** STATE.md explicitly requires targeting ALL prediction rows for a `game_id`. Carry-forward predictions (older versions) also need outcome stamps for historical accuracy tracking.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MLB API caching | Custom Redis/memcached setup | Module-level dict + Lock + TTL (existing pattern) | Consistent with `get_schedule_cached()`; no new infrastructure |
| Game status detection | Custom status string parsing | Existing `map_game_status()` in `mlb_schedule.py` | Already handles `abstractGameState` -> `PRE_GAME`/`LIVE`/`FINAL`/`POSTPONED` mapping |
| Periodic job scheduling | `while True: sleep(90)` loop | APScheduler `IntervalTrigger` with `max_instances=1` | Handles concurrency, missed runs, graceful shutdown |
| Inning ordinal formatting | Manual suffix logic | Simple lookup function | Standard pattern: 1st, 2nd, 3rd, 4th+th |
| Bases diamond SVG | Canvas or DOM-based diamond | Inline SVG in React component | Spec provides exact coordinates; SVG is declarative and accessible |

**Key insight:** The project already has established patterns for every major backend concern (caching, scheduling, status mapping, DB writes). Phase 15 extends these patterns rather than introducing new architectural concepts.

## Common Pitfalls

### Pitfall 1: MLB API Amplification (Multiple Tabs)
**What goes wrong:** Multiple browser tabs or clients each trigger `/games/{date}`, each of which fetches linescore data from MLB API. With 15 live games and 10 tabs, that's 150 API calls per 90s cycle.
**Why it happens:** No server-side deduplication of MLB API calls.
**How to avoid:** The per-game linescore cache with 90s TTL ensures at most one MLB API call per game per 90s window, regardless of how many clients request `/games/{date}`. First request fetches; subsequent requests within TTL get cached data.
**Warning signs:** MLB API 429 (rate limit) or 503 errors in API server logs.

### Pitfall 2: Race Condition Between Pipeline UPSERT and Reconciliation
**What goes wrong:** The pipeline's `insert_prediction()` UPSERT includes `DO UPDATE SET` for prediction columns. If reconciliation columns (`actual_winner`, `prediction_correct`, `reconciled_at`) were in `_PREDICTION_UPDATE_COLS`, a late-running pipeline job could overwrite outcome data.
**Why it happens:** The 5pm confirmation pipeline runs while games may be finishing.
**How to avoid:** Already handled -- `_PREDICTION_UPDATE_COLS` in `db.py` deliberately excludes reconciliation columns (see line 109 comment). The live poller writes these columns via a separate SQL UPDATE, never through the UPSERT path.
**Warning signs:** `actual_winner` values going NULL after being written. Check pipeline_runs table timing vs. reconciled_at timestamps.

### Pitfall 3: APScheduler Job Collision
**What goes wrong:** If a live poller cycle takes >90s (e.g., fetching 15 game linescores from MLB API), the next cycle starts before the previous finishes, causing duplicate outcome writes.
**Why it happens:** `IntervalTrigger` fires every 90s regardless of job duration.
**How to avoid:** `max_instances=1` on the job configuration. APScheduler logs a warning ("maximum number of running instances reached") and skips the overlapping cycle.
**Warning signs:** Warning logs about skipped instances. Monitor with APScheduler event listeners if needed.

### Pitfall 4: `inningHalf` Values Beyond Top/Bottom
**What goes wrong:** The MLB API returns `inningHalf` values of "Middle" (between half-innings) and "End" (inning complete), not just "Top" and "Bottom".
**Why it happens:** Between-innings game states.
**How to avoid:** Map "Middle" and "End" to a reasonable display value. "Middle" can display as the last known half (defaulting to "Top"); "End" similarly. The score row format handles this gracefully.
**Warning signs:** Score row showing unexpected inning text. Add logging when unknown `inningHalf` values appear.

### Pitfall 5: Batter Data Null During Between-Innings
**What goes wrong:** During half-inning transitions (Middle/End states), `offense.batter` may be null or reference the last batter rather than the next one. `onDeck` may also be null.
**Why it happens:** MLB API reflects true game state -- between innings, there's no current at-bat.
**How to avoid:** UI-SPEC specifies fallbacks: null batter shows `--`, null stats omit the stats line, null on-deck omits the entire section. Backend should pass `None` for these fields.
**Warning signs:** Expanded section showing stale batter data that doesn't match the broadcast.

### Pitfall 6: Boxscore Player ID Key Format
**What goes wrong:** Boxscore player entries are keyed as `"ID{player_id}"` (e.g., `"ID656775"`), not as bare integers.
**Why it happens:** MLB API convention for player keys in boxscore JSON.
**How to avoid:** When looking up batter season stats, construct the key as `f'ID{batter_id}'`. Check both home and away team players since the current batter could be on either team.
**Warning signs:** Batter AVG/OPS always showing as null even when the batter is in the lineup.

### Pitfall 7: Stale Linescore Cache After Game Ends
**What goes wrong:** A game transitions to Final but the linescore cache still holds the last live data for up to 90s. Clients see "LIVE" score row when the schedule already says "FINAL".
**Why it happens:** Linescore cache TTL and schedule cache TTL expire independently.
**How to avoid:** The card's rendering logic uses `game_status` from the schedule data (which has its own 75s cache). When `game_status` transitions to `FINAL`, the ScoreRow stops rendering regardless of what's in the linescore cache. The linescore cache entry for that game_id naturally expires and is never fetched again.
**Warning signs:** Brief flash of stale data during LIVE->FINAL transition. Acceptable given 75-90s cache windows.

## Code Examples

### MLB API Field-Filtered Request (verified)
```python
# Source: Verified against https://statsapi.mlb.com/api/v1.1/game/747009/feed/live
# Using fields parameter to minimize response size
raw = statsapi.get('game', {'gamePk': game_id,
    'fields': 'liveData,linescore,currentInning,currentInningOrdinal,'
              'inningHalf,outs,balls,strikes,teams,home,away,runs,'
              'offense,defense,batter,onDeck,first,second,third,fullName,id,'
              'boxscore,players,person,seasonStats,batting,avg,ops,'
              'gameData,status,abstractGameState'
})
```

### Inning Ordinal Formatter (TypeScript)
```typescript
// Source: UI-SPEC copywriting contract
function formatInningOrdinal(inning: number): string {
  if (inning === 1) return '1st';
  if (inning === 2) return '2nd';
  if (inning === 3) return '3rd';
  return `${inning}th`;
}

function formatInningHalf(half: 'top' | 'bottom'): string {
  return half === 'top' ? 'Top' : 'Bot';
}
```

### BasesDiamond Component (from UI-SPEC)
```tsx
// Source: 15-UI-SPEC.md Bases Diamond SVG Specification
interface BasesDiamondProps {
  runner_on_1b: boolean;
  runner_on_2b: boolean;
  runner_on_3b: boolean;
}

function BasesDiamond({ runner_on_1b, runner_on_2b, runner_on_3b }: BasesDiamondProps) {
  const occupied = '#F59E0B';  // --color-accent
  const empty = 'none';
  const stroke = '#1E1E2A';   // --color-border

  return (
    <svg viewBox="0 0 80 80" width="80" height="80" role="img"
         aria-label={describeRunners(runner_on_1b, runner_on_2b, runner_on_3b)}>
      {/* Basepaths */}
      <line x1="40" y1="72" x2="64" y2="40" stroke={stroke} strokeWidth="1" />
      <line x1="64" y1="40" x2="40" y2="8" stroke={stroke} strokeWidth="1" />
      <line x1="40" y1="8" x2="16" y2="40" stroke={stroke} strokeWidth="1" />
      <line x1="16" y1="40" x2="40" y2="72" stroke={stroke} strokeWidth="1" />
      {/* Home plate */}
      <polygon points="40,78 34,72 34,68 46,68 46,72"
               fill="none" stroke={stroke} strokeWidth="1.5" />
      {/* 1st base */}
      <rect x="58" y="34" width="12" height="12" rx="1"
            transform="rotate(45, 64, 40)"
            fill={runner_on_1b ? occupied : empty}
            stroke={stroke} strokeWidth="1.5" />
      {/* 2nd base */}
      <rect x="34" y="2" width="12" height="12" rx="1"
            transform="rotate(45, 40, 8)"
            fill={runner_on_2b ? occupied : empty}
            stroke={stroke} strokeWidth="1.5" />
      {/* 3rd base */}
      <rect x="10" y="34" width="12" height="12" rx="1"
            transform="rotate(45, 16, 40)"
            fill={runner_on_3b ? occupied : empty}
            stroke={stroke} strokeWidth="1.5" />
    </svg>
  );
}
```

### Reconciliation Write (SQL)
```sql
-- Source: STATE.md carry-forward + migration_001.sql
-- Targets ALL prediction rows for a game_id (not just is_latest = TRUE)
UPDATE predictions
SET actual_winner = %(actual_winner)s,
    prediction_correct = (
        CASE
            WHEN (lr_prob + rf_prob + xgb_prob) / 3.0 >= 0.5
            THEN %(actual_winner)s = home_team
            ELSE %(actual_winner)s = away_team
        END
    ),
    reconciled_at = %(reconciled_at)s
WHERE game_id = %(game_id)s
  AND actual_winner IS NULL;
```

### refetchInterval Gate Update
```typescript
// Source: Existing useGames.ts pattern + CONTEXT.md decision
refetchInterval: (query) => {
  const viewMode = query.state.data?.view_mode;
  if (viewMode !== 'live') return false;
  const hasLiveGames = query.state.data?.games?.some(
    (g: GameResponse) => g.game_status === 'LIVE'
  );
  return hasLiveGames ? 90_000 : false;
},
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 60s polling always-on when today selected | 90s polling gated on live games existing | Phase 15 | Eliminates unnecessary polling pre-game and post-game |
| `statsapi.schedule()` for game data | `statsapi.get('game')` for live data | Phase 13 | Preserves full JSON including linescore, status fields |
| No outcome tracking | Live poller writes `actual_winner` on Final | Phase 15 | Enables accuracy tracking in Phase 16-17 |

**Deprecated/outdated:**
- `statsapi.linescore()` returns formatted text, not raw JSON -- do not use for data extraction
- The current 60s `refetchInterval` in `useGames.ts` will be replaced by the 90s gated version

## Open Questions

1. **Tied games / extra innings**
   - What we know: MLB no longer has ties in regular season (Manfred runner rule since 2020). Extra innings have `currentInning > 9`.
   - What's unclear: Whether `inningHalf` values differ in extras. Likely identical ("Top"/"Bottom").
   - Recommendation: Handle `currentInning > 9` naturally (ordinal formatter produces "10th", "11th", etc.). No special casing needed.

2. **Postponement mid-game**
   - What we know: `codedGameState === 'D'` maps to `POSTPONED` in `map_game_status()`. A game could theoretically start and then be postponed.
   - What's unclear: Whether `abstractGameState` changes to "Final" or stays "Live" for suspended games.
   - Recommendation: The live poller should only write outcomes for `abstractGameState === 'Final'`, never for postponed games. Phase 16 nightly reconciliation handles edge cases.

3. **Batter stats during Spring Training / Opening Day**
   - What we know: Season AVG/OPS in boxscore may be `.000`/`.000` for players in their first game.
   - What's unclear: Whether the API returns empty strings or zero values.
   - Recommendation: Display whatever the API returns. `.000` is valid for Opening Day. Null/empty triggers the "omit stats line" fallback per UI-SPEC.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_pipeline/test_live_poller.py -x` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIVE-01 | GameResponse includes live_score fields for LIVE games | unit | `pytest tests/test_api/test_games_live.py::test_live_game_has_score -x` | No -- Wave 0 |
| LIVE-01 | live_score is null for non-LIVE games | unit | `pytest tests/test_api/test_games_live.py::test_non_live_game_null_score -x` | No -- Wave 0 |
| LIVE-02 | refetchInterval returns 90000 when live games exist | manual-only | Manual: inspect useGames.ts logic; no frontend test framework | N/A |
| LIVE-02 | refetchInterval returns false when no live games | manual-only | Manual: inspect useGames.ts logic | N/A |
| LIVE-03 | ScoreRow renders only for LIVE status | manual-only | Manual: visual verification in browser | N/A |
| LIVE-04 | BasesDiamond fills correct bases | unit | `pytest tests/test_api/test_games_live.py::test_runners_parsed -x` | No -- Wave 0 |
| LIVE-05 | Pitch count parsed from API response | unit | `pytest tests/test_api/test_games_live.py::test_count_parsed -x` | No -- Wave 0 |
| LIVE-06 | Batter name + stats parsed from boxscore | unit | `pytest tests/test_api/test_games_live.py::test_batter_stats -x` | No -- Wave 0 |
| LIVE-07 | On-deck batter name parsed | unit | `pytest tests/test_api/test_games_live.py::test_on_deck_parsed -x` | No -- Wave 0 |
| LIVE-08 | Outcome write targets all rows for game_id | unit (mock DB) | `pytest tests/test_pipeline/test_live_poller.py::test_outcome_write_all_rows -x` | No -- Wave 0 |
| LIVE-08 | Outcome write sets prediction_correct correctly | unit (mock DB) | `pytest tests/test_pipeline/test_live_poller.py::test_prediction_correct -x` | No -- Wave 0 |
| LIVE-08 | Poller skips on 503/timeout (no retry) | unit | `pytest tests/test_pipeline/test_live_poller.py::test_503_silent_skip -x` | No -- Wave 0 |
| LIVE-08 | Poller skips when no live games | unit | `pytest tests/test_pipeline/test_live_poller.py::test_no_live_games_early_exit -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline/test_live_poller.py tests/test_api/test_games_live.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline/test_live_poller.py` -- covers LIVE-08 (poller job, outcome write, error handling, early exit)
- [ ] `tests/test_api/test_games_live.py` -- covers LIVE-01, LIVE-04-07 (linescore parsing, API response enrichment)
- [ ] No frontend test framework exists -- LIVE-02, LIVE-03 are manual verification only

## Sources

### Primary (HIGH confidence)
- MLB Stats API live game feed -- verified field paths against `https://statsapi.mlb.com/api/v1.1/game/747009/feed/live` with `fields` parameter
- Existing codebase files: `src/data/mlb_schedule.py` (cache pattern), `src/pipeline/scheduler.py` (APScheduler pattern), `src/pipeline/db.py` (UPSERT + column exclusion), `api/models.py` (Pydantic models), `api/routes/games.py` (route handler)
- `15-CONTEXT.md` and `15-UI-SPEC.md` -- locked design decisions and component specifications

### Secondary (MEDIUM confidence)
- [APScheduler 3.x IntervalTrigger docs](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html) -- verified `seconds` parameter and `max_instances` behavior
- [TanStack React Query v5 useQuery docs](https://tanstack.com/query/v5/docs/framework/react/reference/useQuery) -- `refetchInterval` callback signature
- [toddrob99/MLB-StatsAPI GitHub](https://github.com/toddrob99/MLB-StatsAPI) -- `statsapi.get()` function interface and endpoint definitions

### Tertiary (LOW confidence)
- `inningHalf` values "Middle" and "End" -- observed in documentation references but not verified against a live in-progress game. The mapping logic handles them safely.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use; no new dependencies
- Architecture: HIGH -- extends existing patterns (cache, scheduler, Pydantic models, route handler)
- MLB API structure: HIGH -- verified against live API responses with field filtering
- Pitfalls: HIGH -- five converging pitfalls identified in STATE.md; all have documented mitigations
- Frontend components: HIGH -- UI-SPEC provides exact CSS, SVG coordinates, copy, and interaction contracts

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable -- MLB API structure unchanged since 2019 GUMBO specification; all libraries are already pinned in requirements.txt)
