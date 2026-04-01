---
phase: 13
slug: schema-migration-and-game-visibility
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via pyproject.toml) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_pipeline/test_schema.py tests/test_api/test_games.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline/test_schema.py tests/test_api/test_games.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | SCHM-01, SCHM-02 | unit | `pytest tests/test_pipeline/test_schema.py -x -q` | YES | green |
| 13-01-02 | 01 | 1 | SCHM-01 | integration | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_game_id_column -x` | YES | green |
| 13-01-03 | 01 | 1 | SCHM-01 | integration | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_upsert_with_game_id -x` | YES | green |
| 13-01-04 | 01 | 1 | SCHM-02 | integration | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_reconciliation_columns -x` | YES | green |
| 13-01-05 | 01 | 1 | SCHM-02 | unit | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_reconciliation_excluded_from_upsert -x` | YES | green |
| 13-02-01 | 02 | 0 | VIBL-01, VIBL-02 | unit | `pytest tests/test_api/test_games.py -x -q` | YES | green |
| 13-02-02 | 02 | 2 | VIBL-01 | unit (mocked) | `pytest tests/test_api/test_games.py::TestGamesEndpoint::test_stub_cards_for_unpredicted_games -x` | YES | green |
| 13-02-03 | 02 | 2 | VIBL-01 | unit (mocked) | `pytest tests/test_api/test_games.py::TestGamesEndpoint::test_games_with_predictions -x` | YES | green |
| 13-02-04 | 02 | 2 | VIBL-02 | unit | `pytest tests/test_api/test_games.py::TestStatusMapping::test_status_mapping -x` | YES | green |
| 13-02-05 | 02 | 2 | VIBL-02 | unit | `pytest tests/test_api/test_games.py::TestStatusMapping::test_postponed_detection -x` | YES | green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_api/test_games.py` — stubs for VIBL-01, VIBL-02 (games endpoint tests, status mapping)
- [x] `tests/test_pipeline/test_schema.py` — TestMigration stubs for SCHM-01, SCHM-02 (migration column tests, requires Postgres)
- [x] `tests/test_pipeline/conftest.py` — update `sample_prediction_data` fixture to include `game_id` field

*`tests/test_api/conftest.py` — no changes expected; mock pool pattern sufficient.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Status badge renders PRE-GAME / LIVE / FINAL / POSTPONED on game cards | VIBL-02 | Visual rendering cannot be asserted by pytest | Load dashboard, check each badge color/label against known game states |
| Stub card shows matchup names and game time with no probability area | VIBL-01 | UI layout absence of probability section | Load dashboard with a game that has no prediction; confirm card shows teams + time, no probability numbers |
| Dashboard shows all games including pre-game and postponed | VIBL-01 | Browser integration across all game states | Open dashboard during pre-game window; verify no games disappear as statuses change |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
