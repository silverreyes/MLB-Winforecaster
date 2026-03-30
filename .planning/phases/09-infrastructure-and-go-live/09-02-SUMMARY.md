---
phase: 09-infrastructure-and-go-live
plan: 02
subsystem: infra, ui
tags: [nginx, astro, reverse-proxy, portfolio, static-site, brier-score, calibration]

# Dependency graph
requires:
  - phase: 09-infrastructure-and-go-live
    provides: Docker Compose stack on port 8082 (Plan 01)
  - phase: 06-model-training-and-evaluation
    provides: Brier scores in model_metadata.json and reliability diagram PNGs
provides:
  - Nginx server block template for VPS reverse proxy to port 8082
  - Static Astro portfolio page with methodology, Brier table, calibration curves
  - Portfolio page links to live dashboard at mlbforecaster.silverreyes.net
affects: [09-03-deployment, vps-deploy]

# Tech tracking
tech-stack:
  added: [astro-5.x]
  patterns: [host-level-nginx-reverse-proxy, astro-subdirectory-base-path, static-portfolio-no-backend]

key-files:
  created:
    - nginx/mlbforecaster.conf
    - portfolio/astro.config.mjs
    - portfolio/package.json
    - portfolio/tsconfig.json
    - portfolio/src/pages/index.astro
    - portfolio/src/components/BrierTable.astro
    - portfolio/src/components/CalibrationCurves.astro
    - portfolio/src/components/MethodologySection.astro
    - portfolio/src/layouts/Layout.astro
    - portfolio/public/images/reliability_team_only.png
    - portfolio/public/images/reliability_sp_enhanced.png
  modified: []

key-decisions:
  - "Astro BASE_URL needs explicit trailing slash in template literals for correct subdirectory image paths"
  - "Portfolio .gitignore added for node_modules, dist, .astro (Rule 2 auto-fix)"

patterns-established:
  - "Nginx template in nginx/ directory: reference config copied to VPS /etc/nginx/sites-available/"
  - "Astro portfolio with base path: use import.meta.env.BASE_URL + '/path' for subdirectory-served assets"

requirements-completed: [INFRA-02, INFRA-03, PORT-01]

# Metrics
duration: 5min
completed: 2026-03-30
---

# Phase 9 Plan 2: Nginx & Portfolio Page Summary

**Nginx reverse proxy template for mlbforecaster.silverreyes.net and static Astro portfolio page with Brier score comparison table, calibration curves, and live dashboard link**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T06:28:57Z
- **Completed:** 2026-03-30T06:34:12Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Nginx server block template proxying port 80 to 127.0.0.1:8082 with full proxy headers, keep-alive, and certbot deployment instructions
- Complete Astro 5.x portfolio project with dark theme, methodology overview, Brier score comparison table (all 6 models + Kalshi market), calibration curve images, and live dashboard CTA
- All data hardcoded from model_metadata.json -- zero backend API calls on the portfolio page

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Nginx server block template** - `2004d00` (feat)
2. **Task 2: Create Astro portfolio page with methodology and Brier scores** - `77eaf74` (feat)
3. **Task 2 supplement: package-lock.json** - `ff84ede` (chore)

## Files Created/Modified
- `nginx/mlbforecaster.conf` - Nginx server block template for VPS reverse proxy
- `portfolio/astro.config.mjs` - Astro config with base path /mlb-winforecaster and static output
- `portfolio/package.json` - Astro 5.x dependency
- `portfolio/package-lock.json` - Lock file for reproducible builds
- `portfolio/tsconfig.json` - TypeScript config extending astro/tsconfigs/strict
- `portfolio/.gitignore` - Excludes node_modules, dist, .astro
- `portfolio/src/layouts/Layout.astro` - Base HTML layout with dark theme (DM Sans font, #0a0a0f background)
- `portfolio/src/components/MethodologySection.astro` - Walk-forward backtest methodology, feature sets, calibration, Kalshi comparison
- `portfolio/src/components/BrierTable.astro` - 6-model + Kalshi Brier score comparison table with amber accent
- `portfolio/src/components/CalibrationCurves.astro` - Side-by-side reliability diagrams with BASE_URL-prefixed paths
- `portfolio/src/pages/index.astro` - Portfolio landing page composing all components + live dashboard CTA
- `portfolio/public/images/reliability_team_only.png` - Calibration curve for TEAM_ONLY models (copied from data/results/)
- `portfolio/public/images/reliability_sp_enhanced.png` - Calibration curve for SP_ENHANCED models (copied from data/results/)

## Decisions Made
- Astro `import.meta.env.BASE_URL` returns the base path without trailing slash; template literals must include explicit `/` before subpaths (e.g., `${BASE_URL}/images/...`)
- Added portfolio `.gitignore` to prevent committing node_modules, dist, and .astro build cache
- Google Fonts CDN used for DM Sans (consistent with dashboard aesthetic) rather than self-hosting in the portfolio

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing slash in BASE_URL image paths**
- **Found during:** Task 2 (CalibrationCurves component)
- **Issue:** `import.meta.env.BASE_URL` returns `/mlb-winforecaster` without trailing slash; concatenating directly with `images/` produced `/mlb-winforecasterimages/` (404)
- **Fix:** Changed to `${import.meta.env.BASE_URL}/images/...` with explicit slash
- **Files modified:** portfolio/src/components/CalibrationCurves.astro
- **Verification:** Rebuilt; `grep src= dist/index.html` shows correct `/mlb-winforecaster/images/` paths
- **Committed in:** 77eaf74 (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added portfolio .gitignore**
- **Found during:** Task 2 (after npm install)
- **Issue:** No .gitignore for portfolio directory; node_modules (277 packages) and dist would be committed
- **Fix:** Created portfolio/.gitignore excluding node_modules, dist, .astro
- **Files modified:** portfolio/.gitignore
- **Committed in:** 77eaf74 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Astro 5.x with `base: '/mlb-winforecaster'` outputs built files to `dist/` (not `dist/mlb-winforecaster/`). The base path affects URL rewriting within HTML, not the output directory structure. The plan's acceptance criteria expected `dist/mlb-winforecaster/index.html` but the actual output is `dist/index.html`. This is correct Astro behavior -- the web server is configured to serve the dist directory at the `/mlb-winforecaster` path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Nginx config template ready to copy to VPS `/etc/nginx/sites-available/`
- Portfolio Astro project builds successfully; `dist/` can be deployed to VPS
- Plan 09-03 (VPS deployment and go-live) can proceed with these artifacts
- DNS A record for mlbforecaster.silverreyes.net must be configured before Certbot SSL issuance

## Self-Check: PASSED

All 13 created files verified on disk. All 3 commits (2004d00, 77eaf74, ff84ede) verified in git log.

---
*Phase: 09-infrastructure-and-go-live*
*Completed: 2026-03-30*
