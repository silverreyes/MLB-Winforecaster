---
phase: 1
slug: data-ingestion-and-raw-cache
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest) |
| **Config file** | none — Wave 0 installs `pytest.ini` or `pyproject.toml` |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-xx | 01 | 0 | DATA-01..06 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-01 | unit (mock HTTP) | `pytest tests/test_mlb_schedule.py -x` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-02 | unit (mock pybaseball) | `pytest tests/test_team_batting.py -x` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-03 | unit (mock pybaseball) | `pytest tests/test_sp_stats.py -x` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-04 | unit (mock pybaseball) | `pytest tests/test_statcast.py -x` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-05 | unit | `pytest tests/test_cache.py -x` | ❌ W0 | ⬜ pending |
| 1-xx-xx | TBD | 1 | DATA-06 | unit (mock HTTP) | `pytest tests/test_kalshi.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — empty init
- [ ] `pytest.ini` or `pyproject.toml` — basic pytest configuration
- [ ] `tests/test_cache.py` — stubs for DATA-05 (manifest read/write, Parquet round-trip)
- [ ] `tests/test_team_batting.py` — stubs for DATA-02 (column validation, 2020 flag)
- [ ] `tests/test_sp_stats.py` — stubs for DATA-03 (column validation, starter filtering)
- [ ] `tests/test_statcast.py` — stubs for DATA-04 (column validation)
- [ ] `tests/test_mlb_schedule.py` — stubs for DATA-01 (probable pitcher fields)
- [ ] `tests/test_kalshi.py` — stubs for DATA-06 (price parsing, team normalization)
- [ ] Framework install: `pip install pytest` (add to requirements.txt dev section)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Parquet files actually written to `data/raw/` subdirs | DATA-05 | Filesystem side-effect requires real I/O | Run each ingestion notebook end-to-end; confirm files exist with `ls data/raw/**/*.parquet` |
| Kalshi API returns price data for 2025 season | DATA-06 | External API, can't mock entire seasonal coverage | Run `notebooks/05_kalshi_ingestion.ipynb`; confirm DataFrame has rows for 2025 MLB games |
| Coverage validation reports 2015–2024 complete | DATA-05 | Requires real data from pybaseball/MLB API | Run coverage validator cell; confirm no gaps reported across seasons |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
