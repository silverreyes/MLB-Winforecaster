# Phase 3: Model Training and Backtesting - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Train three probability-calibrated models (logistic regression, random forest, XGBoost) on the feature matrix using walk-forward backtesting, produce per-model Brier scores and calibration curves across multiple seasons, and present a side-by-side comparison notebook. Kalshi market comparison is Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Walk-forward split design
- Expanding window: each fold trains on all seasons up to N-2, calibrates on season N-1, predicts season N
- Test years: 2019–2024 (first fold: train 2015–2018, calibrate on 2018, predict 2019... wait — see calibration section)
- Fold structure: train 2015..N-2 → calibrate on N-1 → test on N, for N = 2019..2024
- 2020 season: include in training sets only — never used as a test year (60-game season, Brier score would be statistically unreliable). 2020 games contribute training signal but are not reported as a standalone fold result.
- Early-season games (games 1–9 per team per season, where `rolling_ops_diff` is NaN): drop from both training and test sets entirely. Consistent with Phase 2's NaN-means-not-available policy. No imputation.

### Calibration mechanics
- `CalibratedClassifierCV(cv="prefit", method="isotonic")` — post-hoc calibration applied after base model is trained
- Per-fold pipeline: train base model on seasons 1..N-2 → fit isotonic calibrator on season N-1 → evaluate calibrated model on season N
- Calibration is re-run per fold — each fold has its own independently calibrated model. Never fit calibration once on full training set.
- Isotonic chosen over sigmoid: a full season (~1,100–1,200 games) provides enough calibration data for isotonic to outperform Platt scaling

### Notebook & code structure
- Model and backtest logic in `src/models/` — follow Phase 1/2 pattern of thin notebooks calling importable modules
- Two Phase 3 notebooks:
  - `09_model_training.ipynb` — runs all three models through the walk-forward loop, saves results to disk
  - `10_model_comparison.ipynb` — loads saved results, displays side-by-side Brier scores, calibration curves, per-season accuracy
- Backtest results persisted to `data/results/backtest_results.parquet` so the comparison notebook can run independently without re-training
- Comparison notebook must be runnable standalone (load results, display) without triggering any training

### NaN & feature handling
- Two feature sets used across all models:
  - **Full feature set**: all columns including xwOBA and Statcast-derived features (NaN rows handled by imputation for LR/RF; XGBoost handles NaN natively)
  - **Statcast-safe set**: drop xwOBA, sp_recent_era_diff, and any other Statcast-derived columns entirely. All models train on complete rows, no imputation needed. Used to isolate whether Statcast features help.
- Both feature sets reported in the comparison notebook — side-by-side Brier scores for full vs Statcast-safe
- LR and RF imputation: `SimpleImputer(strategy='median')` fit on training split only, applied to calibration and test splits. No data from future folds leaks into the imputer.
- LR pipeline: `StandardScaler` → `SimpleImputer` → `LogisticRegression`. Scaler fit on training split only.
- RF and XGBoost: no scaling. XGBoost handles NaN natively on full feature set; RF uses the imputation pipeline.
- All preprocessing wrapped in `sklearn.pipeline.Pipeline` to enforce temporal safety.

### Claude's Discretion
- Exact hyperparameters for RF (n_estimators, max_depth, min_samples_leaf) — tune with reasonable defaults for ~12K rows tabular
- XGBoost early stopping: validation set is last 20% of the training window (temporally ordered), not the calibration season
- Exact column names for the Statcast-safe feature set (Claude identifies which columns are Statcast-derived from FeatureBuilder)
- data/results/ subdirectory structure and exact Parquet schema for saved backtest results
- Calibration curve binning (number of bins for reliability diagrams)
- Per-season accuracy metric definition (e.g., whether to report accuracy alongside Brier score)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §MODEL-01 through MODEL-04 — model training and calibration acceptance criteria
- `.planning/REQUIREMENTS.md` §EVAL-01 through EVAL-04 — backtesting and evaluation acceptance criteria

### Roadmap
- `.planning/ROADMAP.md` §Phase 3 — goal, success criteria, dependency on Phase 2

### Prior phase context (patterns to follow)
- `.planning/phases/01-data-ingestion-and-raw-cache/01-CONTEXT.md` — cache infrastructure, notebook structure, src/ module pattern
- `.planning/phases/02-feature-engineering-and-feature-store/02-CONTEXT.md` — FeatureBuilder output schema, NaN policy, rolling feature design, 2020 flag

### No external specs
No ADRs or design docs. Requirements fully captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/features/feature_builder.py` — `FeatureBuilder(seasons, as_of_date).build()` returns the full feature DataFrame. Phase 3 calls this to load the feature matrix. The `as_of_date` parameter enforces temporal cutoff — use it in the backtest loop.
- `src/data/cache.py` — `is_cached()`, `save_to_cache()`, `read_cached()`: use for persisting backtest results to `data/results/`
- `src/data/team_mappings.py` — not needed in Phase 3 but already present
- Notebooks 01–08 — pattern for how notebooks call `src/` modules and display results

### Established Patterns
- `src/` modules are importable via repo root in sys.path — `src/models/` follows this same convention
- Notebooks are thin wrappers: imports, calls to `src/` functions, display results
- Cache-before-compute: check if result exists on disk before re-running expensive computation (backtest loop is expensive)
- Phase 2 decision: feature matrix includes `season`, `game_date`, `home_win`, `is_shortened_season`, and `kalshi_yes_price` columns — walk-forward splitting uses `season` column

### Integration Points
- Feature matrix at `data/features/feature_matrix.parquet` (Phase 2 output) — Phase 3 reads this as its input
- Backtest results at `data/results/backtest_results.parquet` — Phase 4 may need per-game predictions for the Kalshi comparison track
- Phase 4 join key `(date, home_team, away_team)` must be preserved in the backtest results so Phase 4 can join model predictions to Kalshi prices

</code_context>

<specifics>
## Specific Ideas

- The fold structure means test years 2019–2024 but 2020 is skipped as a test year. Effective test folds: 2019, 2021, 2022, 2023, 2024 — 5 folds reported in the comparison notebook.
- Calibration season N-1 is always skipped as a test year within each fold. For the 2019 fold: train 2015–2017, calibrate 2018, test 2019. For 2020 fold: skip (2020 not a test year). For 2021 fold: train 2015–2019, calibrate 2020, test 2021 (2020 is used as calibration data even though it's a short season — acceptable for calibration).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-model-training-and-backtesting*
*Context gathered: 2026-03-29*
