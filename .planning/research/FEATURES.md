# Feature Landscape

**Domain:** MLB win probability dashboard -- game lifecycle, live scores, date navigation, historical accuracy
**Researched:** 2026-03-30
**Milestone:** v2.2 Game Lifecycle, Live Scores & Historical Accuracy

## Table Stakes

Features users expect from a sports prediction dashboard that tracks games through their full lifecycle. Missing any of these makes the product feel broken or abandoned mid-day.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| All-day game visibility | Games currently vanish once in-progress or Final; users navigating after first pitch see an empty dashboard | Low | Root cause: `/predictions/today` API only returns rows for today's predictions, not all scheduled games. Fix: merge schedule data with predictions so every game_date game appears regardless of game status. |
| Game status indicator on card | Users need to know at a glance whether a game is Pre-Game, In Progress, or Final | Low | MLB Stats API `abstractGameState` returns exactly these three values. Map to visual badges: "Pre-Game" (default), green pulse dot + "Live" (in-progress), checkered flag + "FINAL" (complete). |
| Live score on in-progress cards | Every sports scoreboard (ESPN, MLB.com, FanGraphs, Yahoo) shows score + inning as primary information during a live game | Medium | MLB Stats API `schedule?hydrate=linescore` returns score, currentInning, inningState, outs inline. Poll every 90s server-side. Score supersedes prediction probabilities as the visual hero once a game goes live. |
| Final score on completed cards | After a game ends, users must see who won and the final score | Low | Same linescore data. When `abstractGameState === 'Final'`, show "FINAL" badge + score. Freeze card state -- no more polling for this game. |
| Prediction outcome marker | The entire point of a prediction tool is to show "was it right?" | Low | Compare predicted home_win (ensemble_prob > 0.5) against actual winner. Show green checkmark or red X. This is the moment that builds or erodes user trust in the model. |
| Date navigation: today + past dates | Users return next day wanting to see yesterday's results. ESPN, MLB.com, FanGraphs all have left/right arrows + date display as primary navigation. | Medium | Arrow buttons flanking current date + optional calendar picker for jump-to-date. Past dates load from Postgres (predictions + actual outcomes). Keep navigation range within current season. |
| Inning display format | Baseball convention: "Top 5th", "Bot 7th", "Mid 3rd". Users expect the standard ordinal + half format. | Low | MLB API provides `currentInningOrdinal` ("5th") and `inningHalf` ("Top"/"Middle"/"Bottom"). Display as "T5" / "B7" in compact view, "Top 5th" in expanded. |

## Differentiators

Features that set this dashboard apart from generic scoreboards. Not expected but valued, because they bridge the gap between "scoreboard" and "prediction analytics tool."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Bases diamond on live cards | Visual baseball literacy -- a 3-diamond SVG showing occupied bases is instantly recognizable to any baseball fan. ESPN, Baseball Savant, FanGraphs all show this. | Low | Implement as a pure SVG/CSS component: 3 rotated squares at 1st/2nd/3rd positions. `offense.first`, `offense.second`, `offense.third` present in MLB Stats API linescore when runners are on base (verified against live game data 2026-03-30). Amber fill for occupied, dark for empty -- matches existing design tokens. Total: ~30 lines of TSX + CSS. |
| Expanded live card (pitcher/batter/count) | Power users want to see the current pitcher, current batter, ball-strike count, and outs without leaving the dashboard. FanGraphs scoreboard offers this in its expanded card view. | Medium | Data available from MLB Stats API `offense.batter.fullName`, `defense.pitcher.fullName`, `balls`, `strikes`, `outs`. Implement as a collapsible section below the score row, collapsed by default. Uses existing `<details>/<summary>` pattern from AboutModels. |
| Tomorrow's preliminary predictions | Shows the model's "best guess" before game day, giving users a reason to visit the night before. FanGraphs Game Odds publishes next-day odds once probable pitchers are posted. | Medium | Run a 9pm ET "preview" pipeline fetching tomorrow's probable pitchers from MLB Stats API. Where SP is confirmed, run SP_ENHANCED model. Where SP is TBD, run TEAM_ONLY model. Prominently label as "PRELIMINARY" with visual uncertainty treatment (dashed border, muted colors, "SP not confirmed" caveat). |
| History page with rolling accuracy chart | Proves the model works over time. The single most important trust-building feature for a prediction product. No competitor in the hobbyist/analytics space does this well. | High | Date range picker + table of predictions vs actuals + rolling accuracy line chart (Recharts). Key metrics: win rate by model, Brier score trend, edge signal hit rate. This is the feature that separates a "dashboard" from an "analytics platform." |
| Prediction vs actual overlay on final cards | On a completed game card, show the pre-game probability alongside the actual outcome. "Model said 62% home win; home won." This is more informative than a bare checkmark. | Low | Already have ensemble_prob. After writing actual_winner to Postgres, display both on the card. Consider a simple bar or pill visualization: amber bar at 62% with green "W" or red "L" endpoint. |
| Future-date schedule-only mode | Users checking "what's on Friday?" should see the schedule even if no predictions exist yet. | Low | For dates >tomorrow with no predictions: show schedule grid (teams, game time, probable pitchers if known) with "Predictions available on game day" placeholder. Reuse existing card layout minus prediction body. |
| Nightly reconciliation job | Safety net for games the live poller missed (server restart, API hiccup). Runs at 2am ET, checks all games from yesterday, fills in any missing actual_winner values. | Medium | Cron-style APScheduler job. Query MLB Stats API for yesterday's final scores, UPDATE predictions SET actual_winner, prediction_correct WHERE reconciled_at IS NULL. Idempotent -- safe to re-run. |

