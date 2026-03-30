# Requirements: MLB Win Probability Model

**Defined:** 2026-03-30
**Milestone:** v2.1 — Dashboard UX / Contextual Clarity
**Core Value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## v2.1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Game Time (GMTIME)

- [ ] **GMTIME-01**: Backend exposes `game_time` (UTC ISO string or null) in prediction response, sourced from `game_datetime` in schedule data — entry point: `api/routes/predictions.py`
- [ ] **GMTIME-02**: Game card displays game time converted to Eastern Time ("7:05 PM ET") using `Intl.DateTimeFormat` with `timeZone: "America/New_York"`
- [ ] **GMTIME-03**: Game card displays "Time TBD" when `game_time` is null

### Header Clock (HEADER)

- [ ] **HEADER-01**: Dashboard header displays today's date in Eastern Time (e.g., "Monday, March 30")
- [ ] **HEADER-02**: Dashboard header displays a live clock updating every second in Eastern Time (e.g., "2:34 PM ET")

### Explanatory UI (EXPLAIN)

- [ ] **EXPLAIN-01**: Dashboard includes a collapsible "About the Models" section
- [ ] **EXPLAIN-02**: Section explains Logistic Regression, Random Forest, and XGBoost in one plain-English sentence each
- [ ] **EXPLAIN-03**: Section explains what the probability number means ("68% means the home team wins in 68 out of 100 similar matchups")
- [ ] **EXPLAIN-04**: Section explains calibration: a 70% prediction wins roughly 70% of the time historically
- [ ] **EXPLAIN-05**: Section distinguishes PRE-LINEUP (team-level stats only, more uncertainty) from POST-LINEUP (confirmed SP data, primary signal)
- [ ] **EXPLAIN-06**: Section explains Kalshi as a regulated prediction market with implied probability derivation (e.g., 62% → market pricing home win contract at $0.62)
- [ ] **EXPLAIN-07**: Kalshi explanation includes 7% fee disclosure; no language recommending or encouraging trading

### Tooltips (TLTP)

- [ ] **TLTP-01**: Buy Yes label has inline (?) tooltip: pays $1 if home team wins; user pays the displayed price
- [ ] **TLTP-02**: Buy No label has inline (?) tooltip: pays $1 if home team loses; user pays (1 − Yes price)

## Future Requirements

### Advanced Features (v3+)

- **ADVF-01**: Weather features (temperature, wind, precipitation) — deferred to v3+
- **ADVF-02**: Bullpen fatigue tracking — deferred to v3+
- **ADVF-03**: Travel distance penalty — deferred to v3+
- **ADVF-04**: Elo rating system — deferred to v3+

## Out of Scope

| Feature | Reason |
|---------|--------|
| Persist collapsible state across sessions | localStorage overhead not worth it for explanatory content |
| Pipeline worker or DB schema changes | Scope locked to response model + frontend only |
| New API calls or external data fetches | game_time sourced from existing schedule payload only |
| In-game / live win probability | Pre-game only; mid-game state is a separate domain |
| Automated trade execution | Analysis tool only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GMTIME-01 | Phase 10 | Pending |
| GMTIME-02 | Phase 10 | Pending |
| GMTIME-03 | Phase 10 | Pending |
| HEADER-01 | Phase 11 | Pending |
| HEADER-02 | Phase 11 | Pending |
| EXPLAIN-01 | Phase 12 | Pending |
| EXPLAIN-02 | Phase 12 | Pending |
| EXPLAIN-03 | Phase 12 | Pending |
| EXPLAIN-04 | Phase 12 | Pending |
| EXPLAIN-05 | Phase 12 | Pending |
| EXPLAIN-06 | Phase 12 | Pending |
| EXPLAIN-07 | Phase 12 | Pending |
| TLTP-01 | Phase 12 | Pending |
| TLTP-02 | Phase 12 | Pending |

**Coverage:**
- v2.1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
