# Phase 14: Date Navigation - Research

**Researched:** 2026-03-31
**Domain:** React date navigation UI, TanStack Query conditional polling, FastAPI backend date-aware responses, MLB Stats API probable pitcher hydration
**Confidence:** HIGH

## Summary

Phase 14 adds date navigation to the dashboard -- arrow controls, a date picker, and date-aware content rendering. The existing `/games/{date}` endpoint already accepts arbitrary dates (designed for this in Phase 13), so backend changes are minimal. The primary work is frontend: a DateNavigator component, conditional polling logic in `useGames()`, and date-context-aware card rendering that distinguishes past, today, tomorrow, and future dates.

The critical complexity is DATE-07 (tomorrow's games with confirmed SPs shown as PRELIMINARY predictions). This requires extending `fetch_schedule_for_date()` to extract probable pitcher data from the MLB Stats API (via `hydrate=probablePitcher(note)`), and extending the `GameResponse` model to communicate whether a game is "preliminary", "schedule-only", or "live". The backend must determine the date context (past/today/tomorrow/future) and surface it in the response so the frontend can render appropriate content.

A key architectural decision: the backend should include a `view_mode` field in the `GamesDateResponse` (or per-game metadata) that tells the frontend what rendering behavior to apply, rather than having the frontend independently determine date context. This centralizes date logic (time zone handling, "today" definition) on the server side.

**Primary recommendation:** Add a `view_mode` field to `GamesDateResponse` (`'live' | 'historical' | 'tomorrow' | 'future'`) computed server-side, extend `fetch_schedule_for_date()` with `hydrate=probablePitcher(note)` for tomorrow's pitcher data, and build a `DateNavigator` component using a native HTML `<input type="date">` with left/right arrow buttons.

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATE-01 | User can step to previous day via left arrow control | Frontend DateNavigator component with `<button>` left arrow, date state management in App.tsx |
| DATE-02 | User can step to next day via right arrow control | Frontend DateNavigator component with `<button>` right arrow, same state management |
| DATE-03 | User can pick a specific date via date input control | Native `<input type="date">` styled to match dark theme; no third-party date picker needed |
| DATE-04 | Dashboard loads today's date by default | Existing `useGames()` already defaults to `todayDateStr()`; DateNavigator initializes to today |
| DATE-05 | Past dates display stored predictions from DB | Existing `/games/{date}` already queries predictions for any date; backend adds `view_mode: 'historical'` to disable frontend polling |
| DATE-06 | Today's date displays live pipeline predictions with live polling active | `useGames()` sets `refetchInterval: 60_000` only when `view_mode === 'live'`; `false` otherwise |
| DATE-07 | Tomorrow: games with both SPs confirmed show PRELIMINARY prediction; unconfirmed SP games show schedule only | Backend extends `fetch_schedule_for_date()` with `hydrate=probablePitcher(note)` to get SP names; `GameResponse` gains `prediction_label` field; tomorrow games with both SPs get `'PRELIMINARY'` label |
| DATE-08 | Beyond tomorrow: scheduled matchups only with "Predictions available on game day" message | Backend returns `view_mode: 'future'`; frontend renders message banner and schedule-only stub cards |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | Frontend UI framework | Already in use |
| @tanstack/react-query | 5.95.2 | Data fetching with conditional polling | Already in use; supports `refetchInterval: false` to disable polling |
| FastAPI | (existing) | API framework | Already serving `/api/v1/games/{date}` |
| Pydantic | (existing) | Response model validation | Already in use in `api/models.py` |
| MLB-StatsAPI | 1.9.0 | MLB Stats API wrapper | Already in use; `statsapi.get('schedule', params)` supports `hydrate` parameter |
| TypeScript | ~5.9.3 | Frontend type system | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime` (stdlib) | N/A | Server-side date comparison | Determine view_mode (today vs past vs tomorrow vs future) |
| Native HTML `<input type="date">` | N/A | Date picker UI | No third-party date picker needed; dark theme via CSS |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `<input type="date">` | react-datepicker or similar | Native is simpler, no bundle size increase, good enough for single-date selection. Third-party only needed for range pickers or complex UX. |
| Server-side `view_mode` | Client-side date comparison | Server already knows the date and time zone. Centralizing avoids timezone bugs where browser midnight != server midnight. |
| Extending `GameResponse` with `prediction_label` | Separate endpoint for tomorrow | Extending the existing shape is cleaner; one endpoint for all dates, different metadata per view_mode. |

**No new packages required.** All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
api/
  routes/
    games.py             # UPDATED: add view_mode computation, probable pitcher extraction for tomorrow
  models.py              # UPDATED: add view_mode to GamesDateResponse, prediction_label to GameResponse
src/
  data/
    mlb_schedule.py      # UPDATED: add hydrate=probablePitcher(note) for tomorrow dates, extract SP names
frontend/
  src/
    components/
      DateNavigator.tsx        # NEW: left/right arrows + date picker
      DateNavigator.module.css # NEW: styling
      FutureDateBanner.tsx     # NEW: "Predictions available on game day" banner
      FutureDateBanner.module.css # NEW: styling
      GameCard.tsx             # UPDATED: show PRELIMINARY badge for tomorrow confirmed-SP games
      EmptyState.tsx           # UPDATED: date-aware empty state text
    hooks/
      useGames.ts              # UPDATED: conditional polling based on view_mode
      useSelectedDate.ts       # NEW: date state management (or inline in App.tsx)
    App.tsx                    # UPDATED: add DateNavigator, pass selectedDate to useGames
    api/
      types.ts                 # UPDATED: add ViewMode, prediction_label to GameResponse
```

### Pattern 1: Server-Side View Mode Computation
**What:** The `/games/{date}` endpoint computes a `view_mode` based on comparing the requested date to today's date (server-side, ET timezone).
**When to use:** Every response from `/games/{date}`.
**Example:**
```python
# Source: existing api/routes/games.py pattern
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def compute_view_mode(requested_date_str: str) -> str:
    """Determine rendering mode for the requested date.

    Returns one of: 'live', 'historical', 'tomorrow', 'future'
    """
    requested = date.fromisoformat(requested_date_str)
    today = datetime.now(ET).date()
    tomorrow = today + timedelta(days=1)

    if requested == today:
        return "live"
    elif requested < today:
        return "historical"
    elif requested == tomorrow:
        return "tomorrow"
    else:
        return "future"
```

### Pattern 2: Conditional Polling via refetchInterval
**What:** TanStack Query v5 supports `refetchInterval` as a callback function `(query) => number | false`. When the view_mode is not `'live'`, return `false` to disable polling.
**When to use:** In `useGames()` hook.
**Example:**
```typescript
// Source: TanStack Query v5 docs - useQuery reference
export function useGames(dateStr?: string) {
  const date = dateStr ?? todayDateStr();

  const query = useQuery({
    queryKey: ['games', date],
    queryFn: () => fetchJson<GamesDateResponse>(`/games/${date}`),
    staleTime: 55_000,
    // Only poll when viewing today (live mode)
    refetchInterval: (query) => {
      const viewMode = query.state.data?.view_mode;
      return viewMode === 'live' ? 60_000 : false;
    },
  });

  const games: GameResponse[] = query.data?.games ?? [];

  return {
    ...query,
    games,
    viewMode: query.data?.view_mode ?? null,
    generatedAt: query.data?.generated_at ?? null,
  };
}
```

### Pattern 3: DateNavigator Component
**What:** A controlled component with left arrow, date display/picker, and right arrow. Manages a `selectedDate` string state.
**When to use:** Rendered in the header/toolbar area of the dashboard.
**Example:**
```tsx
interface DateNavigatorProps {
  selectedDate: string;  // YYYY-MM-DD
  onDateChange: (date: string) => void;
}

export function DateNavigator({ selectedDate, onDateChange }: DateNavigatorProps) {
  const goToPreviousDay = () => {
    const d = new Date(selectedDate + 'T12:00:00');  // Noon to avoid TZ issues
    d.setDate(d.getDate() - 1);
    onDateChange(formatDate(d));
  };

  const goToNextDay = () => {
    const d = new Date(selectedDate + 'T12:00:00');
    d.setDate(d.getDate() + 1);
    onDateChange(formatDate(d));
  };

  return (
    <div className={styles.navigator}>
      <button onClick={goToPreviousDay} className={styles.arrow} aria-label="Previous day">
        &#8592;
      </button>
      <input
        type="date"
        value={selectedDate}
        onChange={(e) => onDateChange(e.target.value)}
        className={styles.datePicker}
      />
      <button onClick={goToNextDay} className={styles.arrow} aria-label="Next day">
        &#8593;
      </button>
    </div>
  );
}
```

### Pattern 4: Extending Schedule Fetch for Probable Pitchers
**What:** Add `hydrate=probablePitcher(note)` to the `statsapi.get('schedule', ...)` call for tomorrow's date to extract probable pitcher names.
**When to use:** When the requested date is tomorrow. Could also be applied to all dates for consistency.
**Example:**
```python
# Source: MLB-StatsAPI wrapper source code and MLB Stats API documentation
def fetch_schedule_for_date(date_str: str, include_pitchers: bool = False) -> list[dict]:
    """Fetch MLB schedule, optionally with probable pitcher data."""
    from datetime import datetime as _dt
    dt = _dt.strptime(date_str, "%Y-%m-%d")
    api_date = dt.strftime("%m/%d/%Y")

    params = {'sportId': 1, 'date': api_date}
    if include_pitchers:
        params['hydrate'] = 'probablePitcher(note)'

    data = statsapi.get('schedule', params)

    games = []
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            if game.get('gameType') != 'R':
                continue

            status = game.get('status', {})
            game_status = map_game_status(status)
            game_pk = game.get('gamePk')
            if game_pk is None:
                continue

            # Extract probable pitchers if hydrated
            home_pitcher = None
            away_pitcher = None
            if include_pitchers:
                home_pitcher = (game.get('teams', {}).get('home', {})
                               .get('probablePitcher', {}).get('fullName'))
                away_pitcher = (game.get('teams', {}).get('away', {})
                               .get('probablePitcher', {}).get('fullName'))

            games.append({
                'game_id': game_pk,
                'home_name': game['teams']['home']['team']['name'],
                'away_name': game['teams']['away']['team']['name'],
                'game_datetime': game.get('gameDate'),
                'game_status': game_status,
                'doubleheader': game.get('doubleHeader', 'N'),
                'game_num': game.get('gameNumber', 1),
                'home_probable_pitcher': home_pitcher,
                'away_probable_pitcher': away_pitcher,
            })

    return games
```

### Pattern 5: Tomorrow Preliminary Prediction Logic
**What:** For tomorrow's date, games where BOTH probable pitchers are confirmed (non-null from MLB API) get a `prediction_label: 'PRELIMINARY'` in `GameResponse`. Games without both SPs get `prediction_label: null` (schedule-only). No actual model prediction is run -- the "PRELIMINARY" label indicates that when game day arrives, this game will get an SP-enhanced prediction.
**When to use:** In the `/games/{date}` endpoint when `view_mode == 'tomorrow'`.
**Important note:** Per REQUIREMENTS.md, DATE-09 (running TEAM_ONLY model for tomorrow) is deferred to v2.3+. DATE-07 only shows SP names and a PRELIMINARY label -- it does NOT generate probability predictions for tomorrow.

### Anti-Patterns to Avoid
- **Client-side date comparison for view_mode:** The browser's Date() uses the user's local timezone, which may differ from ET. A user in Pacific time at 11pm would see a different "today" than the server. Compute view_mode server-side using ET.
- **Polling non-today dates:** Fetching /games/2026-03-28 (past) every 60s wastes API calls and DB queries. Past dates never change. Tomorrow/future dates change rarely. Only poll today.
- **Running predictions for tomorrow's games:** DATE-09 (TEAM_ONLY model for tomorrow) is explicitly deferred per REQUIREMENTS.md. DATE-07 only shows schedule + SP names as PRELIMINARY, not probability numbers.
- **Using third-party date picker library:** Native `<input type="date">` is sufficient for single-date selection. Adding a dependency for this is unnecessary complexity.
- **Constructing Date objects from YYYY-MM-DD without noon anchor:** `new Date('2026-04-01')` can be parsed as UTC midnight, which is March 31 in Western time zones. Always use `new Date('2026-04-01T12:00:00')` for date arithmetic to avoid off-by-one errors.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date picker UI | Custom calendar component | Native `<input type="date">` | Built into all modern browsers, handles locale, validation, accessibility |
| Date arithmetic | Manual month/year rollover logic | `Date.setDate()` (frontend) or `timedelta` (backend) | Edge cases (month boundaries, leap years) already handled |
| Conditional polling | Manual `setInterval` with cleanup | TanStack Query `refetchInterval` callback | Already integrated, handles mount/unmount cleanup, supports `false` to disable |
| Time zone handling | Client-side "is this today?" check | Server-side `view_mode` in response | Single source of truth, avoids TZ bugs |
| Probable pitcher extraction | Custom MLB API HTTP client | `statsapi.get('schedule', {'hydrate': 'probablePitcher(note)'})` | Already handles authentication, URL construction, error handling |

**Key insight:** Phase 14 adds no new dependencies. The existing stack (TanStack Query conditional polling, native HTML date input, Python datetime/zoneinfo, MLB-StatsAPI hydration) handles everything.

## Common Pitfalls

### Pitfall 1: Timezone Mismatch Between Client and Server for "Today"
**What goes wrong:** The client determines "today" using the user's local timezone. A user in PST at 11pm thinks it's still March 31, but the server (using ET) says it's April 1. The dashboard shows yesterday's data with live polling, or today's data without polling.
**Why it happens:** `new Date()` in the browser uses the system timezone. MLB games and the pipeline use ET.
**How to avoid:** The server computes `view_mode` based on ET date. The frontend passes the selected date string (YYYY-MM-DD) and trusts the server's `view_mode` field to determine polling and rendering behavior. The initial "today" in the DateNavigator uses the browser's local date (which is fine -- it's the user's perceived date), but the server decides whether that date gets live treatment.
**Warning signs:** Polling continuing after midnight ET when viewing "today"; past dates showing as live.

### Pitfall 2: Date Parsing Off-by-One with new Date()
**What goes wrong:** `new Date('2026-04-01')` in JavaScript is parsed as UTC midnight (April 1, 00:00 UTC), which is March 31 in all US time zones. Using `.toLocaleDateString()` or `getDate()` gives the wrong day.
**Why it happens:** ECMA-262 specifies that date-only strings are parsed as UTC, not local time.
**How to avoid:** Always add a time component when doing date arithmetic: `new Date('2026-04-01T12:00:00')`. Or use string manipulation for day increment: split YYYY-MM-DD, create Date with year/month/day constructor, add day, format back.
**Warning signs:** Arrow navigation skipping dates or showing wrong date labels near midnight.

### Pitfall 3: Cache Entry Explosion with Date Navigation
**What goes wrong:** Users clicking through many dates rapidly fill the in-memory schedule cache. The `_CACHE_MAX_ENTRIES = 7` guard was set in Phase 13, but aggressive navigation could cause thrashing (evicting today's cache entry to load a future date, then re-fetching today).
**Why it happens:** Each unique date gets its own cache entry. If the user clicks through 10 dates quickly, 7 entries are the max but today's may be evicted.
**How to avoid:** The existing max-entries guard (7) with LRU eviction handles this. Today's date is re-fetched frequently (every 60s poll), so it stays warm. Optionally: increase max entries to 14, or pin today's entry so it's never evicted. The current implementation is likely fine.
**Warning signs:** Excessive MLB API calls when navigating dates; slow response when returning to today after browsing.

### Pitfall 4: Stale "Today" After Midnight
**What goes wrong:** User opens the dashboard at 11pm ET, leaves it open. At midnight, "today" changes but the DateNavigator still shows yesterday's date with live polling. The user sees stale data and the polling fetches yesterday's games (which are now all Final).
**Why it happens:** The `todayDateStr()` function is called once when the component mounts. It doesn't update at midnight.
**How to avoid:** Two options: (1) When the server returns `view_mode: 'historical'` for what the client thought was today, show a "Date has changed" banner prompting refresh. (2) Add a midnight-crossing check in the useEasternClock hook that triggers a date re-evaluation. Option 1 is simpler and sufficient.
**Warning signs:** Dashboard showing yesterday's completed games after midnight with no indication that the date has rolled over.

### Pitfall 5: Empty Pitcher Data for Tomorrow Misinterpreted
**What goes wrong:** MLB Stats API returns `probablePitcher: {}` or no `probablePitcher` key at all for games where the pitcher is TBD. Code checks `pitcher.get('fullName')` which returns `None`, correctly marking the game as schedule-only. But some games have a `probablePitcher` with `fullName: "TBD"` string.
**Why it happens:** MLB API is inconsistent with how it represents "no pitcher assigned" vs "pitcher explicitly TBD".
**How to avoid:** Check for `None`, empty string, and the literal string "TBD" when determining if a pitcher is confirmed: `if name and name.strip() and name.strip().upper() != 'TBD'`. This matches the normalization pattern already used in `fetch_today_schedule()`.
**Warning signs:** Games with "TBD" SP showing as PRELIMINARY when they should be schedule-only.

### Pitfall 6: Styling Native Date Input for Dark Theme
**What goes wrong:** The native `<input type="date">` uses the browser's default light theme styling -- white background, default system font, light dropdown calendar. Looks terrible against the dark dashboard.
**Why it happens:** Native date inputs have limited CSS customization, especially the calendar dropdown (which is a shadow DOM element).
**How to avoid:** Apply `color-scheme: dark` to the input (modern browsers respect this for form controls). Add explicit background, color, border, and font-family CSS. The calendar dropdown will follow the dark scheme. Test in Chrome, Firefox, and Safari.
**Warning signs:** Bright white date picker against dark background; unreadable text in dropdown.

## Code Examples

### GamesDateResponse with view_mode
```python
# Source: extending existing api/models.py
class GamesDateResponse(BaseModel):
    """Response shape for GET /games/{date}."""
    games: list[GameResponse]
    generated_at: datetime
    view_mode: Literal['live', 'historical', 'tomorrow', 'future']
```

### GameResponse with prediction_label
```python
# Source: extending existing api/models.py
class GameResponse(BaseModel):
    """Single game entry for the /games/{date} endpoint."""
    game_id: int
    home_team: str
    away_team: str
    game_time: datetime | None
    game_status: Literal['PRE_GAME', 'LIVE', 'FINAL', 'POSTPONED']
    prediction: PredictionGroup | None = None
    prediction_label: Literal['PRELIMINARY'] | None = None  # DATE-07: tomorrow confirmed-SP games
    home_probable_pitcher: str | None = None  # For tomorrow/future display
    away_probable_pitcher: str | None = None  # For tomorrow/future display
```

### TypeScript Types Update
```typescript
// Source: extending existing frontend/src/api/types.ts
export type ViewMode = 'live' | 'historical' | 'tomorrow' | 'future';

export interface GameResponse {
  game_id: number;
  home_team: string;
  away_team: string;
  game_time: string | null;
  game_status: GameStatus;
  prediction: PredictionGroup | null;
  prediction_label: 'PRELIMINARY' | null;
  home_probable_pitcher: string | null;
  away_probable_pitcher: string | null;
}

export interface GamesDateResponse {
  games: GameResponse[];
  generated_at: string;
  view_mode: ViewMode;
}
```

### DateNavigator CSS (Dark Theme)
```css
/* Source: following existing design system from index.css */
.navigator {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) 0;
}

.arrow {
  background: none;
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  font-size: 18px;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s;
}

.arrow:hover {
  border-color: var(--color-accent);
}

.datePicker {
  font-family: var(--font-data);
  font-size: 14px;
  color: var(--color-text-primary);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: var(--space-xs) var(--space-sm);
  color-scheme: dark;
}
```

### Server-Side Tomorrow Logic
```python
# Source: new logic in api/routes/games.py for DATE-07
from datetime import timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def _is_pitcher_confirmed(name: str | None) -> bool:
    """Check if a probable pitcher name is a real confirmed name (not TBD/null)."""
    if not name:
        return False
    stripped = name.strip()
    return bool(stripped) and stripped.upper() != 'TBD'

def _apply_tomorrow_labels(games: list[GameResponse], schedule: list[dict]) -> None:
    """For tomorrow view_mode, mark games with both SPs confirmed as PRELIMINARY."""
    schedule_lookup = {g['game_id']: g for g in schedule}
    for game_resp in games:
        sched = schedule_lookup.get(game_resp.game_id, {})
        home_sp = sched.get('home_probable_pitcher')
        away_sp = sched.get('away_probable_pitcher')
        if _is_pitcher_confirmed(home_sp) and _is_pitcher_confirmed(away_sp):
            game_resp.prediction_label = 'PRELIMINARY'
            game_resp.home_probable_pitcher = home_sp
            game_resp.away_probable_pitcher = away_sp
        else:
            game_resp.home_probable_pitcher = home_sp if _is_pitcher_confirmed(home_sp) else None
            game_resp.away_probable_pitcher = away_sp if _is_pitcher_confirmed(away_sp) else None
```

### Conditional Polling in useGames
```typescript
// Source: TanStack Query v5 useQuery docs
export function useGames(dateStr?: string) {
  const date = dateStr ?? todayDateStr();

  const query = useQuery({
    queryKey: ['games', date],
    queryFn: () => fetchJson<GamesDateResponse>(`/games/${date}`),
    staleTime: 55_000,
    refetchInterval: (query) => {
      const viewMode = query.state.data?.view_mode;
      return viewMode === 'live' ? 60_000 : false;
    },
  });

  const games: GameResponse[] = query.data?.games ?? [];

  return {
    ...query,
    games,
    viewMode: query.data?.view_mode ?? null,
    generatedAt: query.data?.generated_at ?? null,
  };
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dashboard always shows today, always polls | Date navigation with conditional polling | Phase 14 | Past dates don't poll; reduces unnecessary API calls |
| `useGames()` always uses `todayDateStr()` | `useGames(selectedDate)` with date param | Phase 14 | Dashboard can show any date |
| `fetch_schedule_for_date()` without pitcher hydration | `hydrate=probablePitcher(note)` for tomorrow | Phase 14 | Enables DATE-07 PRELIMINARY label |
| No view_mode in API response | `view_mode` field in `GamesDateResponse` | Phase 14 | Frontend knows rendering context without date math |

**Deprecated/outdated:**
- Nothing deprecated. Phase 14 extends existing patterns without removing anything.

## Open Questions

1. **Where should DateNavigator be placed visually?**
   - What we know: The Header component currently has a clock row showing the date and time. The DateNavigator could replace the date display in the clock row, or sit as a separate row below the header.
   - What's unclear: Exact visual placement -- alongside clock, below header, or as a sub-header bar.
   - Recommendation: Place it between the Header and AccuracyStrip, as its own row. The existing clock row continues to show "real" current date/time, while the DateNavigator shows the "selected" date for viewing. This avoids confusing the user about what today actually is.

2. **Should "Today" button be included?**
   - What we know: DATE-01 through DATE-03 specify arrow and date picker controls. No "Today" button is in the requirements.
   - What's unclear: Whether a convenience "Today" shortcut is worth adding.
   - Recommendation: Add a "Today" button between the arrows and date picker. It's a one-line addition and greatly improves UX when the user has navigated far from today. This is a minor enhancement that doesn't conflict with requirements.

3. **Cache TTL differentiation by view_mode?**
   - What we know: Current cache TTL is 75s for all dates. Past dates never change (their schedule is final). Tomorrow/future dates change slowly.
   - What's unclear: Whether to use different TTLs per date category.
   - Recommendation: Keep 75s TTL for all dates for simplicity. Past dates hit the cache and rarely get evicted. The overhead of a more complex caching strategy isn't justified given the 7-entry max and low traffic.

4. **EmptyState text for non-today dates**
   - What we know: Current EmptyState says "No games scheduled today". This is wrong when viewing a past or future date.
   - What's unclear: Exact copy for each scenario.
   - Recommendation: Pass the `view_mode` and `selectedDate` to EmptyState and render contextually: "No games scheduled for [date]" for historical, "No games scheduled for tomorrow" for tomorrow, etc.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml) + TypeScript compiler |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_api/test_games.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATE-01 | Left arrow navigates to previous day | manual (browser) | N/A -- UI interaction test | N/A |
| DATE-02 | Right arrow navigates to next day | manual (browser) | N/A -- UI interaction test | N/A |
| DATE-03 | Date picker jumps to specific date | manual (browser) | N/A -- UI interaction test | N/A |
| DATE-04 | Default date is today | unit | `pytest tests/test_api/test_games.py::TestDateNavigation::test_default_view_mode_today -x` | No -- Wave 0 |
| DATE-05 | Past date returns historical predictions, view_mode='historical' | unit (mocked) | `pytest tests/test_api/test_games.py::TestDateNavigation::test_past_date_view_mode -x` | No -- Wave 0 |
| DATE-06 | Today returns view_mode='live' | unit (mocked) | `pytest tests/test_api/test_games.py::TestDateNavigation::test_today_view_mode_live -x` | No -- Wave 0 |
| DATE-07 | Tomorrow with both SPs returns PRELIMINARY label | unit (mocked) | `pytest tests/test_api/test_games.py::TestTomorrowPreliminary::test_both_sps_confirmed_preliminary -x` | No -- Wave 0 |
| DATE-07 | Tomorrow with missing SP returns no label (schedule-only) | unit (mocked) | `pytest tests/test_api/test_games.py::TestTomorrowPreliminary::test_missing_sp_no_label -x` | No -- Wave 0 |
| DATE-08 | Future date returns view_mode='future', no predictions | unit (mocked) | `pytest tests/test_api/test_games.py::TestDateNavigation::test_future_date_view_mode -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_api/test_games.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api/test_games.py::TestDateNavigation` -- covers DATE-04, DATE-05, DATE-06, DATE-08 (view_mode computation tests)
- [ ] `tests/test_api/test_games.py::TestTomorrowPreliminary` -- covers DATE-07 (tomorrow pitcher confirmation and PRELIMINARY label logic)
- [ ] Frontend: `npx tsc --noEmit` in frontend/ -- type-level verification of new types and component props

*(DATE-01, DATE-02, DATE-03 are UI interaction requirements -- verified by manual browser testing, not automated unit tests)*

## Sources

### Primary (HIGH confidence)
- **Existing codebase** -- `api/routes/games.py`, `api/models.py`, `src/data/mlb_schedule.py`, `frontend/src/hooks/useGames.ts`, `frontend/src/App.tsx`, `frontend/src/components/GameCard.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/api/types.ts` -- all read and analyzed in full
- **Phase 13 VERIFICATION.md** -- Confirmed all Phase 13 artifacts are in place; `/games/{date}` endpoint fully functional with date parameter
- **Phase 13 RESEARCH.md** -- Status mapping, cache architecture, merge logic patterns all verified and in production
- **TanStack Query v5 useQuery reference** -- `refetchInterval` accepts `(query) => number | false` callback for conditional polling: [useQuery docs](https://tanstack.com/query/v5/docs/framework/react/reference/useQuery)
- **MLB-StatsAPI source code** -- `statsapi.schedule()` uses `hydrate=probablePitcher(note)` and extracts `game["teams"]["home"]["probablePitcher"]["fullName"]`: [GitHub](https://github.com/toddrob99/MLB-StatsAPI/blob/master/statsapi/__init__.py)

### Secondary (MEDIUM confidence)
- **MLB Stats API hydrate=probablePitcher** -- URL pattern verified from public API usage: `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=...&hydrate=probablePitcher(note)` -- returns `probablePitcher.fullName` in teams structure
- **Native HTML date input dark theme** -- `color-scheme: dark` property on `<input type="date">` supported in Chrome 81+, Firefox 96+, Safari 15.4+ for dark form controls

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already installed and in use; no new dependencies
- Architecture: HIGH -- Extends existing patterns (server-side view_mode, conditional polling, GameResponse extensions); minimal new concepts
- Pitfalls: HIGH -- Date parsing, timezone, cache concerns all verified against existing code and MDN/TanStack docs
- Tomorrow SP logic: HIGH -- `hydrate=probablePitcher(note)` verified in MLB-StatsAPI wrapper source code; extraction path confirmed

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable -- no fast-moving dependencies)