## Anti-Features

Features to explicitly NOT build. Each has been considered and rejected for specific reasons.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| In-game win probability updates | OUT OF SCOPE per PROJECT.md. Mid-game state modeling (base-out, leverage, bullpen fatigue) is a fundamentally different problem from pre-game prediction. Building this would require new models, new training data, and new evaluation metrics. | Keep pre-game probabilities frozen once game starts. The prediction was made pre-game; showing it change mid-game would mislead users about what the model actually does. |
| Full line score (inning-by-inning grid) | Duplicates ESPN/MLB.com/Baseball Reference. This dashboard is not a scoreboard -- it is a prediction tool that shows enough game state for context. Adding a 9-inning grid per card bloats the card layout and dilutes focus from the prediction. | Show current score + inning only. Link out to ESPN/MLB.com for full line score if users want it. |
| Pitch-by-pitch play log | Way too much data for a prediction dashboard. FanGraphs has play logs; this tool does not need them. | Show "last play" text (one sentence) at most, but even that is optional for v2.2. |
| WebSocket real-time push | CLIENT-SIDE POLLING IS SUFFICIENT per PROJECT.md Key Decision. WebSocket infrastructure adds server complexity (connection management, reconnection, load balancing) for marginal UX improvement over 90s polling. At this user scale, polling is correct. | 90s client-side polling for live games, 60s for predictions (existing). Both visibilityState-gated. |
| Historical backfill of predictions | Tempting to show "what would the model have predicted last week?" but this is simulated data, not real predictions. Displaying backtested results as if they were live predictions is dishonest. | History page only shows predictions that were actually generated by the live pipeline. Start date = first day the pipeline ran (Opening Day 2026). |
| Animated base-running or play visualization | Fun but massive scope creep. SVG animation, play-by-play event parsing, edge cases (double plays, pickoffs, errors). | Static bases diamond: 3 squares, filled or empty. Updated each poll cycle. |
| Team logos on game cards | Requires licensing consideration, asset management, and fallback handling for 30 teams. Adds visual clutter that competes with the prediction data. | Team abbreviations (NYY, LAD, etc.) are sufficient and match the existing card aesthetic. Consider adding later if there is user demand. |
| Automatic calendar date jumping based on game state | Some apps auto-advance to tomorrow when all games are Final. This is disorienting -- the user chose to look at today's results. | Always stay on the date the user selected. Never auto-navigate. Show a subtle "All games final" indicator instead. |
| Infinite scroll history | Pagination with date range filters is clearer for analytics data. Infinite scroll obscures data boundaries and makes it hard to reference specific date ranges. | Date range picker (start/end) with paginated table. Default to last 7 days. |
| Complex charting library (D3/Victory/etc.) | Recharts is sufficient for a single rolling-accuracy line chart. D3 is powerful but adds unnecessary complexity and bundle size for this use case. | Use Recharts (~45KB gzipped) for the history page chart. If charting needs grow in v3+, reassess then. |

## Feature Dependencies

