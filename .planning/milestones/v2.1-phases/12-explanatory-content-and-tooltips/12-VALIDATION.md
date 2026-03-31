---
phase: 12
slug: explanatory-content-and-tooltips
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None (no vitest/jest configured for frontend) |
| **Config file** | none — no Wave 0 needed |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd frontend && npm run build` |
| **Estimated runtime** | ~3s (type-check) / ~10s (full build) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd frontend && npm run build`
- **Before `/gsd:verify-work`:** Full build must succeed + visual inspection complete
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | EXPLAIN-01–07 | type-check + manual | `cd frontend && npx tsc --noEmit` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | TLTP-01, TLTP-02 | type-check + manual | `cd frontend && npx tsc --noEmit` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test framework or stub files needed.

- `cd frontend && npx tsc --noEmit` — already available via TypeScript installation
- `cd frontend && npm run build` — already configured in package.json

*All content requirements (EXPLAIN-01 through EXPLAIN-07, TLTP-01, TLTP-02) are static UI verified via TypeScript compilation + visual inspection.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Collapsible section defaults to collapsed | EXPLAIN-01 | DOM state, not type-checkable | Load dashboard; confirm section is collapsed on page load |
| Click toggles open/close | EXPLAIN-01 | Interaction, not type-checkable | Click "About the Models"; confirm it expands and collapses |
| Model type descriptions visible when expanded | EXPLAIN-02 | Content correctness | Expand section; verify LR, RF, XGBoost descriptions present |
| Probability interpretation text | EXPLAIN-03 | Content correctness | Confirm "68 out of 100" or equivalent phrasing present |
| Calibration explanation | EXPLAIN-04 | Content correctness | Confirm calibration paragraph explains "lower is better" |
| PRE vs POST-LINEUP distinction | EXPLAIN-05 | Content correctness | Confirm both terms explained in section |
| Kalshi market explanation | EXPLAIN-06 | Content correctness | Confirm market mechanics described (price = implied probability) |
| 7% fee disclosure, no trading recommendations | EXPLAIN-07 | Content policy | Confirm fee mention present; no action verbs toward user |
| Buy Yes (?) tooltip on hover/focus | TLTP-01 | Interaction, not type-checkable | Hover or focus (?) next to BUY YES badge; confirm tooltip appears with correct copy |
| Buy No (?) tooltip on hover/focus | TLTP-02 | Interaction, not type-checkable | Hover or focus (?) next to BUY NO badge; confirm tooltip appears with correct copy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
