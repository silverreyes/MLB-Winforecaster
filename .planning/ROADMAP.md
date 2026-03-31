# Roadmap: MLB Win Probability Model

## Milestones

- v1.0 MVP - Phases 1-4 (shipped 2026-03-29) - [Archive](milestones/v1.0-ROADMAP.md)
- v2.0 Live Platform - Phases 5-9 (shipped 2026-03-30) - [Archive](milestones/v2.0-ROADMAP.md)
- v2.1 Dashboard UX / Contextual Clarity - Phases 10-12 (shipped 2026-03-31) - [Archive](milestones/v2.1-ROADMAP.md)
- **v2.2 Game Lifecycle, Live Scores & Historical Accuracy** - Phases 13-17 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) - SHIPPED 2026-03-29</summary>

- [x] Phase 1: Data Ingestion and Raw Cache (3/3 plans) - completed 2026-03-28
- [x] Phase 2: Feature Engineering and Feature Store (3/3 plans) - completed 2026-03-29
- [x] Phase 3: Model Training and Backtesting (2/2 plans) - completed 2026-03-29
- [x] Phase 4: Kalshi Market Comparison and Edge Analysis (2/2 plans) - completed 2026-03-29

</details>

<details>
<summary>v2.0 Live Platform (Phases 5-9) - SHIPPED 2026-03-30</summary>

- [x] Phase 5: SP Feature Integration (4/4 plans) - completed 2026-03-29
- [x] Phase 6: Model Retrain and Calibration (3/3 plans) - completed 2026-03-30
- [x] Phase 7: Live Pipeline and Database (3/3 plans) - completed 2026-03-30
- [x] Phase 8: API and Dashboard (3/3 plans) - completed 2026-03-30
- [x] Phase 9: Infrastructure and Go-Live (3/3 plans) - completed 2026-03-30

</details>

<details>
<summary>v2.1 Dashboard UX / Contextual Clarity (Phases 10-12) - SHIPPED 2026-03-31</summary>

- [x] Phase 10: Game Time Display (1/1 plans) - completed 2026-03-30
- [x] Phase 11: Header Date and Clock (1/1 plans) - completed 2026-03-30
- [x] Phase 12: Explanatory Content and Tooltips (1/1 plans) - completed 2026-03-30

</details>

### v2.2 Game Lifecycle, Live Scores & Historical Accuracy

- [x] **Phase 13: Schema Migration & Game Visibility** - Add game_id and outcome columns to predictions table; make all games visible regardless of status (gap closure in progress) (completed 2026-03-31)
- [x] **Phase 14: Date Navigation** - Arrow/calendar date controls with today default, past predictions, and future schedule-only mode (completed 2026-03-31)
- [ ] **Phase 14.5: Post-Phase-14 Bug Fixes** - Header timestamp (BUG-A), browser timezone clock (BUG-B), MLB API retry logic (RETRY)
- [ ] **Phase 15: Live Score Polling** - In-progress game scores, inning display, expanded card with bases/pitcher/batter, auto-Final outcome writes
- [ ] **Phase 16: Final Outcomes & Nightly Reconciliation** - Completed game cards with score/prediction/outcome marker; safety-net reconciler for missed Finals
- [ ] **Phase 17: History Route** - Date range picker, predictions vs actuals table, rolling accuracy by model

## Phase Details

### Phase 13: Schema Migration & Game Visibility
**Goal**: Users see every scheduled game on the dashboard all day long, with a clear status badge, and the database is ready to record outcomes
**Depends on**: Nothing (first phase of v2.2)
**Requirements**: SCHM-01, SCHM-02, VIBL-01, VIBL-02
**Success Criteria** (what must be TRUE):
  1. User sees all games for today on the dashboard regardless of whether a game is pre-game, in-progress, final, or postponed -- no games disappear
  2. Each game card displays a status badge (PRE-GAME / LIVE / FINAL / POSTPONED) that reflects the game's current state
  3. The predictions table contains a `game_id` column with an updated unique constraint that prevents doubleheader row collisions
  4. The predictions table contains nullable `actual_winner`, `prediction_correct`, and `reconciled_at` columns ready for downstream writes
**Plans**: 4 plans

Plans:
- [x] 13-01-PLAN.md — Schema migration: game_id + reconciliation columns, pipeline UPSERT update, tests
- [x] 13-02-PLAN.md — Backend API: /games/{date} endpoint with schedule+prediction merge, status mapping, TTL cache
- [x] 13-03-PLAN.md — Frontend: StatusBadge component, GameCard/Grid updates, useGames hook, stub cards
- [ ] 13-04-PLAN.md — Gap closure: migration packaging fix, API startup migration call, pre-lineup pitcher name display

### Phase 14: Date Navigation
**Goal**: Users can browse predictions and schedules across any date, with appropriate content for past, today, tomorrow, and future dates
**Depends on**: Phase 13
**Requirements**: DATE-01, DATE-02, DATE-03, DATE-04, DATE-05, DATE-06, DATE-07, DATE-08
**Success Criteria** (what must be TRUE):
  1. User can navigate to previous and next days using arrow controls and jump to any date via a date picker, with today loaded by default
  2. Viewing a past date shows that day's stored predictions from the database (no live polling)
  3. Viewing today shows live pipeline predictions with active polling behavior
  4. Viewing tomorrow shows games with both SPs confirmed as PRELIMINARY predictions and games without confirmed SPs as schedule-only entries
  5. Viewing a date beyond tomorrow shows scheduled matchups with a "Predictions available on game day" message and no prediction data
**Plans**: 3 plans