```
Game visibility fix --> Live score display (can't show score on cards that aren't rendered)
Game visibility fix --> Final outcome display (same reason)
Live score display --> Prediction outcome marker (need actual_winner to compare)
Live score display --> Nightly reconciliation (fallback for missed live updates)
DB schema changes (actual_winner, prediction_correct, reconciled_at) --> Prediction outcome marker
DB schema changes --> History page (needs prediction_correct for accuracy calc)
Date navigation --> Past date loading (need API endpoint for arbitrary dates)
Date navigation --> Tomorrow's preliminary predictions (need date param to fetch)
Date navigation --> Future-date schedule mode (need date param + schedule endpoint)
Tomorrow's preliminary predictions --> Preview pipeline run (9pm ET job)
History page --> DB schema changes (depends on actual_winner being populated)
Bases diamond component --> Live score display (only shown on in-progress cards)
```

## MVP Recommendation

Prioritize in this order:

1. **Game visibility fix** -- Highest urgency. Games disappearing mid-day is a usability bug, not a feature gap. Users visiting the site during evening games see an empty dashboard. Fix this first by merging schedule data into the `/predictions/today` response regardless of game status.

2. **Game status indicator + final score** -- Once all games are visible, they need status labels. "Pre-Game", "Live", "Final" badges with scores for completed games. This is mostly frontend work (new badges, conditional rendering) plus a lightweight API change to include game status and score in the response.

3. **Live score display (compact)** -- Score + inning on in-progress cards. This requires the backend live score poller (90s interval, MLB Stats API `schedule?hydrate=linescore`). Start with the compact view: score and "T5" / "B7" inning indicator. No bases diamond yet.

4. **DB schema + prediction outcome marker** -- Add `actual_winner`, `prediction_correct`, `reconciled_at` columns. Write actual outcomes when games go Final. Show checkmark/X on completed cards.

5. **Nightly reconciliation** -- Safety net. Schedule after live poller is working.

6. **Date navigation (today + past)** -- Left/right arrows + date display. Past dates fetch from Postgres. This unlocks the full history use case.

7. **Bases diamond + expanded live card** -- Polish for in-progress games. Add after core live scoring works.

8. **Tomorrow's preliminary predictions** -- Requires preview pipeline run. Add after date navigation supports tomorrow.

9. **Future-date schedule mode** -- Low priority; depends on date navigation being built.

10. **History page** -- Last because it requires the most accumulated data to be useful. Build the DB population (items 3-5) first, let data accumulate for a few weeks, then build the history UI.

**Defer to v2.3+:** Rolling accuracy chart (needs sufficient data volume to render meaningful trends; at least 50+ games or ~4 full days of MLB schedule), model-specific Brier score breakdown, edge signal performance tracking.

## UX Design Decisions

### In-Progress Card Layout

**At-a-glance (always visible on card):**
- Score (large, prominent -- replaces ensemble_prob as hero number when game is live)
- Inning + half ("T5", "B7") -- compact format beside score
- Team abbreviations (existing)
- Green pulsing dot indicator for "Live" status

**Expanded (click/tap to reveal, collapsed by default):**
- Bases diamond (SVG, ~40x40px)
- Outs indicator (3 dots, filled for each out)
- Current pitcher name
- Current batter name
- Ball-strike count ("2-1")
- Pre-game prediction probabilities (moved here from hero position)

**Rationale:** Once a game is live, the score is what matters. The pre-game prediction becomes historical context, not the primary display. ESPN, FanGraphs, and MLB.com all promote score to the hero position during live play. The prediction probability should remain visible but secondary -- users still want to see it to mentally compare against the unfolding game.

### Date Navigation Pattern

