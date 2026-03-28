# Pitfalls Research

**Domain:** MLB Pre-Game Win Probability Modeling with Prediction Market Comparison
**Researched:** 2026-03-28
**Confidence:** HIGH (multiple academic sources, official documentation, and empirical market data converge)

## Critical Pitfalls

### Pitfall 1: Look-Ahead Bias in Feature Construction

**What goes wrong:**
Features are computed using data that would not have been available at prediction time. The most insidious form: using full-season or rolling stats that include the game being predicted (or future games) when constructing pitcher ERA, team wOBA, bullpen workload, or any cumulative metric. A model trained this way will show inflated backtest accuracy that collapses entirely in live deployment.

**Why it happens:**
When you pull a pitcher's season ERA from a historical table, that number already incorporates all games in that season -- including games after the one you are predicting. Similarly, a "last 30 days rolling wOBA" computed naively from a full-season dataframe will include future games unless you explicitly lag it. Pandas operations on grouped data make this easy to do accidentally: a `.rolling(30)` on a date-sorted series without proper `.shift(1)` will include the current row's outcome.

**How to avoid:**
- Every feature must be computed as of the morning of the game, using only data from completed games prior to that date.
- Implement a strict `as_of_date` parameter in all feature engineering functions. For any game on date D, features must use data from games with `game_date < D` only.
- For rolling pitcher stats (ERA, FIP, xFIP, K%), compute the rolling window ending the day before the game. Use `.shift(1)` after any `.rolling()` or `.expanding()` call on game-level data.
- For Statcast metrics (exit velocity, barrel rate), ensure aggregation windows exclude the game day.
- Write an explicit unit test: for each game in the test set, verify that no feature value changes if you remove that game's outcome from the source data.

**Warning signs:**
- Backtest accuracy significantly above 58-60% (the practical ceiling for MLB game prediction). Anything above 62% should trigger immediate suspicion.
- Model performance in backtest is dramatically better than live/forward performance.
- Features like "season ERA" that are suspiciously static across a whole season instead of evolving game-by-game.

**Phase to address:**
Feature Engineering phase. This must be the foundational design principle of the feature pipeline, not a retrofit.

---

### Pitfall 2: Temporal Leakage in Train/Test Splits

**What goes wrong:**
Using random or k-fold cross-validation splits instead of chronological splits. A model trained on 2022 games that includes August 2022 data in the training set while predicting June 2022 games in the test set has seen the future. Standard scikit-learn `train_test_split` with `shuffle=True` (the default) will do exactly this.

**Why it happens:**
Default scikit-learn behavior shuffles data. Tutorials and Kaggle kernels often use random splits because they work for non-temporal data. MLB game data is inherently temporal -- team strength, pitcher form, injuries, and roster composition all evolve through a season. A random split lets the model learn from these temporal patterns in reverse.

**How to avoid:**
- Use walk-forward validation (expanding window): train on seasons 2019-2021, test on 2022; then train on 2019-2022, test on 2023; and so on.
- Within a single season, use chronological splits: train on April-July, validate on August, test on September-October.
- Use scikit-learn's `TimeSeriesSplit` with data sorted by `game_date`.
- Never use `KFold`, `StratifiedKFold`, or `train_test_split(shuffle=True)` on game-level data.
- For hyperparameter tuning, use time-series-aware cross-validation. Use `TimeSeriesSplit` inside `GridSearchCV` or `RandomizedSearchCV`.

**Warning signs:**
- Cross-validation scores that are significantly better than holdout test scores on a future season.
- Identical performance across all folds (in time-series data, earlier folds should generally have less training data and slightly worse performance).
- Importing `KFold` or calling `train_test_split` without `shuffle=False` in any notebook.

**Phase to address:**
Model Training phase. The validation framework must be established before any model is trained -- retrofitting walk-forward validation onto a model tuned with random splits invalidates all prior tuning.

---

### Pitfall 3: Using End-of-Season Stats as Features for Mid-Season Games

