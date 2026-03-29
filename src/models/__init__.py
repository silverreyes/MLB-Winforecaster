"""Model training, calibration, and evaluation modules for MLB Win Probability.

Submodules:
    feature_sets: Feature column definitions (full vs core)
    train: Model factory functions (LR, RF, XGBoost pipelines)
    calibrate: Post-hoc isotonic calibration
    backtest: Walk-forward fold generation and backtest loop
    evaluate: Brier score computation and calibration curves
"""