**Standard pattern (used by ESPN, MLB.com, FanGraphs, Yahoo Sports, FOX Sports):**
- Left arrow | Date display ("Mon, Mar 30") | Right arrow
- "Today" quick-jump button (always visible, highlighted when on today's date)
- Optional: calendar icon that opens a date picker for jump-to-date

**Scope boundaries:**
- Backward: Opening Day of current season (2026-03-26; no predictions exist before pipeline started)
- Forward: +7 days (schedule data available but predictions only for today/tomorrow)
- Tomorrow specifically gets "PRELIMINARY" treatment
- Future dates (day+2 through +7) show schedule only, no predictions

**URL strategy:** Use query parameter `?date=2026-03-30` rather than path-based routing (`/scores/2026-03-30`). Simpler, bookmarkable, works with existing single-page architecture. Default to today when no param present.

### Bases Diamond Implementation

**Pure CSS/SVG approach (no library):**
```
    [2B]
   /    \
[3B]    [1B]
```
- Three 12x12px squares rotated 45deg, positioned at diamond vertices within a ~40x40px container
- Fill: `var(--color-accent)` (amber) when occupied, `var(--color-border)` (#1E1E2A) when empty
- Total component: ~25 lines TSX + ~15 lines CSS module
- No dependency on `react-baseball-field-component` (too heavy for 3 squares)
- Home plate not rendered (it conveys no game-state information)

**Data source verified:** MLB Stats API linescore `offense` node includes `first`, `second`, `third` keys only when a runner occupies that base. Tested live 2026-03-30: NYY @ SEA game showed `offense.first: "Giancarlo Stanton"`, `offense.second: "Ben Rice"`, no `third` key.

### Tomorrow's Preliminary Predictions -- Uncertainty Signaling

**Visual treatments that signal "this is a best-effort forecast":**
1. Card border: dashed instead of solid (`border-style: dashed`)
2. Prediction label: "PRELIMINARY" badge in muted amber (`var(--color-accent-muted)`)
3. Where SP is TBD: "SP not yet announced" in place of pitcher name, SpBadge shows "TBD"
4. Where SP is TBD: use TEAM_ONLY feature set (already exists), label as "TEAM ONLY (SP TBD)"
5. Where SP is confirmed: use SP_ENHANCED as normal, but still label card as "PRELIMINARY" since lineup changes happen
6. Tooltip: "These predictions may change once starting pitchers are confirmed on game day."

**What NOT to do:**
- Do not grey out the entire card (suggests disabled/unavailable, discouraging engagement)
- Do not hide probabilities (users want the numbers, even preliminary ones)
- Do not show confidence intervals (the models do not produce them; fabricating them would be misleading)
- Do not use a separate card layout (reuse existing GameCard with a `preliminary` prop for styling)

### History Page: Table vs Chart

**Use both, with the table as primary and chart as secondary (added when data volume warrants).**

| Component | Purpose | Priority |
|-----------|---------|----------|
| Date range picker | Filter: last 7d, 14d, 30d, season, or custom range | P0 |
| Predictions vs actuals table | One row per game: date, matchup, ensemble_prob, predicted winner, actual winner, correct (checkmark/X) | P0 |
| Summary stats row | Total games, correct count, accuracy %, average Brier score | P0 |
| Per-model accuracy breakdown | LR/RF/XGB accuracy side by side in a compact row | P1 |
| Rolling accuracy line chart (Recharts) | 20-game rolling window, one line per model + ensemble. X-axis = date, Y-axis = accuracy %. | P1 |
| Edge signal performance | How often BUY_YES / BUY_NO was correct | P2 |
| Brier score trend chart | Rolling 20-game Brier score over time | P2 |

**Table first because:**
- Works with small sample sizes (first week of the season -- even 15 games)
- Scannable, sortable, filterable
- Does not require a charting library (defer Recharts addition)
- Users can verify individual predictions against their memory of game outcomes
- Mobile-friendly (horizontal scroll with sticky first column)

**Chart added when:**
- At least 50+ games of data accumulated (~4 days of full MLB schedule)
- Rolling averages become statistically meaningful
- Recharts is lightweight (~45KB gzip) and compatible with Vite/React stack

### Card State Machine

Each game card has exactly one of four visual states:

```
PRE_GAME -----> IN_PROGRESS -----> FINAL
    |                                 |
    |         (postponed/suspended)   |
    +---------> POSTPONED <-----------+
```

| State | Hero Display | Secondary Display | Polling | Card Chrome |
|-------|-------------|-------------------|---------|-------------|
| PRE_GAME | Ensemble prob (existing layout) | LR/RF/XGB breakdown, Kalshi edge, SP badges | 60s predictions (existing) | Solid border (existing) |
| IN_PROGRESS | Score + Inning ("3-1, T5") | Expand: bases, pitcher/batter, count, outs; Collapse: pre-game prob | 90s live score | Green left-border accent + animated pulse dot |
| FINAL | Final score ("5-3 FINAL") | Prediction outcome (checkmark/X) + pre-game ensemble prob | None (frozen) | "FINAL" badge, muted border |
| POSTPONED | "Postponed" label | Reschedule info if available from API | None | Grey muted treatment (`var(--color-stale)`) |

## Data Sources for Each Feature

| Feature | Data Source | Endpoint / Method | Polling |
|---------|------------|-------------------|---------|
| Game visibility | MLB Stats API | `schedule?date={date}&sportId=1` | Once on page load + merge with Postgres predictions |
| Live score (compact) | MLB Stats API | `schedule?date={date}&sportId=1&hydrate=linescore` | Every 90s while any game is In Progress |
| Bases/pitcher/batter (expanded) | MLB Stats API | `game/{gamePk}/feed/live` -> `liveData.linescore.offense/defense` | Every 90s (only for expanded cards to limit API calls) |
| Final outcomes | MLB Stats API | Same schedule endpoint (`abstractGameState=Final`, scores in teams node) | Triggered once when game transitions to Final |
| Past predictions | Postgres | `SELECT * FROM predictions WHERE game_date = $1` | Once on date navigation |
| Tomorrow schedule + probables | MLB Stats API | `schedule?date={tomorrow}&sportId=1&hydrate=probablePitcher` | Once on navigation to tomorrow |
| History data | Postgres | Aggregation query with date range filter, JOIN on prediction_correct | Once on page load + filter change |

## Existing Component Impact

| Existing Component | Change Required | Scope |
|--------------------|----------------|-------|
| `GameCard.tsx` | Add game status badge, conditional score display, expanded live section, prediction outcome marker | Major refactor -- but structure stays (header + body + footer) |
| `GameCard.module.css` | New styles for status badges, score hero, green accent, pulse animation, dashed border (preliminary) | Additive CSS |
| `PredictionColumn.tsx` | No change needed -- still used in PRE_GAME state and as secondary in expanded FINAL/LIVE views | None |
| `KalshiSection.tsx` | Hide during IN_PROGRESS (Kalshi edge is stale once game starts); show on FINAL cards alongside outcome | Conditional render |
| `usePredictions.ts` | Accept `date` parameter; query key includes date; merge with schedule data | Moderate refactor |
| `types.ts` | Add `GameStatus`, `LiveScoreData`, `HistoryEntry` types; extend `GameGroup` with status/score fields | Additive |
| `Header.tsx` | Add DateNavigation component (arrows + date display + Today button) | Additive -- new child component |
| `App.tsx` | Add `selectedDate` state, pass to hooks; add react-router for `/history` route | Moderate refactor |
| `client.ts` | Add `fetchScores(date)`, `fetchHistory(startDate, endDate)` methods | Additive |
| `index.css` | Add new CSS custom properties for live/final states if needed | Minimal |

## Sources

- [ESPN MLB Scoreboard](https://www.espn.com/mlb/scoreboard) -- date navigation, live game card layout reference (HIGH confidence)
- [FanGraphs Live Scoreboard docs](https://library.fangraphs.com/features/live-scoreboard/) -- win probability graph, expanded card tabs, game odds display (HIGH confidence)
- [FanGraphs Win Probability](https://library.fangraphs.com/misc/) -- WE/WPA methodology, pre-game vs in-game modeling distinction (HIGH confidence)
- [FanGraphs Game Odds announcement](https://blogs.fangraphs.com/fangraphs-game-odds/) -- pre-game prediction methodology based on pitchers + lineups (HIGH confidence)
- [MLB.com Scores](https://www.mlb.com/scores) -- standard scoreboard layout reference (HIGH confidence)
- [MLB.com Probable Pitchers](https://www.mlb.com/probable-pitchers) -- how TBD starters are displayed (MEDIUM confidence -- could not scrape rendered HTML)
- [MLB Stats API](https://statsapi.mlb.com/) -- verified live 2026-03-30: linescore structure with offense.first/second/third for bases, balls/strikes/outs, currentInning/inningHalf, schedule hydrate=linescore for inline scores (HIGH confidence)
- [MLB-StatsAPI Python wrapper](https://pypi.org/project/MLB-StatsAPI/) -- schedule(), linescore() functions; project already uses this library (HIGH confidence)
- [GUMBO Documentation (MLB Stats API)](https://bdata-research-blog-prod.s3.amazonaws.com/uploads/2019/03/GUMBOPDF3-29.pdf) -- official live game feed JSON specification (MEDIUM confidence -- PDF unreadable, verified structure via live API calls instead)
- [react-baseball-field-component](https://github.com/jingfei/react-baseball-field-component) -- evaluated and rejected; too heavy for 3-square bases display (MEDIUM confidence)
- [Recharts](https://github.com/recharts/recharts) -- LineChart for rolling accuracy visualization; lightweight, React-native (HIGH confidence)
- [Baseball scoreboard explained](https://keepthescore.com/blog/posts/baseball-scoreboard-explained/) -- R-H-E convention, standard baseball scoreboard elements (HIGH confidence)
- [Sports Betting App UX 2026](https://prometteursolutions.com/blog/user-experience-and-interface-in-sports-betting-apps/) -- real-time data display, information hierarchy patterns (MEDIUM confidence)
- [Dashboard UX patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards) -- F-pattern reading, card-based layouts, KPI placement (MEDIUM confidence)
