---
phase: 15-live-score-polling
verified: 2026-04-01T00:00:00Z
status: passed
score: "14/14 must-haves verified"
re_verification: false
---

# Phase 15: Live Score Polling Verification Report

**Phase Goal:** Users see real-time game progress on in-progress cards and the system automatically records outcomes when games finish.
**Verified:** 2026-04-01
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LiveScoreData Pydantic model exists with 14 typed fields (away_score, home_score, inning, inning_half, outs, balls, strikes, runner_on_1b, runner_on_2b, runner_on_3b, current_batter, batter_avg, batter_ops, on_deck_batter) | VERIFIED | `api/models.py` lines 75-92: `class LiveScoreData(BaseModel)` with all 14 fields typed (`int`, `Literal['top', 'bottom']`, `bool`, `str | None`) |
| 2 | GameResponse has an optional live_score field of type LiveScoreData | VERIFIED | `api/models.py` line 106: `live_score: LiveScoreData | None = None` inside `class GameResponse(BaseModel)` |
| 3 | get_linescore_cached() uses a thread-safe dict+Lock cache with 90s TTL and 20-entry max | VERIFIED | `src/data/mlb_schedule.py` lines 283-284: `_linescore_cache: dict[int, tuple[float, dict]] = {}` and `_linescore_lock = threading.Lock()`; line 285: `_LINESCORE_TTL = 90`; line 286: `_LINESCORE_MAX_ENTRIES = 20`; lines 303-306: cache check inside `with _linescore_lock:` |
| 4 | parse_linescore() extracts live game state from raw MLB API response | VERIFIED | `src/data/mlb_schedule.py` lines 335-419: `def parse_linescore(raw: dict) -> dict | None:` extracts score, inning, runners, batter, on-deck from liveData.linescore and boxscore sections |
| 5 | statsapi.get('game') uses fields parameter to reduce response size | VERIFIED | `src/data/mlb_schedule.py` lines 311-319: `statsapi.get('game', {'gamePk': game_id, 'fields': ('liveData,linescore,currentInning,...')})` specifying exactly which fields to return |
| 6 | In-progress game cards display current score and inning (ScoreRow component) | VERIFIED | `frontend/src/components/GameCard.tsx` lines 107-136: `{game_status === 'LIVE' && game.live_score && (` renders ScoreRow div with `away_team {game.live_score.away_score} - {home_team} {game.live_score.home_score}` and `formatInningHalf` + `formatInningOrdinal` + outs |
| 7 | Dashboard polls live game data every 90 seconds only when hasLiveGames AND view_mode is 'live' (dual gate) | VERIFIED | `frontend/src/hooks/useGames.ts` lines 21-28: `refetchInterval: (query) => { const viewMode = query.state.data?.view_mode; if (viewMode !== 'live') return false; const hasLiveGames = query.state.data?.games?.some((g: GameResponse) => g.game_status === 'LIVE'); return hasLiveGames ? 90_000 : false; }` |
| 8 | User can expand an in-progress card (ScoreRow has expand/collapse via useState) | VERIFIED | `frontend/src/components/GameCard.tsx` line 43: `const [expanded, setExpanded] = useState(false);`; lines 109-120: scoreRow div with `role="button"`, `aria-expanded={expanded}`, `onClick={() => setExpanded(prev => !prev)}`, and Enter/Space keyboard handlers |
| 9 | Expanded card shows BasesDiamond SVG with amber-highlighted runners | VERIFIED | `frontend/src/components/BasesDiamond.tsx` lines 16-50: `export function BasesDiamond` renders SVG with `viewBox="0 0 80 80"`, `role="img"`; line 17: `const occupied = '#F59E0B';` (amber); lines 36-37: `fill={runner_on_1b ? occupied : empty}` for each base |
| 10 | Expanded card shows pitch count (balls/strikes/outs) | VERIFIED | `frontend/src/components/LiveDetail.tsx` lines 20-22: `<div className={styles.countRow}> B: {liveScore.balls}  S: {liveScore.strikes}  O: {liveScore.outs}` |
| 11 | Expanded card shows current batter name and stats | VERIFIED | `frontend/src/components/LiveDetail.tsx` lines 23-31: `<span className={styles.batterName}>{liveScore.current_batter ?? '--'}</span>` and `{liveScore.batter_avg} / {liveScore.batter_ops ?? '--'}` |
| 12 | Expanded card shows on-deck batter name | VERIFIED | `frontend/src/components/LiveDetail.tsx` lines 33-37: `{liveScore.on_deck_batter && (<div className={styles.batterRow}><span className={styles.onDeckLabel}>On deck:</span><span className={styles.onDeckName}>{liveScore.on_deck_batter}</span>` |
| 13 | write_game_outcome() writes actual_winner and prediction_correct to predictions table | VERIFIED | `src/pipeline/db.py` lines 169-207: `def write_game_outcome(pool, game_id, home_team, away_team, home_score, away_score)` computes `actual_winner = home_team if home_score > away_score else away_team` then executes UPDATE setting actual_winner, prediction_correct, reconciled_at WHERE `game_id = %(game_id)s AND actual_winner IS NULL` |
| 14 | live_poller_job detects Final transition and calls write_game_outcome | VERIFIED | `src/pipeline/scheduler.py` lines 73-137: `def live_poller_job(pool)` fetches schedule, filters `game_status == 'FINAL'`, fetches linescore data per game via `statsapi.get('game', ...)`, extracts home/away scores, calls `write_game_outcome(pool, game_id, home_team, away_team, home_score, away_score)` at line 131 |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/models.py` | LiveScoreData class with 14 fields, GameResponse.live_score Optional field | VERIFIED | Lines 75-92: LiveScoreData with 14 typed fields; line 106: `live_score: LiveScoreData | None = None` |
| `src/data/mlb_schedule.py` | get_linescore_cached(), parse_linescore(), _linescore_cache dict, _linescore_lock Lock | VERIFIED | Lines 283-332: cache infrastructure (dict, Lock, TTL=90, max=20, get_linescore_cached); lines 335-419: parse_linescore |
| `api/routes/games.py` | Live score enrichment in build_games_response | VERIFIED | Lines 262-267: `if game_status == 'LIVE' and view_mode == 'live':` calls `get_linescore_cached(game_id)` then `parse_linescore(raw)` then creates `LiveScoreData(**parsed)` |
| `src/pipeline/db.py` | write_game_outcome() function | VERIFIED | Lines 169-207: Full implementation with actual_winner computation, UPDATE SQL, rowcount return, WHERE actual_winner IS NULL guard |
| `src/pipeline/scheduler.py` | live_poller_job with IntervalTrigger | VERIFIED | Lines 73-137: `live_poller_job(pool)` function; lines 199-207: registered with `IntervalTrigger(seconds=90)`, `max_instances=1`, `misfire_grace_time=30` |
| `frontend/src/api/types.ts` | LiveScoreData TypeScript interface | VERIFIED | Lines 57-72: `export interface LiveScoreData` with all 14 fields typed; line 84: `live_score: LiveScoreData | null` on GameResponse |
| `frontend/src/hooks/useGames.ts` | 90s dual-gate polling (hasLiveGames + viewMode === 'live') | VERIFIED | Lines 21-28: refetchInterval callback checks `viewMode !== 'live'` first, then `hasLiveGames` via `.some(g => g.game_status === 'LIVE')`, returns `90_000` only when both gates pass |
| `frontend/src/components/GameCard.tsx` | ScoreRow, expand/collapse logic, conditional render on game_status === 'LIVE' | VERIFIED | Line 107: `{game_status === 'LIVE' && game.live_score && (` gates entire scoreRow; line 43: useState; lines 109-120: expand/collapse with aria attributes; line 134: `{expanded && <LiveDetail ...>}` |
| `frontend/src/components/BasesDiamond.tsx` | SVG diamond with runner_on_1b/2b/3b highlighting | VERIFIED | Lines 1-50: Full SVG component with boolean props, amber fill (`#F59E0B`), `role="img"`, `aria-label` via describeRunners helper |
| `tests/test_api/test_games_live.py` | 12 tests for parse_linescore and get_linescore_cached | VERIFIED | 10 TestParseLinescore tests (lines 91-163) + 2 TestGetLinescoreCached tests (lines 166-186) = 12 tests total |
| `tests/test_pipeline/test_live_poller.py` | 8 tests for write_game_outcome and live_poller_job | VERIFIED | 4 TestWriteGameOutcome tests (lines 17-59) + 4 TestLivePollerJob tests (lines 62-124) = 8 tests total |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/data/mlb_schedule.py` parse_linescore | LiveScoreData model fields | parse_linescore returns dict with same 14 keys as LiveScoreData field names | WIRED | mlb_schedule.py lines 404-419 return dict with keys (away_score, home_score, inning, inning_half, outs, balls, strikes, runner_on_1b/2b/3b, current_batter, batter_avg, batter_ops, on_deck_batter) matching models.py lines 78-92 |
| `api/routes/games.py` route handler | get_linescore_cached per LIVE game -> GameResponse.live_score | build_games_response calls cache then parser then creates LiveScoreData | WIRED | games.py line 24: `from src.data.mlb_schedule import get_linescore_cached, ..., parse_linescore`; lines 262-267: conditional enrichment for LIVE + live view_mode |
| `src/pipeline/scheduler.py` live_poller_job | write_game_outcome on Final transition | Poller detects FINAL games, fetches scores, calls write_game_outcome | WIRED | scheduler.py line 24: `from src.pipeline.db import reconcile_outcomes, write_game_outcome`; line 131: `count = write_game_outcome(pool, game_id, home_team, away_team, home_score, away_score)` |
| `frontend/src/hooks/useGames.ts` refetchInterval | hasLiveGames + viewMode dual gate | Callback reads view_mode and game_status from query.state.data | WIRED | useGames.ts lines 21-28: `refetchInterval: (query) => { const viewMode = query.state.data?.view_mode; if (viewMode !== 'live') return false; ... return hasLiveGames ? 90_000 : false; }` |
| `frontend/src/components/GameCard.tsx` | game.live_score -> ScoreRow/LiveDetail/BasesDiamond | GameCard renders live data via conditional chain | WIRED | GameCard.tsx line 107: LIVE gate; line 134: `{expanded && <LiveDetail liveScore={game.live_score} />}`; LiveDetail.tsx line 13: `<BasesDiamond runner_on_1b=... runner_on_2b=... runner_on_3b=.../>` |
| `frontend/src/App.tsx` | GameCardGrid -> GameCard with viewMode prop | App passes viewMode from useGames to GameCard via grid | WIRED | GameCard.tsx line 38: `interface GameCardProps { game: GameResponse; viewMode: ViewMode | null; }` accepts viewMode prop from parent |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LIVE-01 | 15-01, 15-03 | Score + inning on in-progress card | SATISFIED | ScoreRow in GameCard.tsx lines 122-128: renders `away_team {away_score} - {home_team} {home_score}` with `formatInningHalf(inning_half)` + `formatInningOrdinal(inning)` + `{outs} out`; LiveScoreData model has home_score, away_score, inning, inning_half fields |
| LIVE-02 | 15-03 | 90s polling gate -- only when hasLiveGames AND viewMode is 'live' | SATISFIED | useGames.ts lines 21-28: refetchInterval callback first checks `viewMode !== 'live'` (returns false), then checks `hasLiveGames` via `games.some(g => g.game_status === 'LIVE')`, returns `90_000` only when both pass; false otherwise |
| LIVE-03 | 15-03 | Expand in-progress card for detailed live state | SATISFIED | GameCard.tsx line 43: `const [expanded, setExpanded] = useState(false)`; lines 109-120: scoreRow div with `role="button"`, `tabIndex={0}`, `aria-expanded`, onClick/onKeyDown handlers; line 134: `{expanded && <LiveDetail liveScore={game.live_score} />}` |
| LIVE-04 | 15-01, 15-03 | Bases diamond with runners highlighted | SATISFIED | BasesDiamond.tsx lines 16-50: SVG with 3 base rects, `fill={runner_on_Nb ? occupied : empty}` where occupied = `'#F59E0B'` (amber); `aria-label` via describeRunners helper; LiveDetail.tsx line 13: renders BasesDiamond with runner props |
| LIVE-05 | 15-01, 15-03 | Pitch count (balls/strikes/outs) in expanded view | SATISFIED | LiveDetail.tsx lines 20-22: `B: {liveScore.balls}  S: {liveScore.strikes}  O: {liveScore.outs}` in countRow div; parse_linescore extracts balls/strikes/outs from linescore |
| LIVE-06 | 15-01, 15-03 | Batter name and stats in expanded view | SATISFIED | LiveDetail.tsx lines 23-31: `{liveScore.current_batter ?? '--'}` and `{liveScore.batter_avg} / {liveScore.batter_ops ?? '--'}`; parse_linescore extracts batter from offense.batter.fullName and stats from boxscore via ID lookup |
| LIVE-07 | 15-01, 15-03 | On-deck batter name in expanded view | SATISFIED | LiveDetail.tsx lines 33-37: `{liveScore.on_deck_batter && (...<span>{liveScore.on_deck_batter}</span>...)}`; parse_linescore extracts from offense.onDeck.fullName |
| LIVE-08 | 15-02 | Final transition writes actual_winner + prediction_correct | SATISFIED | write_game_outcome in db.py lines 169-207: UPDATE predictions SET actual_winner, prediction_correct, reconciled_at WHERE game_id AND actual_winner IS NULL; live_poller_job in scheduler.py lines 73-137: detects FINAL games, fetches scores, calls write_game_outcome; IntervalTrigger(seconds=90) at line 201 |

All 8 requirements fully satisfied. No orphaned requirements.

### Anti-Patterns Found

No blockers or warnings detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | -- | -- | -- | -- |

Scan covered: api/models.py, src/data/mlb_schedule.py, api/routes/games.py, src/pipeline/db.py, src/pipeline/scheduler.py, frontend TypeScript files (types.ts, useGames.ts, GameCard.tsx, BasesDiamond.tsx, LiveDetail.tsx). No TODO/FIXME/PLACEHOLDER comments found in Phase 15 code. No stub implementations.

### Human Verification Required

The following behaviors require visual or browser-level confirmation and cannot be verified programmatically:

#### 1. Live Score Row Visual Rendering

**Test:** Open the dashboard in a browser during a game with LIVE status. Verify the ScoreRow appears between the header and prediction body.
**Expected:** Amber-tinted background row showing "AWAY 3 - HOME 1 . Top 7th . 2 out" with expand chevron.
**Why human:** CSS class rendering (scoreRow with amber tint) requires visual inspection.

#### 2. BasesDiamond Amber Fill

**Test:** Expand a LIVE game card when runners are on base.
**Expected:** Diamond SVG shows amber-filled squares for occupied bases and hollow squares for empty bases.
**Why human:** SVG fill color (#F59E0B) rendering requires visual confirmation.

#### 3. Expand/Collapse Interaction

**Test:** Click on a LIVE ScoreRow, then click again.
**Expected:** First click expands to show LiveDetail (diamond, count, batter info); second click collapses it. Enter/Space keys also work.
**Why human:** Interactive behavior and animation cannot be verified through code analysis alone.

#### 4. 90s Polling Cadence

**Test:** Open browser dev tools Network tab while LIVE games are present on today's dashboard.
**Expected:** /games/{date} requests fire every 90 seconds. When no LIVE games exist, polling stops.
**Why human:** Requires real-time network monitoring with actual LIVE games in progress.

### Gaps Summary

None. All 14 observable truths are verified, all 11 artifacts confirmed (exists, substantive, wired), all 6 key links are confirmed wired, all 8 requirements (LIVE-01 through LIVE-08) are fully satisfied.

Test evidence:
- `tests/test_api/test_games_live.py` -- 12 tests (10 parse_linescore + 2 cache)
- `tests/test_pipeline/test_live_poller.py` -- 8 tests (4 write_game_outcome + 4 live_poller_job)
- Phase 15 implementation commits: 84b9127, 997f42f, fbb76c0, b32b6c0, 6b59381, c537aac

---

_Verified: 2026-04-01_
_Verifier: Claude (gsd-executor)_
