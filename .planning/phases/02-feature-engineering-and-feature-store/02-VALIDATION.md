---
phase: 2
slug: feature-engineering-and-feature-store
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.1.1 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_feature_builder.py tests/test_formulas.py tests/test_leakage.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_feature_builder.py tests/test_formulas.py tests/test_leakage.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01 | 01 | 0 | FEAT-01–08 | unit | `pytest tests/test_feature_builder.py tests/test_formulas.py tests/test_leakage.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02 | 01 | 1 | FEAT-01 | unit | `pytest tests/test_feature_builder.py::test_sp_differential -x` | ❌ W0 | ⬜ pending |
| 2-03 | 01 | 1 | FEAT-02 | unit | `pytest tests/test_feature_builder.py::test_offense_differential -x` | ❌ W0 | ⬜ pending |
| 2-04 | 01 | 1 | FEAT-03 | unit | `pytest tests/test_feature_builder.py::test_rolling_ops -x` | ❌ W0 | ⬜ pending |
| 2-05 | 01 | 1 | FEAT-04 | unit | `pytest tests/test_feature_builder.py::test_bullpen_differential -x` | ❌ W0 | ⬜ pending |
| 2-06 | 01 | 1 | FEAT-05 | unit | `pytest tests/test_feature_builder.py::test_park_features -x` | ❌ W0 | ⬜ pending |
| 2-07 | 01 | 1 | FEAT-06 | unit | `pytest tests/test_feature_builder.py::test_advanced_features -x` | ❌ W0 | ⬜ pending |
| 2-08 | 01 | 1 | FEAT-07 | unit | `pytest tests/test_leakage.py -x` | ❌ W0 | ⬜ pending |
| 2-09 | 01 | 2 | FEAT-08 | integration | `pytest tests/test_feature_builder.py::test_output_schema -x` | ❌ W0 | ⬜ pending |
| 2-10 | 02 | 2 | FEAT-07 | manual | Feature notebook run + leakage correlation check | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_feature_builder.py` — stubs for FEAT-01 through FEAT-06, FEAT-08
- [ ] `tests/test_formulas.py` — stubs for Log5, Pythagorean formula correctness
- [ ] `tests/test_leakage.py` — stubs for FEAT-07 temporal safety
- [ ] `src/features/__init__.py` — module initialization
- [ ] `src/features/feature_builder.py` — main FeatureBuilder class (skeleton)
- [ ] `src/features/formulas.py` — sabermetric formulas (skeleton)
- [ ] `src/features/game_logs.py` — per-game data loader with caching (skeleton)
- [ ] `data/features/` — output directory for feature matrix Parquet

*Wave 0 must be green (stubs passing) before Wave 1 tasks start.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Feature exploration notebook shows distributions, correlations, coverage | FEAT-08 | Notebook output requires human review of plots and coverage table | Run `notebooks/02_feature_exploration.ipynb`; confirm all feature columns present, no NaN columns, correlation heatmap renders, season coverage table shows 2015–2024 |
| Leakage correlation heatmap confirms no feature corr > 0.7 with outcome | FEAT-07 | Visual inspection required for distribution analysis | Run notebook; confirm correlation matrix cell for feature-vs-outcome is < 0.7 for all rolling features |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
