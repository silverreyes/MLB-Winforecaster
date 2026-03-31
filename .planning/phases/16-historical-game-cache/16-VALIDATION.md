---
phase: 16
slug: historical-game-cache
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via pyproject.toml) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_pipeline/test_game_log_sync.py -x` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline/test_game_log_sync.py -x`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | CACHE-01, CACHE-02, CACHE-03, CACHE-04, CACHE-05 | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x` | ❌ W0 | ⬜ pending |
| 16-02-01 | 02 | 2 | CACHE-01 | unit | `pytest tests/test_pipeline/test_schema.py -x -k game_logs` | ✅ (needs additions) | ⬜ pending |
| 16-02-02 | 02 | 2 | CACHE-02, CACHE-03, CACHE-05 | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k "seed or sync or immutability"` | ❌ W0 | ⬜ pending |
| 16-03-01 | 03 | 3 | CACHE-04 | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k feature_builder` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline/test_game_log_sync.py` — stubs for CACHE-01 through CACHE-05 (seed, sync, immutability, feature_builder)
- [ ] `src/pipeline/migration_002.sql` — `game_logs` DDL with `UNIQUE(game_id)` constraint
- [ ] `scripts/seed_game_logs.py` — CLI seed script scaffold (runnable via `docker compose exec worker`)

*Existing `tests/test_pipeline/test_schema.py` requires additions for CACHE-01 (game_logs table existence check).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Seed script backfills real 2025+2026 games from live MLB API | CACHE-02 | Requires live API access and populated DB | Run `docker compose exec worker python scripts/seed_game_logs.py`; check row count: `SELECT COUNT(*) FROM game_logs;` — expect ~2,400+ rows |
| Pipeline run fetches only incremental games (not full season) | CACHE-03 | Requires watching actual API call volume | Run pipeline, check logs for "Fetching game_logs from YYYY-MM-DD forward" — should NOT log full season fetch |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
