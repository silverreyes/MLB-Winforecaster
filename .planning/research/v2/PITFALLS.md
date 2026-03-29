# Domain Pitfalls — v2.0 (SP Features + Live Dashboard)

**Domain:** MLB pre-game win probability with SP features and live deployment
**Researched:** 2026-03-29

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or fundamentally broken predictions.

### Pitfall 1: Feature Drift Between Backtest and Live Pipeline

**What goes wrong:** The live prediction pipeline computes features differently from the backtest pipeline, even subtly. Model performance in production does not match backtested metrics.
**Why it happens:** Copy-pasting feature engineering code into the FastAPI app instead of importing from `src/`. Or modifying live code without updating backtest, or vice versa.
**Consequences:** Predictions are meaningfully worse than backtested Brier scores suggest. Trust in the model erodes. Edge signals become unreliable.
**Prevention:** Both pipelines MUST import from `src/features/feature_builder.py`. No feature logic in the FastAPI app or scheduler. The Docker image must include `src/` as an installable package.
**Detection:** Compare live prediction output for a historical date against the backtest's stored prediction for the same date. Any difference signals drift.

### Pitfall 2: pybaseball FanGraphs Data Acquisition Failure

**What goes wrong:** `pitching_stats()` returns 403 or empty DataFrame during the initial 10-season data pull. You get partial data (some seasons cached, others not) and proceed with incomplete SP features.
**Why it happens:** FanGraphs uses Cloudflare protection that intermittently blocks automated requests. pybaseball is unmaintained (last release Sep 2023, maintainer unresponsive).
**Consequences:** Models trained on incomplete SP data have inconsistent feature availability across seasons. Walk-forward validation produces misleading metrics for seasons with missing SP data.
**Prevention:**
1. Install from master branch (contains URL fixes not in 2.2.7)
2. Fetch one season at a time, not 10-year spans
3. Cache to Parquet immediately on success (already implemented)
4. Implement retry with exponential backoff (3 attempts per season)
5. Validate after fetch: assert expected column count and row count (>100 pitchers per season)
6. Have a manual fallback: if all retries fail, compute FIP/K%/BB% from MLB Stats API raw stats
**Detection:** Data validation step that checks each season's Parquet file has the expected columns (ERA, FIP, xFIP, K%, BB%, WHIP) and a reasonable row count.

### Pitfall 3: Temporal Leakage in SP Features

**What goes wrong:** Using current-season SP stats for early-season games when the pitcher has only 2-3 starts. Small sample size makes the stats meaningless, or worse, the feature uses data from AFTER the game being predicted.
**Why it happens:** Forgetting to apply the `shift(1)` / `as_of_date` temporal guard that v1 uses for all rolling features. Or using full-season aggregates instead of as-of-date rolling stats.
**Consequences:** Backtest metrics are artificially inflated. Live predictions underperform.
**Prevention:**
- For season-level stats (FIP, xFIP, WHIP): use PRIOR completed season for games before the pitcher has 30+ IP in the current season, then transition to current-season stats.
- For rolling stats (30-day ERA): already uses `shift(1)` in v1 implementation. Maintain this.
- For Statcast expected stats: use prior season's xwOBA/xERA. These are season-level aggregates.
- Run the existing leakage unit tests (`tests/test_leakage.py`) after adding SP features.
**Detection:** Existing leakage tests. Add new tests: for each game, verify that SP features only use data available BEFORE the game date.

### Pitfall 4: SP Name Matching Failures

