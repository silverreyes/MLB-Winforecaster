---
phase: 6
slug: model-retrain-and-calibration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q --tb=short` |
| **Full suite command** | `pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | MDL-01 | unit | `pytest tests/ -x -q -k "feature_store"` | ✅ / ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | MDL-02 | unit | `pytest tests/ -x -q -k "vif"` | ✅ / ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | MDL-03 | unit | `pytest tests/ -x -q -k "shap"` | ✅ / ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | MDL-04 | unit | `pytest tests/ -x -q -k "train"` | ✅ / ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | MDL-05 | unit | `pytest tests/ -x -q -k "calibrat"` | ✅ / ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | MDL-06 | unit | `pytest tests/ -x -q -k "brier"` | ✅ / ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 3 | MDL-07 | manual | N/A — visual inspection | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase06_feature_prep.py` — stubs for MDL-01 (feature store build), MDL-02 (VIF check), MDL-03 (SHAP zero-gain filter)
- [ ] `tests/test_phase06_training.py` — stubs for MDL-04 (6 model artifacts), MDL-05 (calibration)
- [ ] `tests/test_phase06_evaluation.py` — stubs for MDL-06 (Brier comparison), MDL-07 (reliability diagrams)

*Existing pytest infrastructure covers framework — Wave 0 adds phase-specific test stubs only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reliability diagrams visually pass | MDL-07 | Visual inspection required — no automated pass/fail threshold | Open `notebooks/reliability_diagrams_v2.ipynb`; verify no model has severe S-curve or cliff pattern |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
