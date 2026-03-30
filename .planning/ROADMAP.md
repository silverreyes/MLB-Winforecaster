# Roadmap: MLB Win Probability Model

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-03-29) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Live Platform** — Phases 5-9 (shipped 2026-03-30) — [Archive](milestones/v2.0-ROADMAP.md)
- 🚧 **v2.1 Dashboard UX / Contextual Clarity** — Phases 10-12 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-03-29</summary>

- [x] Phase 1: Data Ingestion and Raw Cache (3/3 plans) — completed 2026-03-28
- [x] Phase 2: Feature Engineering and Feature Store (3/3 plans) — completed 2026-03-29
- [x] Phase 3: Model Training and Backtesting (2/2 plans) — completed 2026-03-29
- [x] Phase 4: Kalshi Market Comparison and Edge Analysis (2/2 plans) — completed 2026-03-29

</details>

<details>
<summary>✅ v2.0 Live Platform (Phases 5-9) — SHIPPED 2026-03-30</summary>

- [x] Phase 5: SP Feature Integration (4/4 plans) — completed 2026-03-29
- [x] Phase 6: Model Retrain and Calibration (3/3 plans) — completed 2026-03-30
- [x] Phase 7: Live Pipeline and Database (3/3 plans) — completed 2026-03-30
- [x] Phase 8: API and Dashboard (3/3 plans) — completed 2026-03-30
- [x] Phase 9: Infrastructure and Go-Live (3/3 plans) — completed 2026-03-30

</details>

### 🚧 v2.1 Dashboard UX / Contextual Clarity (In Progress)

**Milestone Goal:** Add game times, a live date/time header, and explanatory UI copy to the dashboard -- primarily frontend changes with one small backend addition for game time.

- [ ] **Phase 10: Game Time Display** - Backend game_time field + ET conversion on game cards
- [ ] **Phase 11: Header Date and Clock** - Dashboard header with today's date and live ET clock
- [ ] **Phase 12: Explanatory Content and Tooltips** - Collapsible model/Kalshi explanation + Buy Yes/No tooltips

## Phase Details

### Phase 10: Game Time Display
**Goal**: Users see when each game starts, displayed in Eastern Time on every game card
**Depends on**: Nothing (first phase of v2.1; backend change is self-contained)
**Requirements**: GMTIME-01, GMTIME-02, GMTIME-03
**Success Criteria** (what must be TRUE):
  1. API response for each prediction includes a `game_time` field containing the UTC ISO string (or null when unavailable)
  2. Each game card displays the start time converted to Eastern Time in "7:05 PM ET" format
  3. Game cards with no scheduled time display "Time TBD" instead of a time string
  4. Mobile layout does not break with the added game time element
**Plans**: TBD

Plans:
- [ ] 10-01: TBD

### Phase 11: Header Date and Clock
**Goal**: Users always know today's date and current time in the context of the game schedule (Eastern Time)
**Depends on**: Nothing (no backend dependency; can execute in parallel with Phase 10)
**Requirements**: HEADER-01, HEADER-02
**Success Criteria** (what must be TRUE):
  1. Dashboard header displays today's date in Eastern Time (e.g., "Monday, March 30")
  2. Dashboard header displays a live clock that updates every second showing current Eastern Time (e.g., "2:34 PM ET")
  3. Clock continues updating accurately after the page has been open for extended periods (no drift from setInterval accumulation)
**Plans**: TBD

Plans:
- [ ] 11-01: TBD

### Phase 12: Explanatory Content and Tooltips
**Goal**: Users understand what the models are, how to interpret probabilities, and what Buy Yes/No means -- without needing external documentation
**Depends on**: Nothing (no backend dependency; pure frontend content)
**Requirements**: EXPLAIN-01, EXPLAIN-02, EXPLAIN-03, EXPLAIN-04, EXPLAIN-05, EXPLAIN-06, EXPLAIN-07, TLTP-01, TLTP-02
**Success Criteria** (what must be TRUE):
  1. Dashboard includes a collapsible "About the Models" section that defaults to collapsed and expands/collapses on click
  2. Expanded section contains plain-English explanations of all three model types, probability interpretation, calibration meaning, PRE vs POST-LINEUP distinction, and Kalshi market mechanics with 7% fee disclosure
  3. No language in the Kalshi section recommends or encourages trading
  4. Each game card's Buy Yes label has an inline (?) icon that shows a tooltip explaining "pays $1 if home team wins; user pays the displayed price"
  5. Each game card's Buy No label has an inline (?) icon that shows a tooltip explaining "pays $1 if home team loses; user pays (1 - Yes price)"
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

## Progress

**Execution Order:**
Phases 10, 11, and 12 have no inter-dependencies and can execute in any order.

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
| 10. Game Time Display | v2.1 | 0/? | Not started | - |
| 11. Header Date and Clock | v2.1 | 0/? | Not started | - |
| 12. Explanatory Content and Tooltips | v2.1 | 0/? | Not started | - |