Plans:
- [ ] 14-01-PLAN.md — Backend: view_mode computation, probable pitcher hydration, tomorrow PRELIMINARY logic, tests
- [ ] 14-02-PLAN.md — Frontend: TypeScript types, DateNavigator component, useGames conditional polling, App.tsx wiring
- [ ] 14-03-PLAN.md — Frontend: FutureDateBanner, EmptyState date-aware copy, GameCard PRELIMINARY badge, visual verification

### Phase 14.5: Post-Phase-14 Bug Fixes
**Goal**: Fix three bugs identified during Phase 14 VPS verification
**Depends on**: Phase 14
**Requirements**: BUG-A, BUG-B, RETRY
**Success Criteria** (what must be TRUE):
  1. Header "Last updated" shows the pipeline run time, not page load time
  2. Live clock and "Next update" display in the user's browser timezone
  3. On 503 or timeout from MLB Stats API, pipeline jobs retry once after 15 minutes
**Plans**: 3 plans

Plans:
- [ ] 14.5-01-PLAN.md — BUG-A: Wire pipeline timestamp to Header, isStale, hasNewPredictions in App.tsx
- [ ] 14.5-02-PLAN.md — BUG-B: Browser-local timezone in useEasternClock (clock + next update display)
- [ ] 14.5-03-PLAN.md — RETRY: run_pipeline_with_retry wrapper in scheduler.py with 8 unit tests

### Phase 15: Live Score Polling
**Goal**: Users see real-time game progress on in-progress cards and the system automatically records outcomes when games finish
**Depends on**: Phase 13, Phase 14
**Requirements**: LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08
**Success Criteria** (what must be TRUE):
  1. In-progress game cards display the current score and inning, updated every 90 seconds (polling active only when today is selected and live games exist)
  2. User can expand an in-progress card to see a bases diamond with runners highlighted, pitch count (balls/strikes/outs), current batter with stats, and on-deck batter
  3. When a game transitions to Final, the live poller immediately writes `actual_winner` and `prediction_correct` to the corresponding prediction row in Postgres
  4. The live score endpoint uses a server-side cache to prevent MLB API amplification from multiple browser tabs or clients
**Plans**: 4 plans

Plans:
- [ ] 15-01-PLAN.md — Test scaffolds + LiveScoreData model + linescore cache + parse_linescore function
- [ ] 15-02-PLAN.md — Games route enrichment + live_poller_job + write_game_outcome + poller tests
- [ ] 15-03-PLAN.md — Frontend: TypeScript types, useGames 90s gate, ScoreRow, LiveDetail, BasesDiamond
- [ ] 15-04-PLAN.md — Full test suite verification + human VPS deployment check

### Phase 16: Final Outcomes & Nightly Reconciliation
**Goal**: Users see prediction results on completed game cards, and a nightly safety net ensures no Final game is missed
**Depends on**: Phase 15
**Requirements**: FINL-01, FINL-02, FINL-03, FINL-04
**Success Criteria** (what must be TRUE):
  1. Completed game cards display the final score, the model's win probability prediction, and a correctness marker (check or X) showing whether the model called it right
  2. A nightly reconciliation job stamps `actual_winner` and `prediction_correct` for any Final games not already written by the live poller (covering postponements, late West Coast games, and poller downtime)
  3. The reconciliation job is idempotent -- running it multiple times produces the same result with no duplicate writes
**Plans**: TBD

Plans:
- [ ] 16-01: TBD

### Phase 17: History Route
**Goal**: Users can review their prediction track record over any date range with accuracy metrics per model
**Depends on**: Phase 16
**Requirements**: HIST-01, HIST-02, HIST-03, HIST-04
**Success Criteria** (what must be TRUE):
  1. A `/history` route is accessible from the main dashboard via navigation
  2. User can select a date range and see a table of past predictions vs actual outcomes within that range
  3. History page displays rolling model accuracy (percentage correct) over the selected date range, broken down by model
**Plans**: TBD

Plans:
- [ ] 17-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 13 -> 14 -> 15 -> 16 -> 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data Ingestion and Raw Cache | v1.0 | 3/3 | Complete | 2026-03-28 |
| 2. Feature Engineering and Feature Store | v1.0 | 3/3 | Complete | 2026-03-29 |
| 3. Model Training and Backtesting | v1.0 | 2/2 | Complete | 2026-03-29 |
| 4. Kalshi Market Comparison and Edge Analysis | v1.0 | 2/2 | Complete | 2026-03-29 |
| 5. SP Feature Integration | v2.0 | 4/4 | Complete | 2026-03-29 |
| 6. Model Retrain and Calibration | v2.0 | 3/3 | Complete | 2026-03-30 |
| 7. Live Pipeline and Database | v2.0 | 3/3 | Complete | 2026-03-30 |
| 8. API and Dashboard | v2.0 | 3/3 | Complete | 2026-03-30 |
| 9. Infrastructure and Go-Live | v2.0 | 3/3 | Complete | 2026-03-30 |
| 10. Game Time Display | v2.1 | 1/1 | Complete | 2026-03-30 |
| 11. Header Date and Clock | v2.1 | 1/1 | Complete | 2026-03-30 |
| 12. Explanatory Content and Tooltips | v2.1 | 1/1 | Complete | 2026-03-30 |
| 13. Schema Migration & Game Visibility | 4/4 | Complete   | 2026-03-31 | - |
| 14. Date Navigation | 3/3 | Complete   | 2026-03-31 | - |
| 15. Live Score Polling | 2/4 | In Progress|  | - |
| 16. Final Outcomes & Nightly Reconciliation | v2.2 | 0/? | Not started | - |
| 17. History Route | v2.2 | 0/? | Not started | - |