**What goes wrong:** A pitcher's name in the MLB Stats API schedule (`probablePitchers`) doesn't match the name in FanGraphs data or Baseball Savant data. Mismatches cause NULL SP features for games where the data actually exists.
**Why it happens:** Different sources use different name formats. MLB Stats API uses "First Last", FanGraphs uses "First Last" but may differ on suffixes (Jr., III), Baseball Savant uses "last_name, first_name". Traded players may appear under different team abbreviations.
**Consequences:** Systematic NaN SP features for certain pitchers. Models learn to ignore SP features because they're too sparse.
**Prevention:**
- Build a name normalization function that strips suffixes, handles special characters, and maps known aliases.
- The v1 codebase already has a `_get_pitcher_id_map()` in `sp_recent_form.py` that maps names to MLB player IDs. Extend this to also map to FanGraphs IDfg and Savant player_id.
- Log and alert on name match failures during pipeline runs (don't silently drop).
**Detection:** After feature matrix construction, count the percentage of games with non-null SP features. Should be >90% for full seasons (some rare starters or emergency starts may legitimately lack data).

---

## Moderate Pitfalls

### Pitfall 5: Scheduler Timezone Handling

**What goes wrong:** The APScheduler cron triggers fire at the wrong time because the Docker container timezone differs from ET.
**Why it happens:** Docker containers default to UTC. "10am ET" is UTC-5 (EST) or UTC-4 (EDT) depending on daylight saving time.
**Prevention:** Set `TZ=America/New_York` in the Docker container environment. Use `CronTrigger(hour=10, minute=0, timezone='America/New_York')` explicitly. Test with `date` command inside the container after deployment.

### Pitfall 6: Postgres Connection Pool Exhaustion

**What goes wrong:** The scheduler and API both open connections to Postgres. During a pipeline run (which writes many predictions), the connection pool fills up and API requests fail.
**Why it happens:** Default SQLAlchemy async pool size is small (5 connections). Both services share the same database.
**Prevention:** Set `pool_size=10, max_overflow=5` on the async engine. Use separate connection pools for API and scheduler (they're separate containers). Add health check endpoint that verifies database connectivity.

### Pitfall 7: React Build Artifact Not Updated After Deploy

**What goes wrong:** After deploying a new version, the browser shows the old dashboard because the static files are cached.
**Why it happens:** Vite produces hashed filenames by default, but if the `index.html` itself is cached by the browser or an intermediate proxy, the old hashed filenames are requested.
**Prevention:** Set `Cache-Control: no-cache` for `index.html` in nginx config. Vite's default content-hashing for JS/CSS bundles handles cache busting for everything else.

### Pitfall 8: Kalshi API Rate Limiting or Downtime

**What goes wrong:** The pipeline fails to fetch Kalshi prices during its twice-daily run. Predictions are stored without Kalshi comparison data.
**Why it happens:** Kalshi API may have rate limits, maintenance windows, or may not have markets for all games (especially early/late season).
**Prevention:** Make Kalshi price fetching optional -- store predictions regardless, with `kalshi_home_price=NULL` when unavailable. Retry Kalshi fetch up to 3 times with 30-second delays. Edge signals are only computed when Kalshi data is available.

### Pitfall 9: Docker Compose Secrets Leaked to Git

**What goes wrong:** `.env` file with database passwords and Kalshi API keys is committed to the repository.
**Why it happens:** Forgetting to add `.env` to `.gitignore`.
**Prevention:** Add `.env` and `*.secret` to `.gitignore` before creating any environment files. Use `docker-compose.yml` with `env_file: .env` and document the required variables in a `.env.example` file (with placeholder values).

### Pitfall 10: Model Artifacts Out of Sync with Feature Store

**What goes wrong:** The live pipeline loads a model `.joblib` file that was trained with different features than what the live FeatureBuilder produces. Model throws errors or produces garbage predictions.
**Why it happens:** Retraining models in a notebook, saving new artifacts, but not updating the Docker image or volume mount. Or adding new features to FeatureBuilder without retraining models.
**Prevention:** Version model artifacts. Include a metadata file alongside each `.joblib` that records: training date, feature list, training seasons, Brier score. The live pipeline checks that the model's expected feature list matches the current FeatureBuilder output before predicting.

---

## Minor Pitfalls

### Pitfall 11: Browser Notification Permission Not Requested

**What goes wrong:** The dashboard polls for updates but never shows notifications because the user hasn't granted permission.
**Prevention:** On first load, show a UI prompt explaining why notifications are useful ("Get notified when post-lineup predictions are ready"). Call `Notification.requestPermission()` on user interaction (button click), not on page load (browsers block auto-requests).

### Pitfall 12: MLB Schedule Changes (Doubleheaders, Postponements)

**What goes wrong:** The pipeline fetches the schedule at 10am, but a game is postponed or a doubleheader is added by 1pm.
**Prevention:** Re-fetch the full schedule at each pipeline run (10am and 1pm). Compare game_ids between runs. Handle new games (add predictions) and removed games (mark as postponed in database) gracefully.

### Pitfall 13: Multi-Stage Docker Build Caching Issues

**What goes wrong:** Docker rebuilds the entire Python dependencies layer on every code change, making builds take 5+ minutes.
**Prevention:** Structure Dockerfile to copy `requirements.txt` first, run `pip install`, THEN copy application code. This leverages Docker layer caching so dependency installation is cached unless requirements change.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SP data acquisition | FanGraphs 403 / empty data (#2) | Retry logic, one-season-at-a-time, cache immediately, manual FIP fallback |
| SP feature engineering | Temporal leakage (#3), name matching (#4) | Prior-season stats for early games, name normalization, leakage tests |
| FeatureBuilder expansion | Feature drift (#1) | Single `src/` codebase shared by backtest and live |
| Docker Compose setup | Timezone (#5), secrets (#9), build caching (#13) | Explicit TZ, .gitignore, multi-stage Dockerfile |
| Daily pipeline | Connection pool (#6), Kalshi API (#8), schedule changes (#12) | Pool sizing, optional Kalshi, re-fetch schedule |
| React dashboard | Notification permissions (#11), cache (#7) | User-initiated permission, no-cache for index.html |
| Model deployment | Artifact sync (#10) | Version metadata, feature list validation |

---

## Sources

- [pybaseball GitHub Issues](https://github.com/jldbc/pybaseball/issues) -- #479 (FanGraphs 403), #492 (multi-year 500), #495 (unmaintained)
- [project_constraints.md](C:/Users/silve/.claude/projects/E--ClaudeCodeProjects-MLB-WinForecaster/memory/project_constraints.md) -- FeatureBuilder shared, walk-forward only, pandas 2.2.x pin
- v1 codebase: `src/features/sp_recent_form.py` (name matching implementation), `src/data/sp_stats.py` (FanGraphs caching), `src/features/feature_builder.py` (temporal safety patterns)
- [APScheduler timezone documentation](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [SQLAlchemy async connection pooling](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
