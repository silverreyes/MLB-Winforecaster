# Pitfalls Research

**Domain:** Adding SP Features to Existing MLB Win Probability Pipeline + Live Dashboard Deployment
**Researched:** 2026-03-29
**Confidence:** HIGH (verified against codebase, pybaseball GitHub issues, Docker/Nginx documentation, and v1 lessons learned)

---

## Critical Pitfalls

### Pitfall 1: pybaseball FanGraphs Endpoints Are Behind Cloudflare and Have Silent Failure Modes

**What goes wrong:**
`pitching_stats()`, `team_batting()`, `team_pitching()` -- all FanGraphs-backed endpoints -- now return HTTP 403 due to Cloudflare JS-challenge protection (pybaseball GitHub issue #479, opened May 2025, still active as of March 2026). Additionally, aggregate queries spanning more than 10 seasons return HTTP 500 because FanGraphs now requires authentication for 10+ year data ranges (issue #492). The existing v1 pipeline uses `pitching_stats()` in `sp_stats.py` and `team_batting()` in `team_batting.py` -- both are at risk if the Parquet cache is ever cleared or needs regeneration.

**Why it happens:**
pybaseball scrapes FanGraphs' legacy endpoint (`leaders-legacy.aspx`) via HTTP requests. FanGraphs added Cloudflare verification in mid-2025. A fix using `curl_cffi` with browser impersonation was merged in January 2026, but only in the latest pybaseball master branch -- not necessarily in the pinned version this project uses. The project also has a pybaseball maintenance risk: issue #495 (December 2025) asks "Is this project still being maintained?" -- 92 open issues total.

**How to avoid:**
1. **Never clear the Parquet cache for 2015-2024 historical data.** The v1 data is already cached. Treat those Parquet files as immutable golden source for historical seasons.
2. **Pin pybaseball to a known-working version** in `requirements.txt` and document which version includes the curl_cffi fix if upgrading.
3. **For any new season data (2025, 2026)**, add a try/except around every `pybaseball.*()` call with a specific `requests.exceptions.HTTPError` catch that logs the status code. The current `sp_stats.py` has no error handling around `pybaseball_pitching_stats()` -- a 403 will crash the entire feature build.
4. **Implement a fallback data source plan:** If FanGraphs scraping fails for 2025+ data, the MLB Stats API (`statsapi`) can provide ERA, WHIP, K, BB, IP, and GS per pitcher. FIP and xFIP would need to be computed from component stats (HR, BB, K, IP, league FIP constant). SIERA cannot be computed without batted ball data.
5. **For v2 SP features specifically**, consider whether the new SP columns (ERA, FIP, xFIP, K%, BB%, WHIP, home/away splits) should come from FanGraphs or from MLB Stats API game logs that are already working in `sp_recent_form.py`. The MLB Stats API path is more reliable but requires computing season-level aggregates from per-game logs.

**Warning signs:**
- `fetch_sp_stats()` or `fetch_team_batting()` throwing unhandled exceptions after a cache clear
- pybaseball upgrade silently changing column names or DataFrame schema
- HTTP 403/500 errors in logs during pipeline runs for current-season data

**Phase to address:**
SP Feature Integration phase -- before adding any new SP features, verify data source reliability for 2025-2026 seasons. Historical 2015-2024 data is safe in cache.

---

### Pitfall 2: SP Season-Level Stats Create Temporal Leakage When Used as Game-Level Features

**What goes wrong:**
The current `_add_sp_features()` in `feature_builder.py` uses **full-season** FanGraphs stats (FIP, xFIP, K%, SIERA) for each pitcher. For a game on June 15, the pitcher's FIP includes starts from July-September -- data from the future. This is a known v1 design choice (documented as season-level, not game-level), but v2 explicitly aims to add richer SP features. If v2 adds new SP columns using the same season-level lookup pattern, the leakage gets worse, not better.

**Why it happens:**
`sp_stats.py` calls `pybaseball.pitching_stats(season, qual=0)` which returns end-of-season totals. The `sp_lookup` dictionary in `_add_sp_features()` maps `(season, pitcher_name)` to a single stat dict per season -- there is no game-date dimension. Every game in June sees the same FIP value as games in September.

**How to avoid:**
1. **For v2, compute SP stats as rolling aggregates from per-game logs.** The infrastructure already exists in `sp_recent_form.py` which fetches per-game pitching logs from MLB Stats API and computes 30-day rolling ERA. Extend this pattern to compute rolling FIP, K%, BB%, and WHIP from per-game component stats (IP, K, BB, HR, ER).
2. **Use shift(1) on the game log** before computing the rolling aggregate. The current `sp_recent_form.py` already does this correctly: `window = log[(log["date"] >= window_start) & (log["date"] < date_dt)]` -- the `< date_dt` (strict less-than) excludes the game day.
3. **If keeping season-level stats as a baseline**, at minimum use expanding-window aggregates (stats through date D-1) rather than end-of-season totals. This requires per-game component stats (ER, IP, K, BB, HR) and running the computation per game date.
4. **Explicit leakage test:** For any new SP feature, verify that removing a game from the dataset does not change the feature values for that game. The v1 codebase already has temporal safety tests -- extend them to cover new SP columns.

**Warning signs:**
- SP feature values that are identical for all of a pitcher's starts within a season (means you are using season-level, not rolling)
- Backtest Brier score improvement that vanishes in walk-forward on the most recent fold (2024)
- New SP features have higher importance in XGBoost than team-level rolling features, which would be suspicious since team-level features already use shift(1)

**Phase to address:**
SP Feature Integration phase. This is the single most important design decision in v2 Track 1. Get this wrong and the entire retrained model is invalidated.

---

### Pitfall 3: Feature Matrix Shape Change Breaks Existing Model Pipeline

**What goes wrong:**
Adding new SP columns (e.g., `sp_era_diff`, `sp_bb_pct_diff`, `sp_whip_diff`, `sp_home_era_diff`, `sp_away_era_diff`) changes the feature matrix dimensions. `FULL_FEATURE_COLS` and `CORE_FEATURE_COLS` in `feature_sets.py` are hardcoded lists of 14 and 13 columns respectively. The `SimpleImputer` in LR and RF pipelines, the `StandardScaler` in LR, and the XGBoost model all expect a fixed number of input features. A mismatch between the feature column list and the actual DataFrame columns will either crash (`KeyError`) or silently produce wrong predictions if columns are reordered.

**Why it happens:**
`feature_sets.py` defines the contract between FeatureBuilder output and model input. When adding SP features, you must update this file atomically with the FeatureBuilder changes. But the backtest in `backtest.py` reads `FULL_FEATURE_COLS` and `CORE_FEATURE_COLS` at import time. If the feature store Parquet was generated with the old schema but `feature_sets.py` references new columns, `X_train = train_df[feature_cols]` will raise `KeyError` on the new column names.

**How to avoid:**
1. **Regenerate the feature store Parquet BEFORE updating `feature_sets.py`.** The sequence must be: (a) update `feature_builder.py` to produce new columns, (b) regenerate the feature store Parquet, (c) verify new columns exist in the Parquet, (d) update `feature_sets.py` to include new columns, (e) retrain all models.
2. **Add a schema validation assertion** at the top of `run_backtest()`: `assert all(col in df.columns for col in feature_cols), f"Missing: {set(feature_cols) - set(df.columns)}"`.
3. **Version the feature store.** Name the Parquet file with a version suffix (e.g., `feature_store_v2.parquet`) so the old v1 file is preserved and you can A/B compare results.
4. **Keep the old feature set definitions.** Do not delete `FULL_FEATURE_COLS` -- rename it to `V1_FULL_FEATURE_COLS` and add `V2_FULL_FEATURE_COLS`. This allows re-running v1 backtest for comparison.

**Warning signs:**
- `KeyError` during model training referencing new column names
- Feature importance plots showing new columns at position 0 importance (means they were all NaN/imputed)
- Brier score comparison between v1 and v2 that uses different feature sets on different feature stores (apples-to-oranges)

**Phase to address:**
Model Retrain phase. Must happen in a specific, tested sequence.

---

### Pitfall 4: Isotonic Calibration Invalidation After Feature Set Change

**What goes wrong:**
The v1 models are calibrated using `IsotonicRegression` fitted on a held-out calibration season. Adding SP features changes the model's raw probability distribution. The isotonic calibration learned from the old distribution no longer maps correctly to the new one. If you add features but forget to recalibrate, or recalibrate on too little data, you get a model that has good discrimination but badly miscalibrated probabilities -- and since Brier score penalizes miscalibration, the retrained model can have *worse* Brier scores than v1 despite better feature signal.

**Why it happens:**
`calibrate.py` fits `IsotonicRegression` on `(raw_probs, y_true)` from the calibration season. When the underlying model changes (new features = different learned weights = different raw probability distribution), the old isotonic mapping is invalid. This is especially dangerous because XGBoost and RF produce differently-distributed raw probabilities than LR, and adding features shifts these distributions differently per model.

**How to avoid:**
1. **Always recalibrate from scratch after any feature set change.** Never reuse a calibration model fitted on v1 raw probabilities.
2. **Verify calibration visually** with reliability diagrams per model per fold. A well-calibrated model's predicted probabilities should align with observed win rates in each bin.
3. **Compare Brier score decomposition** (calibration loss vs. refinement loss) between v1 and v2. If refinement (discrimination) improves but calibration worsens, the isotonic regression is underfitting the new distribution -- this may happen if the calibration season has too few games for the number of isotonic breakpoints.
4. **Consider Platt scaling (sigmoid) as a diagnostic cross-check.** If Platt scaling produces similar calibration to isotonic on the same data, the calibration is robust. If they diverge wildly, the isotonic regression may be overfitting the calibration set.
5. **The existing `FOLD_MAP` structure already handles this** -- each fold recalibrates -- but verify that the calibration season data is large enough. The 2020 calibration fold has only ~891 games, which is marginal for isotonic regression.

**Warning signs:**
- Reliability diagrams showing systematic over/under-confidence in specific probability bins
- Brier score worse than v1 despite better log-loss (indicates calibration problem, not discrimination problem)
- Isotonic calibration producing probability values clustered at 0.0 or 1.0 (overfitting)

**Phase to address:**
Model Retrain phase. Recalibration must be part of every retrain, not a separate step.

---

### Pitfall 5: SP Name Matching Failures Silently Produce NaN Features

**What goes wrong:**
Starting pitcher names in the MLB Stats API schedule (`home_probable_pitcher`: "Marcus Stroman") may not match FanGraphs names used in `sp_stats.py` due to: (a) accent characters (Jose vs Jose), (b) suffix differences ("Jr." vs "Jr" vs no suffix), (c) name changes (marriage, legal), (d) nicknames vs legal names. The current `_add_sp_features()` silently produces NaN when a pitcher name doesn't match. The `SimpleImputer(strategy='median')` then replaces these NaNs with the median SP stat value -- which is the league-average pitcher. This means any name mismatch effectively treats an elite or terrible pitcher as average.

**Why it happens:**
The v1 codebase already documents ~17% NaN rate in SP features from name matching (see `feature_sets.py` comments: "83.1% coverage"). Adding more SP features from FanGraphs multiplies this problem. Every new SP column will have the same ~17% NaN pattern. If you add SP columns from a *different* source (e.g., Statcast for xwOBA, which uses `"last_name, first_name"` format -- already a known v1 bug), the NaN pattern will be different, creating partially-observed SP feature rows.

**How to avoid:**
1. **Use player ID-based matching, not name matching.** The MLB Stats API schedule includes `home_pitcher_id` and `away_pitcher_id` (integer player IDs). FanGraphs data also includes `IDfg` (FanGraphs ID). Build a cross-reference table: `mlb_player_id -> fangraphs_id -> bbref_id`. The `sp_recent_form.py` already uses `_get_pitcher_id_map()` for MLB Stats API -- extend this pattern.
2. **If sticking with name matching**, implement fuzzy matching with a similarity threshold (e.g., `difflib.SequenceMatcher` ratio > 0.85) as a fallback for exact-match failures, and log every fuzzy match for manual review.
3. **Track name-match failure rate per season** as a data quality metric. If the rate exceeds 20% for any season, that season's SP features are statistically degraded.
4. **For the xwOBA fix (ADVF-07)**, the Statcast column is `est_woba` not `xwoba`, and names are `"last_name, first_name"` -- both are known v1 bugs. Fix these before computing any new xwOBA-based SP features.

**Warning signs:**
- NaN rates above 20% in any new SP feature column
- Median imputation changing the distribution of SP differential features (check histograms before/after imputation)
- Model feature importance for new SP columns being near zero (could mean all values are imputed to median)

**Phase to address:**
SP Feature Integration phase. Decide on name-matching vs. ID-matching strategy before writing any new feature code.

---

### Pitfall 6: SP Scratch / Late Change Produces Stale Predictions in Live Pipeline

**What goes wrong:**
The live pipeline runs twice daily: 10am ET (team-only features, SP may be unconfirmed) and 1pm ET (with SP features). But MLB teams can scratch a starter as late as 60 minutes before first pitch -- or even during warmups. If the 1pm run captured a probable pitcher at 1pm but the pitcher is scratched at 5:30pm for a 6:05pm game, the prediction on the dashboard is based on the wrong pitcher. Users see a confident prediction that was built on incorrect input, with no indication that the SP changed.

**Why it happens:**
The MLB Stats API `probable_pitcher` field updates at the source, but the pipeline only runs at fixed times. Between the pipeline run and game time, any SP change creates a stale prediction. This is not an edge case -- per Rotowire's daily lineup page, multiple SP changes happen per week during the regular season (injury scratches, illness, bullpen games).

**How to avoid:**
1. **Display prediction timestamp prominently** on the dashboard: "Prediction generated at 1:03pm ET using SP: Marcus Stroman (NYM) vs. Aaron Nola (PHI)". Users can see when data was captured.
2. **Store the SP name used for each prediction** in Postgres alongside the probability. This creates an audit trail and enables detecting when the actual starter differs from the predicted starter.
3. **Implement a lightweight SP-change detection poll** between pipeline runs: a small worker that checks the MLB Stats API `schedule` endpoint every 30 minutes between 1pm and game time. If `probable_pitcher` changes after the 1pm run, either (a) trigger a re-run for that specific game, or (b) flag the prediction as "SP changed -- prediction may be outdated" on the dashboard.
4. **For PIPE-03 (SP uncertainty)**, when a starter is listed as TBD at 1pm, fall back to the team-only prediction from the 10am run and display "Pitchers TBD -- using team-only model" rather than silently using NaN SP features with median imputation.

**Warning signs:**
- Dashboard showing SP names that differ from the actual game starters (detectable in post-game reconciliation)
- Multiple games per day where 1pm prediction used wrong pitcher
- Users noticing prediction didn't change despite a well-publicized SP scratch

**Phase to address:**
Live Pipeline phase (PIPE-01 through PIPE-03). The SP uncertainty fallback (PIPE-03) is critical to implement in the same phase as the pipeline, not as a later enhancement.

---

### Pitfall 7: Docker Compose on 8GB Shared VPS -- OOM Kills Take Down Ghost CMS and GamePredictor

**What goes wrong:**
The Hostinger KVM 2 VPS has 8GB RAM shared across Ghost CMS (Node.js), the existing GamePredictor app, and the new MLB Forecaster stack (FastAPI + Celery/worker + Postgres + Nginx). Without explicit memory limits in `docker-compose.yml`, a single container (likely Postgres during a large query or the Python worker during model inference) can consume all available RAM. The Linux OOM killer then kills processes system-wide -- which can terminate Ghost CMS (killing silverreyes.net), the GamePredictor, or the SSH daemon (locking you out of the server).

**Why it happens:**
Docker containers have no default memory limit. Postgres `shared_buffers` defaults to 128MB but total memory usage can spike during query planning. The Python prediction worker loading XGBoost models (with 500 estimators, depth 4) and a pandas DataFrame in memory can use 500MB-1GB during a prediction batch. Ghost CMS typically uses 200-400MB. With no limits, total consumption can exceed 8GB during concurrent operations.

**How to avoid:**
1. **Set explicit memory limits in `docker-compose.yml` for every container:**
   ```yaml
   services:
     api:
       deploy:
         resources:
           limits:
             memory: 512M
     worker:
       deploy:
         resources:
           limits:
             memory: 1G
     postgres:
       deploy:
         resources:
           limits:
             memory: 512M
   ```
2. **Budget total container memory at 60-70% of RAM** (4.8-5.6GB), leaving 2.4-3.2GB for the host OS, Ghost CMS, GamePredictor, Nginx, and SSH. Concrete budget: Ghost (400MB) + GamePredictor (400MB) + Nginx (100MB) + OS (1.5GB) = 2.4GB reserved. That leaves ~5.6GB for the MLB Forecaster stack.
3. **Configure Postgres `shared_buffers` explicitly** (e.g., 128MB) and `work_mem` (e.g., 16MB) to prevent query-time spikes.
4. **Add `restart: unless-stopped`** to all containers so they recover after OOM kills, and configure Docker's `--oom-score-adj` to protect critical containers (Nginx, Ghost).
5. **Monitor memory** with a simple cron job: `docker stats --no-stream >> /var/log/docker-stats.log` every 5 minutes. Alert if any container exceeds 80% of its limit.

**Warning signs:**
- Exit code 137 in Docker logs (SIGKILL from OOM)
- Ghost CMS or silverreyes.net going down during MLB pipeline runs
- SSH connection refused after pipeline execution

**Phase to address:**
Infrastructure/Deployment phase (INFRA-01). Memory limits must be set before the first deployment, not after the first OOM incident.

---

### Pitfall 8: Nginx Reverse Proxy Misconfiguration Kills All Hosted Sites

**What goes wrong:**
The VPS runs a single host-level Nginx that reverse-proxies to Ghost CMS, GamePredictor, and the new MLB Forecaster (port 8082). A syntax error in the new `mlbforecaster.silverreyes.net` server block, or a misconfigured SSL cert renewal, causes `nginx -t` to fail. The next `nginx reload` (or Certbot auto-renewal) refuses to start, taking down ALL sites on the VPS -- not just the new one.

**Why it happens:**
Nginx loads all config files in `/etc/nginx/sites-enabled/` atomically. One bad file prevents the entire Nginx process from starting. Certbot's `--nginx` plugin modifies Nginx configs in-place during certificate renewal. If the MLB Forecaster config has an upstream that is unreachable (e.g., Docker container not running), Certbot's renewal can fail and leave Nginx in a broken state.

**How to avoid:**
1. **Always run `nginx -t` before any reload.** Script the deployment: `nginx -t && nginx -s reload || echo "NGINX CONFIG BROKEN"`.
2. **Use a separate config file** for `mlbforecaster.silverreyes.net` in `/etc/nginx/sites-available/` and symlink to `sites-enabled/`. If the config is broken, you can remove the symlink to restore other sites without editing files.
3. **Test Certbot renewal in dry-run mode** before going live: `certbot renew --dry-run`. This validates that all domains can renew without actually modifying certificates.
4. **Use `proxy_pass` to `127.0.0.1:8082`** (not to a Docker network hostname). If the Docker container is down, Nginx will return 502 Bad Gateway for the MLB site but the other sites keep working.
5. **Keep a backup of working Nginx configs** before each change: `cp /etc/nginx/sites-available/mlbforecaster /etc/nginx/sites-available/mlbforecaster.bak`.

**Warning signs:**
- `nginx -t` returns error after adding new server block
- Certbot renewal logs showing "Could not bind to port 80" or upstream errors
- All sites returning 502 or connection refused simultaneously

**Phase to address:**
Infrastructure/Deployment phase (INFRA-02). The Nginx config must be validated in isolation before enabling.

---

### Pitfall 9: Postgres Volume Persistence -- `docker-compose down -v` Destroys All Prediction History

**What goes wrong:**
Postgres data in Docker is only persistent if a named volume is correctly mounted at `/var/lib/postgresql/data`. Running `docker-compose down -v` (the `-v` flag removes volumes) during a routine update destroys the entire prediction history database. Similarly, using an anonymous volume (no explicit volume name in `docker-compose.yml`) means the data appears persistent during normal restarts but is lost if the container is recreated (e.g., `docker-compose up --build`).

**Why it happens:**
The Postgres Docker image declares a VOLUME at `/var/lib/postgresql/data`. If no named volume is mounted there, Docker creates an anonymous volume that is not associated with any compose service name. `docker-compose down` without `-v` preserves named volumes but anonymous volumes can be garbage-collected. Developers running `docker-compose down -v` to "clean up" during development will destroy production data.

**How to avoid:**
1. **Always use a named volume** in `docker-compose.yml`:
   ```yaml
   volumes:
     postgres_data:
   services:
     postgres:
       volumes:
         - postgres_data:/var/lib/postgresql/data
   ```
2. **Never use `docker-compose down -v` on the production VPS.** Document this as a "never run" command in the deployment README.
3. **Implement a daily Postgres backup** via `pg_dump` to a file outside the Docker volume:
   ```bash
   docker exec mlb-postgres pg_dump -U mlb mlb_forecaster > /opt/backups/mlb_$(date +%F).sql
   ```
4. **Test persistence explicitly** during initial deployment: insert a test row, run `docker-compose down && docker-compose up -d`, verify the row persists.
5. **For Postgres 18+**, note that the `PGDATA` path changed to `/var/lib/postgresql/18/docker` -- if using Postgres 18, the volume mount target must be updated accordingly.

**Warning signs:**
- Empty prediction tables after a container rebuild
- `docker volume ls` showing anonymous volumes with hash names instead of named `mlb_postgres_data`
- Postgres container logs showing "database system was not properly shut down" (indicates unclean stop)

**Phase to address:**
Infrastructure/Deployment phase (INFRA-01). Volume configuration must be correct from the first `docker-compose up`.

---

### Pitfall 10: Cron Job Failures Are Silent -- Pipeline Stops Running and Nobody Notices

**What goes wrong:**
The twice-daily prediction pipeline (10am and 1pm ET) runs via cron inside a Docker container or on the host. Cron jobs in Docker do not run by default -- you must explicitly install cron, start the daemon, and configure it in foreground mode. Even when cron is configured, failures are silent: cron sends output to the local mailer, which is not configured on most VPS setups. If the pipeline crashes (data source timeout, model loading error, Postgres connection refused), the dashboard simply shows yesterday's stale predictions with no alert to the operator.

**Why it happens:**
Cron does not load shell profiles (`.bashrc`, `.zshrc`). Environment variables (like `DATABASE_URL`, Python virtualenv paths, or API keys) are not available to cron jobs. The cron shell is `/bin/sh`, not bash. A script that works perfectly when run manually can fail silently in cron due to any of these differences.

**How to avoid:**
1. **Do not use cron inside Docker containers.** Use an external scheduler: either host-level cron that runs `docker exec`, or a process manager like `supervisord`, or a dedicated task runner like Celery Beat.
2. **If using host-level cron**, always redirect stdout and stderr: `*/1 10,13 * * * /opt/mlb/run_pipeline.sh >> /var/log/mlb-pipeline.log 2>&1`.
3. **Implement "heartbeat" monitoring**: After each successful pipeline run, write a timestamp to a health-check endpoint (e.g., `GET /api/health` returns `{"last_run": "2026-04-01T13:05:00Z", "status": "ok"}`). An external uptime monitor (UptimeRobot free tier) can check this endpoint and alert if it goes stale.
4. **Set full PATH and environment in the cron entry or wrapper script:**
   ```bash
   #!/bin/bash
   source /opt/mlb/.env
   export PATH=/usr/local/bin:$PATH
   cd /opt/mlb && docker exec mlb-worker python -m src.pipeline.run
   ```
5. **Test the cron job by running the exact cron command** from a clean shell: `env -i /bin/sh -c '/opt/mlb/run_pipeline.sh'` -- if this fails, cron will fail too.

**Warning signs:**
- Dashboard showing predictions from yesterday (stale `last_updated` timestamp)
- `/var/log/mlb-pipeline.log` not being updated
- `crontab -l` showing entries but `docker logs mlb-worker` showing no recent activity

**Phase to address:**
Live Pipeline phase (PIPE-01). The monitoring must be deployed alongside the pipeline, not after.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using season-level SP stats instead of game-level rolling | Faster to implement, already in v1 | Temporal leakage in every SP feature; invalidates Brier score comparison with Kalshi | Never -- v2 must fix this |
| Median imputation for missing SP features | Models train without errors on NaN data | Treats unmatched elite/bad pitchers as league-average; biases predictions toward 50% for ~17% of games | Only if NaN rate < 5% and the missing pitchers are genuinely random (they are not -- rookies and call-ups are systematically different) |
| Single Postgres container with no backup | No backup infrastructure to maintain | One `docker-compose down -v` or disk failure loses all prediction history | Never in production. Acceptable for first week of development on VPS. |
| Skipping memory limits in docker-compose.yml | Simpler initial config | First OOM takes down Ghost CMS and all hosted sites | Never on a shared VPS. Acceptable only on a dedicated dev machine. |
| Hardcoding port 8082 without checking for conflicts | Works on first deploy | If Ghost or GamePredictor is reconfigured to use 8082, both services fail with "address already in use" | Acceptable if documented in deployment checklist and verified before each deploy |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FanGraphs team names to MLB Stats API team names | Assuming FanGraphs abbreviations match MLB Stats API. FanGraphs uses some different codes (e.g., "WSN" vs "WAS", "TBR" vs "TB") | Always route through `normalize_team()` from `team_mappings.py`. The v1 `team_batting.py` has a comment noting FanGraphs names are NOT normalized -- this is a latent bug for any join. |
| Statcast player name format | Assuming Statcast uses "First Last" format. Baseball Savant returns `"last_name, first_name"` as a single merged column | Parse the merged column with `.str.split(", ", expand=True)` and reconstruct as "First Last". The v1 xwOBA bug (ADVF-07) is exactly this issue. |
| MLB Stats API probable pitcher names to FanGraphs pitcher names | Assuming identical name strings across data sources | Use player ID cross-reference. MLB Stats API provides `home_pitcher_id`; FanGraphs provides `IDfg`. Build a mapping table once per season. |
| Kalshi ticker team codes to canonical codes | Assuming Kalshi uses standard abbreviations. Kalshi uses "KAN" (not KC), "FLA" (not MIA), "ATH" (not OAK) | The v1 `team_mappings.py` already handles these, but any new Kalshi integration code must route through `normalize_team()` |
| Postgres timestamp handling in Docker | Storing timestamps without timezone. Python `datetime.now()` returns naive (no tz) datetimes; Postgres `TIMESTAMP WITHOUT TIME ZONE` stores them as-is | Use `TIMESTAMP WITH TIME ZONE` in Postgres and `datetime.now(timezone.utc)` in Python. Display in ET on the frontend only. |
| FanGraphs 10+ year query limit | Querying `pitching_stats(2015, 2026)` as a single call -- returns HTTP 500 for unauthenticated users | Query one season at a time: `pitching_stats(season, season)` in a loop. The v1 code already does this (loop over `self.seasons` in `_add_sp_features`), but any refactoring must preserve this pattern. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `.apply(lambda, axis=1)` for every row in feature_builder.py | FeatureBuilder.build() takes 15+ minutes for 10 seasons | Vectorize lookups using `pd.merge()` or `pd.Series.map()` instead of row-wise `.apply()`. Priority: `_add_sp_features()` and `_add_advanced_features()` both iterate every row with `.apply()`. | Already slow at 10 seasons; adding per-game SP stats (instead of season-level) will multiply runtime by ~100x per SP feature if done with `.apply()` |
| Fetching individual pitcher game logs sequentially in `sp_recent_form.py` | 300+ API calls per season with 0.3s delay = 90+ seconds per season, ~15 minutes for 10 seasons | Already cached after first run, but cache miss (new season or new pitcher) triggers sequential fetches. Consider batching where MLB Stats API supports it. | Acceptable for backtest (runs once, cached). Unacceptable for live pipeline if cache is cold (10am run could take 5+ minutes for a busy day). |
| Loading all three models into memory simultaneously in the live prediction worker | 1GB+ resident memory for XGBoost + RF + LR with calibration objects | Load models on demand and release after prediction, or serialize to lightweight format. XGBoost model with 500 trees is the largest (~50-100MB serialized, ~200-400MB in memory). | At 8GB VPS with other services, simultaneous model loading during prediction + data fetch can spike to 2GB+ for the worker container alone. |
| Pandas DataFrame copy proliferation in FeatureBuilder | Memory usage doubles or triples as `.copy()` is called in each `_add_*` method | Necessary for correctness (avoid SettingWithCopyWarning) but watch total memory. The full 10-season feature matrix is ~40K rows x ~20 columns -- small. But if expanding to per-game SP stats with 30-day windows, intermediate DataFrames during computation can be much larger. | Not a problem at current scale. Could become a problem if adding many rolling SP features with wide windows. |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing Postgres port (5432) to the internet in Docker Compose | Database accessible from any IP; brute-force attacks on default `postgres` user | Bind Postgres port only to localhost: `ports: ["127.0.0.1:5432:5432"]` or use Docker network (no port mapping at all -- let FastAPI connect via Docker DNS). |
| Storing database credentials in `docker-compose.yml` committed to git | Credentials visible in repository history | Use `.env` file for `POSTGRES_PASSWORD`, add `.env` to `.gitignore`. Reference in compose: `env_file: .env`. |
| FastAPI endpoint with no rate limiting | Attacker hammers `/api/predictions` causing Postgres connection exhaustion and VPS CPU spike | Add rate limiting middleware (e.g., `slowapi` for FastAPI) with 60 req/min per IP. The dashboard is read-only so aggressive rate limiting is acceptable. |
| Kalshi API key in source code or Docker environment | API key leaked if repo goes public or .env is committed | Use a secrets manager or at minimum ensure `.env` is in `.gitignore` and `.dockerignore`. Kalshi API key should have read-only permissions where possible. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing predictions with no indication of when data was generated | User sees stale predictions from 10am run at 6pm, doesn't realize SP may have changed | Show "Last updated: 1:03pm ET" prominently and "SP: [name] vs [name]" per game. Gray out predictions older than 3 hours. |
| No error state when API is down | Dashboard shows infinite loading spinner or blank page if FastAPI is unreachable | Show explicit "Predictions unavailable -- last successful update was [time]" message. Cache last known predictions in localStorage as fallback. |
| Client-side polling at 10-second intervals | 8640 API requests per client per day; unnecessary load on VPS for data that updates twice daily | Poll every 60 seconds. Use `If-Modified-Since` or ETag headers so the server returns `304 Not Modified` for unchanged data. Better: return a `next_update_at` timestamp from the API and have the client sleep until then. |
| Polling continues when browser tab is hidden | Wasted requests and battery drain on mobile | Use `document.visibilityState` to pause polling when tab is not visible. Resume on `visibilitychange` event. |
| Prediction numbers shown without confidence interval or uncertainty flag | User treats 62% win probability as certainty, doesn't understand model limitations | Show "Model: 62% | Kalshi: 58%" side-by-side with a visual indicator of agreement/disagreement. When SP is TBD, show "Team-only estimate (SP TBD)" in a different color/style. |

## "Looks Done But Isn't" Checklist

- [ ] **Feature store regenerated:** New SP features exist in Parquet columns with non-NaN data -- verify `df[new_sp_cols].notna().mean()` > 0.80 for each column
- [ ] **Temporal safety verified:** All new SP features use data strictly before game date -- run the existing temporal safety test suite against v2 feature store
- [ ] **Models retrained on new features:** All 6 model/feature-set combinations (3 models x 2 sets) retrained and evaluated -- check that `run_all_models()` completes without error
- [ ] **Calibration re-verified:** Reliability diagrams for all 6 combinations show diagonal alignment -- visual inspection, not just Brier score
- [ ] **Brier score comparison is apples-to-apples:** v1 and v2 compared on identical test folds using their respective feature sets -- v2 should be compared against v1 on the same `FOLD_MAP`, not a different split
- [ ] **Postgres volume is named (not anonymous):** `docker volume ls` shows a named volume for Postgres, not a hash
- [ ] **Memory limits set in docker-compose.yml:** Every service has explicit `deploy.resources.limits.memory`
- [ ] **Nginx config tested in isolation:** `nginx -t` passes with only the new server block; other sites remain accessible
- [ ] **Cron job verified with clean environment:** Pipeline runs successfully from `env -i /bin/sh -c '...'`
- [ ] **Dashboard shows error state when API is down:** Manually stop FastAPI container; dashboard should show fallback message, not blank/spinner
- [ ] **SP name used for prediction is stored in database:** Each prediction row includes `home_sp` and `away_sp` columns for audit trail
- [ ] **Pipeline logs written to persistent file:** `/var/log/mlb-pipeline.log` exists and is being written to by both 10am and 1pm runs

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| FanGraphs scraping breaks mid-season | LOW | Fall back to cached Parquet for historical data. For current season, compute SP stats from MLB Stats API game logs already cached by `sp_recent_form.py`. |
| OOM kill takes down Ghost CMS | LOW | SSH in (if SSH survived), `systemctl restart docker`, verify `docker ps` shows all containers. Add memory limits immediately. If SSH is also dead, use Hostinger VPS console to reboot. |
| Feature store generated with temporal leakage | HIGH | Identify leaked features, fix the computation, regenerate feature store from scratch, retrain all 6 model combinations, regenerate all backtest results. ~4-8 hours of computation. |
| Postgres data lost (no backup) | HIGH | Predictions must be regenerated from scratch. If models are still saved, re-run predictions for all historical games. If models are also lost, full retrain required. All user-visible prediction history gone. |
| Isotonic calibration broken after retrain | MEDIUM | Re-run calibration step only (no full retrain needed). Inspect reliability diagrams. If calibration fold is too small, consider combining adjacent seasons for calibration data. |
| Nginx config breaks all sites | LOW | Remove symlink for new site config: `rm /etc/nginx/sites-enabled/mlbforecaster`. Run `nginx -t && nginx -s reload`. All other sites restore immediately. Debug config offline. |
| SP name mismatch rate > 30% | MEDIUM | Switch from name-based to ID-based matching. Requires building pitcher ID cross-reference table and modifying `_add_sp_features()`. ~2-4 hours of development, then full feature store regeneration. |
| Cron job silently failing for days | LOW | Check `/var/log/mlb-pipeline.log`. Run pipeline manually. Fix the underlying issue (missing env var, Docker container down, etc.). Re-run for missed dates. |
| Dashboard polling too aggressively | LOW | Update polling interval in React code. Deploy frontend update. No backend changes needed. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| #1: pybaseball FanGraphs 403/500 | SP Feature Integration | `try/except` around all pybaseball calls; historical cache verified intact; 2025+ fallback data source tested |
| #2: SP season-level temporal leakage | SP Feature Integration | New SP features use per-game rolling window with shift(1); temporal safety test passes; feature values change game-to-game |
| #3: Feature matrix shape change | Model Retrain | Schema validation assertion in `run_backtest()`; `FULL_FEATURE_COLS` matches Parquet columns; v1 feature set preserved as `V1_*` |
| #4: Isotonic calibration invalidation | Model Retrain | Reliability diagrams generated and visually inspected for all 6 combinations; Brier decomposition compared v1 vs v2 |
| #5: SP name matching failures | SP Feature Integration | NaN rate per new SP column < 20%; ID-based matching implemented or name-matching failure rate tracked |
| #6: SP scratch / stale prediction | Live Pipeline | Prediction includes SP name in database; dashboard shows "last updated" timestamp; SP-change detection poll implemented or at minimum "SP may have changed" warning for games > 3 hours after last run |
| #7: Docker OOM kills other services | Infrastructure/Deployment | Memory limits in docker-compose.yml verified; `docker stats` shows all containers under limits; Ghost CMS uptime verified during pipeline run |
| #8: Nginx config kills all sites | Infrastructure/Deployment | `nginx -t` passes; new site accessible; existing sites still accessible; Certbot `--dry-run` passes |
| #9: Postgres volume persistence | Infrastructure/Deployment | Named volume verified in `docker volume ls`; persistence tested across `docker-compose down && up`; daily backup cron active |
| #10: Cron job silent failure | Live Pipeline | Pipeline log file exists and updates; health check endpoint returns fresh timestamp; external uptime monitor configured |

## Sources

- [pybaseball GitHub Issues -- #479 FanGraphs 403 Error](https://github.com/jldbc/pybaseball/issues/479) -- Cloudflare blocking, verified March 2026
- [pybaseball GitHub Issues -- #492 Aggregate stats 10+ years 500](https://github.com/jldbc/pybaseball/issues/492) -- FanGraphs authentication requirement
- [pybaseball GitHub Issues -- #495 Maintenance status](https://github.com/jldbc/pybaseball/issues) -- 92 open issues, maintenance uncertainty
- [Docker Docs: Resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) -- Memory limits and OOM behavior
- [Docker Docs: Persisting container data](https://docs.docker.com/get-started/docker-concepts/running-containers/persisting-container-data/) -- Volume persistence
- [Docker Postgres Official Image](https://hub.docker.com/_/postgres) -- Volume mount path requirements, PGDATA changes in Postgres 18+
- [scikit-learn 1.8.0: Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) -- Isotonic regression limitations, Brier decomposition
- [scikit-learn 1.8.0: Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) -- Data leakage patterns
- [Wharton: Forecasting MLB Games Using ML](https://fisher.wharton.upenn.edu/wp-content/uploads/2020/09/Thesis_Andrew-Cui.pdf) -- SP feature leakage, runtime, cold-start approaches
- [CloudRay: Why Cron Jobs Fail Silently in Production](https://cloudray.io/articles/why-cron-job-fails-silently-in-production) -- Cron environment, shell differences, monitoring
- [DEV.to: How to safely run cron jobs in Docker](https://dev.to/cronmonitor/how-to-safely-run-cron-jobs-in-docker-with-monitoring-4nkm) -- Docker cron pitfalls, Supercronic recommendation
- v1 codebase: `feature_builder.py`, `sp_stats.py`, `sp_recent_form.py`, `feature_sets.py`, `backtest.py`, `team_mappings.py` -- Direct code analysis

---
*Pitfalls research for: MLB Win Forecaster v2 -- SP Feature Integration + Live Dashboard Deployment*
*Researched: 2026-03-29*