**What goes wrong:**
A specific and extremely common variant of look-ahead bias: using the final season-level stat line (e.g., a pitcher's final 2023 ERA of 3.45) as the feature for every game that pitcher started in 2023. This means a May game "knows" how the pitcher performed in September. Alternatively, using a pitcher's next-season stats to represent their quality for the current season.

**Why it happens:**
Historical data sources (Baseball Reference, FanGraphs) serve up clean season-level stat lines. It is far easier to join `pitcher_id + season` to a stats table than to compute a game-by-game evolving cumulative stat. Many published MLB prediction projects make exactly this shortcut.

**How to avoid:**
- Build a game-log-level feature pipeline that computes cumulative stats up to (but not including) each game date.
- For pitcher stats: maintain a running tally of innings, earned runs, strikeouts, walks, HR allowed, and compute ERA/FIP/xFIP incrementally.
- For early-season games where the pitcher has < 20 IP in the current season, blend the current-season cumulative stat with prior-season stats using a regression-to-mean approach (see Pitfall 7 on small sample sizes).
- Store features in a "point-in-time" table keyed by `(game_id, team_id, pitcher_id)` where each row represents knowledge available before that game.

**Warning signs:**
- A feature column like `pitcher_era` that has the exact same value for every start by a pitcher in a season.
- Feature importance showing "pitcher_era" as dominant (it would be artificially predictive because it incorporates the game outcome).
- Features that do not exist for the most recent (current) season -- a sign the pipeline depends on end-of-season aggregates.

**Phase to address:**
Data Ingestion and Feature Engineering phases. The game-log pipeline architecture must be decided during data ingestion; feature engineering builds on it.

---

### Pitfall 4: Treating Kalshi Implied Probabilities as Ground Truth

**What goes wrong:**
Comparing model Brier scores directly against Kalshi implied probabilities as if Kalshi prices are "true" probabilities. Kalshi prices are market prices, not probability estimates. They contain a favorite-longshot bias (cheap contracts win less often than their price implies, expensive contracts win more often), bid-ask spreads, and are influenced by liquidity, fee structure, and behavioral biases. A model that "beats" a biased benchmark may still be poorly calibrated.

**Why it happens:**
It is tempting to treat prediction market prices as the gold standard because they aggregate crowd wisdom. Research on Kalshi (Whelan, 2025) analyzed over 300,000 contracts and found a clear favorite-longshot bias, meaning Kalshi prices systematically overestimate longshot probabilities and underestimate favorite probabilities. The bias is much stronger for "taker" participants than "makers."

**How to avoid:**
- Evaluate model calibration independently using reliability diagrams (calibration curves) and Brier score decomposition (reliability + resolution + uncertainty) against actual game outcomes -- not against Kalshi.
- When comparing against Kalshi, compare both the model and Kalshi against actual outcomes separately. Report Brier scores for both, and present calibration curves for both.
- Adjust Kalshi implied probabilities for the favorite-longshot bias before any edge analysis. Use the empirical win rates at each price bucket (e.g., contracts priced 0.10-0.15 historically win at X% rate) to build a de-biasing function.
- Account for Kalshi's fee structure (6.49% to 0.07% variable fee depending on contract price) when computing whether a model "edge" would be profitable after fees.
- Record the exact Kalshi price and timestamp. Kalshi prices improve in accuracy closer to game time; use closing prices (or prices at your prediction timestamp) for fair comparison.

**Warning signs:**
- Reporting "model beats Kalshi" without also reporting the model's own calibration quality.
- Using Kalshi mid-market prices without accounting for bid-ask spread -- particularly in low-liquidity games where spreads can be 5-10 cents.
- Claiming edges that disappear once Kalshi fees are included.
- Comparing model predictions made with confirmed SP data against Kalshi prices from hours earlier when SP was still uncertain.

**Phase to address:**
Evaluation and Benchmarking phase. The comparison methodology against Kalshi must be designed as carefully as the model itself.

---

### Pitfall 5: Ignoring the Impact of MLB Rule Changes on Historical Data

**What goes wrong:**
Training a model on 2019-2025 data as if it is one homogeneous dataset, when MLB introduced game-altering rule changes: pitch clock and shift ban (2023), reduced pitch timer with runners on (2024), ABS challenge system (2025). These changes fundamentally altered run environments, game pace, batting average on balls in play (left-handed BABIP rose ~8 points after the shift ban), and pitcher workload patterns. A model trained on pre-2023 data may learn relationships that no longer hold.

**Why it happens:**
More historical data generally improves model robustness. But MLB's rule changes created structural breaks in the data-generating process. The shift ban boosted left-handed hitter production, the pitch clock changed pitcher rhythm and fatigue patterns, and humidor adoption at additional stadiums changed run environments at specific parks.

**How to avoid:**
- Include a `rule_era` categorical feature (e.g., pre-2023, 2023, 2024+) or, more practically, weight recent seasons more heavily in training.
- Monitor feature distributions across rule eras. If a feature like "team BABIP vs LHP" has a distributional shift pre/post 2023, either de-trend it or only train on post-change data for that feature.
- For the shift ban specifically: left-handed batting stats from pre-2023 are not comparable to post-2023. Consider separate models or interaction terms.
- Use a sliding training window (e.g., last 3 seasons) rather than "all available data" to naturally phase out stale patterns.
- Test model performance with and without pre-2023 data; if adding older data degrades post-2023 prediction, drop it.

**Warning signs:**
- Feature importance of defensive-alignment-related features that no longer exist post-2023.
- Model performs well on 2019-2022 test data but poorly on 2023+.
- Calibration curves that are well-calibrated on older seasons but miscalibrated on recent ones.

**Phase to address:**
Data Ingestion and Feature Engineering phases. Data partitioning by rule era should be a deliberate architectural choice, not an afterthought.

---

### Pitfall 6: Brier Score Tunnel Vision

**What goes wrong:**
Using Brier score as the sole evaluation metric and drawing incorrect conclusions. Brier score conflates calibration and discrimination. A model can achieve a decent Brier score by predicting near the base rate (all games at ~0.54 home win probability) without actually having any discriminative power. Conversely, a model with excellent discrimination but poor calibration will have a worse Brier score than a trivially calibrated model.

**Why it happens:**
Brier score is the correct primary metric for probabilistic forecasts (it is a strictly proper scoring rule). But it is a single number that hides important structure. Recent research (arXiv:2504.04906) specifically highlights misconceptions: low Brier scores do not guarantee good calibration, and Brier score comparisons across different datasets are misleading.

**How to avoid:**
- Always accompany Brier score with its decomposition: reliability (calibration error), resolution (discriminative power), and uncertainty (inherent outcome variance).
- Plot calibration curves (reliability diagrams) with confidence intervals for every model. Bin predicted probabilities into deciles, plot predicted vs. observed win rates.
- Compute log loss as a complementary proper scoring rule -- it is more sensitive to confident wrong predictions.
- Report Brier Skill Score (BSS) against a baseline (climatological home-win rate) rather than raw Brier score alone. BSS = 1 - (BS_model / BS_baseline). A positive BSS means the model adds value over always predicting the base rate.
- When comparing models, use paired comparisons on the same games rather than aggregate scores.

**Warning signs:**
- Model Brier score is "good" but the calibration curve shows consistent over/under-confidence in certain probability ranges.
- A "simple" model (predicting base rate) has nearly the same Brier score as the tuned model -- this means the tuned model adds no discriminative power.
- Comparing Brier scores across different seasons without noting that outcome uncertainty varies (e.g., 2020 60-game season had different base rates).

**Phase to address:**
Model Evaluation phase. The evaluation framework must be richer than a single number.

---

### Pitfall 7: Ignoring Small Sample Sizes in Early-Season and Pitcher Stats

**What goes wrong:**
Using raw current-season stats for pitchers with 2-3 starts (10-18 IP) as if they are reliable. A pitcher's ERA after 15 IP is dominated by noise. FIP stabilizes faster than ERA but still requires ~200 batters faced for reasonable reliability. Using raw early-season stats leads to extreme feature values that drive wild predictions -- a pitcher with a 1.20 ERA after 3 starts is not actually elite; a pitcher with a 7.50 ERA after 3 starts is not necessarily terrible.

**Why it happens:**
Baseball statistics are notoriously noisy in small samples. ERA requires approximately 600-700 batters faced (roughly a full season) to stabilize. FIP requires around 200+ BF. xFIP stabilizes faster (~100 BF). K% and BB% stabilize in 100-200 BF. Using raw stats without regression to the mean in early season produces extreme, unreliable feature values.

**How to avoid:**
- Implement Bayesian shrinkage / regression to the mean for all pitcher and team stats. In April, a pitcher's "feature ERA" should be heavily weighted toward their prior-season ERA (or career ERA) and gradually shift toward current-season as innings accumulate.
- A practical formula: `blended_stat = (prior_weight * prior_stat + current_IP * current_stat) / (prior_weight + current_IP)`, where `prior_weight` is the stabilization point in IP for that stat (~60 IP for ERA, ~30 IP for FIP, ~15 IP for xFIP).
- Use the FanGraphs stabilization points as guides: K% at ~70 BF, BB% at ~170 BF, HR/FB at ~300 BF, BABIP at ~2000 BF (essentially never reliable for pitchers).
- For brand-new MLB pitchers with no prior-season data, use minor league stats with an appropriate level adjustment, or fall back to league-average.
- Apply the same logic to team offensive stats in April.

**Warning signs:**
- Extreme predicted probabilities (>0.75 or <0.25) in April/May games driven by small-sample pitcher stats.
- Model accuracy drops in April/May relative to June-September in backtest analysis.
- Pitcher features with huge variance in the first month of the season.

**Phase to address:**
Feature Engineering phase. Regression-to-mean infrastructure must be built into the feature pipeline, not bolted on after observing bad predictions.

---

### Pitfall 8: Mishandling Starting Pitcher Uncertainty and Late Changes

**What goes wrong:**
The model requires a confirmed starting pitcher as its most important input, but SP announcements are not always timely or final. Pitchers get scratched due to illness (e.g., Bibee's 2025 Opening Day food poisoning scratch), injury, or tactical decisions -- sometimes hours before game time. A live prediction pipeline that cannot handle SP changes gracefully will either produce stale predictions or crash.

**Why it happens:**
MLB's "probable pitchers" page updates at varying times. Teams are required to announce starters before lineups lock, but this can be as late as the day of the game. Sometimes a "probable" pitcher is changed after markets have already priced the original matchup. For backtesting, the historical record may show the actual starter, but the "probable" starter from the morning line may have been different.

**How to avoid:**
- Design the prediction pipeline with a "SP confirmed" vs. "SP probable" flag. When SP is only probable, output predictions with wider uncertainty or a confidence qualifier.
- For backtesting, use the actual starting pitcher, not the probable -- this is one case where using the "true" value is correct, because you are testing model accuracy given correct inputs, not testing your ability to predict SP changes.
- For the live pipeline, implement a fallback: if SP is scratched, either (a) re-run the model with the replacement SP, or (b) flag the game as "low confidence" and skip it.
- Store the timestamp of SP confirmation alongside predictions. When comparing against Kalshi, ensure both your prediction and the Kalshi price were generated with the same SP information.
- For games where SP is TBD (bullpen games, openers), build a "team bullpen" fallback feature rather than leaving the SP feature null. Consider a "bullpen game" indicator feature.

**Warning signs:**
- NaN or missing values in the SP feature column for certain games in the historical dataset.
- Predictions for today's games that use yesterday's probable pitcher list.
- Backtest results that silently drop games with missing SP data (survivorship bias).

**Phase to address:**
Data Ingestion phase (API integration) and Live Pipeline phase (operational robustness).

---

### Pitfall 9: Overfitting Gradient Boosting Models to Recent Seasons

**What goes wrong:**
XGBoost and LightGBM, with their hundreds of hyperparameters, are powerful enough to memorize 3-5 seasons of MLB data. The model learns team-specific or pitcher-specific patterns (essentially memorizing "the 2022 Dodgers were really good") rather than generalizable relationships. It performs well in backtest on seen teams/pitchers but fails on new seasons.

**Why it happens:**
With ~2,430 games per season, 3-5 seasons gives you 7,000-12,000 training samples. With 20-40 features and deep trees, gradient boosting can essentially create lookup tables for specific team-pitcher combinations. The default hyperparameters for XGBoost (max_depth=6, no regularization) are far too complex for this dataset size. LightGBM's leaf-wise growth is even more prone to overfitting with default settings.

**How to avoid:**
- Aggressive regularization: `max_depth` of 3-5 (not 6+), `min_child_weight` of 50-100 (not 1), `subsample` of 0.7-0.8, `colsample_bytree` of 0.7-0.8, `reg_alpha` and `reg_lambda` > 0.
- For LightGBM: set `num_leaves` < 2^max_depth (e.g., 15-31 for max_depth 4-5).
- Use early stopping on a time-based validation set (not a random split). Monitor validation loss and stop when it plateaus.
- Keep the logistic regression model as a calibration anchor. If the GBM model's Brier score is not meaningfully better (> 0.005 improvement) than logistic regression on the holdout set, prefer the simpler model.
- Perform feature importance analysis: if top features are team identifiers or pitcher IDs rather than performance metrics, the model is memorizing, not generalizing.

**Warning signs:**
- GBM model achieves >62% accuracy or Brier score improvement >0.02 over logistic regression on training data but not on holdout.
- Training Brier score is dramatically lower than validation Brier score (gap > 0.01).
- Feature importance dominated by categorical identifiers rather than continuous performance metrics.
- Performance degrades sharply when predicting a season not in the training data.

**Phase to address:**
Model Training phase. Regularization strategy and early stopping must be established before hyperparameter tuning begins.

---

### Pitfall 10: Survivorship Bias in Historical Data

**What goes wrong:**
Dropping games with incomplete data (missing SP stats, missing Kalshi prices, postponed/rescheduled games) without accounting for the systematic patterns in missingness. Games with TBD starters tend to involve weaker teams or bullpen games. Games without Kalshi prices tend to be lower-profile matchups. Excluding these games biases both training data and evaluation toward more predictable, higher-profile games.

**Why it happens:**
Missing data is annoying and the path of least resistance is `dropna()`. But the missingness is not random -- it correlates with factors that affect prediction difficulty. A model trained only on games with complete data may appear to perform better than it would on the full population of games.

**How to avoid:**
- Track and report the fraction of games dropped due to missing data, broken down by reason (missing SP, missing Kalshi price, missing Statcast data, postponement).
- For missing SP stats (new callups, first starts), use the fallback approach from Pitfall 7 (regression to prior/minor league stats) rather than dropping the game.
- For missing Kalshi data, evaluate the model against outcomes independently. Only compare against Kalshi on the subset where both model and Kalshi predictions exist, but report model-only Brier score on the full set.
- For postponed/rescheduled games, ensure the rescheduled game is correctly matched (same teams, but potentially different SPs and different date).
- Explicitly report "coverage" alongside accuracy: "Model covers 92% of games with Brier score X; Kalshi comparison available for 78% of games."

**Warning signs:**
- More than 5-10% of games dropped from analysis without explanation.
- Model performance degrades when you force predictions on previously-excluded games.
- Evaluation sample is significantly smaller than the actual number of games played.

**Phase to address:**
Data Ingestion phase (robust handling of missing data) and Evaluation phase (transparent reporting of coverage).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using end-of-season stats instead of game-by-game cumulative | Vastly simpler feature pipeline | Entire model is invalidated by look-ahead bias; all results meaningless | Never |
| Hardcoding Kalshi fee structure | Simpler edge calculation | Kalshi changes fees and your edge calculations silently become wrong | MVP only, with a TODO and a constant at the top of the notebook |
| Caching API responses locally without versioning | Faster iteration during development | Stale data when APIs update, no way to reproduce old results | Acceptable if cache files include fetch timestamp and a cache-bust mechanism |
| Training on all historical data without a holdout season | More training data | No way to honestly evaluate model generalization | Never for final evaluation; acceptable for exploratory analysis |
| Dropping games with missing features via `dropna()` | Clean dataframe, no errors | Survivorship bias, overstated accuracy | Only if missingness is < 2% and documented |
| Skipping calibration post-processing on tree models | Fewer pipeline steps | Random forest and GBM produce poorly calibrated probabilities; Brier score suffers | Never for a probability-focused project |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Baseball Savant / pybaseball | Requesting too much data at once; hitting the 40,000 row limit or query timeout | Chunk Statcast requests into 2-week windows using `statcast(start_dt, end_dt)`. Implement retry logic with exponential backoff. Cache responses locally with timestamps. |
| MLB Stats API | Assuming the schedule endpoint always has confirmed starters | Check the `probablePitcher` field specifically; it may be null or change. Poll closer to game time for the live pipeline. The `game_status` field matters for postponements. |
| Kalshi API | Assuming historical price data exists for all MLB games back to Kalshi's founding | Kalshi only began listing sports contracts in early 2025. Historical backtest comparison against Kalshi is limited to ~1 season. For deeper backtests, you have no Kalshi benchmark. |
| Kalshi API | Using the contract "last traded price" as the market's probability estimate | Use the midpoint of the best bid and best ask. "Last traded" could be hours old in thin markets. Even better: record the full order book snapshot and note the bid-ask spread as a confidence indicator. |
| FanGraphs | Scraping season stats and joining by pitcher name | Player names are not unique (e.g., multiple "Will Smith" players). Always join by `mlbam_id` or `fangraphs_id`. Build a player ID crosswalk table early. |
| Retrosheet / Baseball Reference | Using game logs without verifying date alignment | Doubleheaders, suspended games, and makeup games can create date mismatches between data sources. Use `game_id` (which encodes team, date, and game number) as the canonical key. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-scraping Baseball Savant on every notebook run | Notebooks take 10+ minutes to execute; API rate limiting kicks in | Build a local data lake: scrape once, store as Parquet files, load from cache. Only re-scrape for new/updated data. | Immediately, on first full-season data pull |
| Computing rolling features in a loop over games | Feature engineering takes hours for 5 seasons | Vectorize with pandas groupby + rolling + shift. Pre-compute all features and store in a feature table. | At ~10,000+ games (4+ seasons) |
| Retraining models from scratch for each day's live predictions | Live pipeline takes 30+ minutes | Train models on historical data and persist (joblib/pickle). Only retrain weekly or when new season data crosses a threshold. | When you want daily predictions |
| Storing all data in CSV files | Slow I/O, no type safety, date parsing issues | Use Parquet for tabular data. It is faster, preserves types, and compresses well. | At datasets > 100MB (Statcast pitch-level data is large) |

## Domain-Specific Calibration Warnings

| Issue | Risk | Prevention |
|-------|------|------------|
| Home field advantage is non-stationary | A fixed "home advantage" feature learned from 2015-2020 data (~.540 home win rate) overestimates modern HFA (.534 in 2020s, lowest in Live Ball era) | Use a recent rolling home-win rate as a feature, or include `season` as a feature so the model can learn the trend. Monitor HFA annually. |
| Park factors shift year-to-year | Humidor additions, fence changes (Anaheim lowered RF fence), and ball composition changes alter park run environments | Use 3-year rolling park factors from Baseball Savant rather than static historical park factors. Flag parks with known recent changes. |
| Logistic regression is naturally calibrated; tree models are not | Directly comparing Brier scores across model types without post-hoc calibration disadvantages tree models unfairly | Apply isotonic regression calibration (preferred over Platt scaling for datasets > 2000 games) to Random Forest and GBM outputs before Brier score comparison. Use a held-out calibration set separate from the test set. |
| The 2020 60-game season is an anomaly | Including 2020 data contaminates both feature distributions and evaluation baselines | Either exclude 2020 entirely or flag it as a separate era. Do not mix 2020 evaluation metrics with other seasons' metrics. |

## "Looks Done But Isn't" Checklist

- [ ] **Feature pipeline:** Verify no feature uses data from the game being predicted -- run the "remove game and recompute" unit test on a sample of 100 games.
- [ ] **Train/test split:** Confirm split is strictly chronological -- print min/max dates in train and test sets; test min date must be > train max date.
- [ ] **Pitcher stats:** Confirm early-season games use blended (prior + current) stats, not raw current-season stats -- check April games specifically for extreme feature values.
- [ ] **Calibration curves:** Plot calibration curves per model; do not report only Brier score -- if calibration curve shows systematic bias at any probability bucket, the model needs post-hoc calibration.
- [ ] **Kalshi comparison:** Ensure model predictions and Kalshi prices are timestamped and use the same SP information -- log both timestamps and flag disagreements.
- [ ] **Missing data report:** Document how many games were excluded and why -- if > 5% are dropped, investigate whether the missingness is correlated with prediction difficulty.
- [ ] **Post-hoc calibration:** Confirm isotonic/Platt calibration was applied to tree model outputs before final evaluation -- compare uncalibrated vs. calibrated Brier scores.
- [ ] **Profit calculation:** Confirm edge calculations against Kalshi include fees, bid-ask spread, and favorite-longshot bias adjustment -- an "edge" that disappears after fees is not an edge.
- [ ] **Feature leakage audit:** For every feature, document when it becomes available relative to game time -- create a "feature availability timeline" table.
- [ ] **Rule era handling:** Verify that models trained on multi-era data perform at least as well as models trained only on post-2023 data -- if not, the old data is hurting, not helping.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Look-ahead bias in features | HIGH | Rebuild entire feature pipeline from game logs. All prior model results are invalid and must be discarded. |
| Temporal leakage in splits | MEDIUM | Re-split data chronologically and retrain. Prior hyperparameter tuning is invalid, but feature pipeline is salvageable. |
| End-of-season stats as features | HIGH | Same as look-ahead bias -- requires full feature pipeline rebuild. |
| Treating Kalshi as ground truth | LOW | Re-frame evaluation: compute model Brier score against outcomes independently, then compare model and Kalshi Brier scores side-by-side. No model retraining needed. |
| Ignoring rule changes | MEDIUM | Add rule-era features or restrict training window. Retrain models. Feature pipeline may only need a new column. |
| Brier score tunnel vision | LOW | Add calibration curves, Brier decomposition, and BSS to evaluation notebooks. No retraining needed. |
| Small sample ignoring | MEDIUM | Implement regression-to-mean blending in feature pipeline. Retrain models with improved features. |
| SP change mishandling | LOW-MEDIUM | Add fallback logic to live pipeline. For backtest, verify actual starters match recorded starters. |
| GBM overfitting | MEDIUM | Re-tune with aggressive regularization and early stopping on time-based validation. May need to reduce feature set. |
| Survivorship bias | MEDIUM | Recompute evaluation metrics on full game population. May need to impute or build fallback features for previously-dropped games. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Look-ahead bias in features | Feature Engineering | Unit test: removing a game's outcome does not change its features |
| Temporal leakage in splits | Model Training | Print train/test date ranges; test min > train max |
| End-of-season stats | Data Ingestion + Feature Engineering | Feature values for a pitcher evolve game-by-game, not constant per season |
| Kalshi as ground truth | Evaluation / Benchmarking | Report model Brier score against outcomes independently of Kalshi |
| Rule change impact | Data Ingestion + Feature Engineering | Compare model performance pre/post 2023; test with and without old data |
| Brier score tunnel vision | Evaluation | Calibration curves and Brier decomposition present in every evaluation notebook |
| Small sample sizes | Feature Engineering | April predictions do not have extreme probabilities; blending formula documented |
| SP uncertainty | Data Ingestion + Live Pipeline | Live pipeline handles null SP gracefully; timestamp logging in place |
| GBM overfitting | Model Training | Training vs. validation Brier gap < 0.01; LR benchmark comparison documented |
| Survivorship bias | Data Ingestion + Evaluation | Coverage percentage reported; dropped-game analysis included |

## Sources

- [Wharton MLB Prediction Thesis (Andrew Cui, 2020)](https://fisher.wharton.upenn.edu/wp-content/uploads/2020/09/Thesis_Andrew-Cui.pdf) -- Feature engineering methodology, train/test design for MLB game prediction
- [Towards Data Science: ML Algorithm for MLB Games](https://towardsdatascience.com/a-machine-learning-algorithm-for-predicting-outcomes-of-mlb-games-fa17710f3c04/) -- Data leakage prevention via lagged variables
- [CEPR: Economics of the Kalshi Prediction Market](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market) -- Favorite-longshot bias in Kalshi pricing
- [Whelan (2025): Pricing and Losses on Kalshi](https://www.karlwhelan.com/sports-betting-kalshi-prediction-market/) -- Empirical analysis of 300K+ Kalshi contracts showing systematic biases
- [arXiv:2504.04906: Misconceptions about Brier Score](https://arxiv.org/html/2504.04906v4) -- Low Brier score does not guarantee calibration
- [scikit-learn: Probability Calibration](https://scikit-learn.org/stable/modules/calibration.html) -- Logistic regression is natively calibrated; tree models need isotonic regression
- [scikit-learn: TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) -- Correct cross-validation for temporal data
- [FanGraphs Sabermetrics Library: FIP](https://library.fangraphs.com/pitching/fip/) -- Stat stabilization rates and minimum sample sizes
- [FanGraphs Sabermetrics Library: xFIP](https://library.fangraphs.com/pitching/xfip/) -- xFIP stabilization faster than FIP/ERA
- [SI: Home Field Advantage Trending Downward in MLB](https://www.si.com/mlb/2024/01/22/home-field-advantage-baseball-trending-downward-playoffs) -- HFA declining trend, .534 in 2020s
- [ESPN: 2023 MLB Rule Changes](https://www.espn.com/mlb/story/_/id/35631564/2023-mlb-rule-changes-pitch-clock-end-shift-bigger-bases) -- Shift ban, pitch clock structural breaks
- [EVAnalytics: MLB Park Factors](https://evanalytics.com/mlb/research/park-factors) -- Multi-year park factor methodology, humidor impacts
- [Baseball Savant: Statcast Park Factors](https://baseballsavant.mlb.com/leaderboard/statcast-park-factors) -- Official Statcast-based park factors
- [Bleacher Nation: MLB Bet Pitcher Scratches](https://www.bleachernation.com/betting/2025/05/19/mlb-bets-scratches/) -- How pitcher scratches affect betting and prediction
- [Neptune.ai: Brier Score and Model Calibration](https://neptune.ai/blog/brier-score-and-model-calibration) -- Brier score decomposition best practices
- [VSiN: MLB and 2025 Home-Field Advantage](https://vsin.com/mlb/mlb-and-2025-home-field-advantage/) -- Recent HFA statistics
- [XGBoost: Parameter Tuning](https://xgboost.readthedocs.io/en/stable/tutorials/param_tuning.html) -- Regularization to prevent overfitting
- [LightGBM: Parameters Tuning](https://lightgbm.readthedocs.io/en/latest/Parameters-Tuning.html) -- Leaf-wise growth overfitting prevention

---
*Pitfalls research for: MLB Pre-Game Win Probability Modeling*
*Researched: 2026-03-28*
