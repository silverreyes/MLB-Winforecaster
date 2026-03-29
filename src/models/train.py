"""Model factory functions for MLB win probability models.

Three factory functions that create fresh (unfitted) model instances:
- make_lr_pipeline: Logistic Regression with StandardScaler + Imputer
- make_rf_pipeline: Random Forest with Imputer
- make_xgb_model: XGBoost (handles NaN natively, no pipeline wrapping)

Each factory returns a new instance so the backtest loop can train
independently per fold without state leakage.
"""

import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def make_lr_pipeline() -> Pipeline:
    """Create a Logistic Regression pipeline with scaling and imputation.

    Pipeline order: StandardScaler -> SimpleImputer(median) -> LogisticRegression.
    max_iter=500 to avoid ConvergenceWarning on ~10K-row datasets.
    penalty parameter omitted (deprecated in sklearn 1.8.0).
    """
    return Pipeline([
        ('scaler', StandardScaler()),
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', LogisticRegression(max_iter=500, random_state=42)),
    ])


def make_rf_pipeline() -> Pipeline:
    """Create a Random Forest pipeline with imputation.

    No scaling needed for tree-based models.
    SimpleImputer handles SP stat NaN (~17% missing from name-matching).
    """
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=20,
            random_state=42,
            n_jobs=-1,
        )),
    ])


def make_xgb_model() -> xgb.XGBClassifier:
    """Create an XGBoost classifier configured for probability estimation.

    No Pipeline wrapping -- XGBoost handles NaN natively.
    Early stopping configured via early_stopping_rounds; caller must
    provide eval_set in fit() call.
    use_label_encoder parameter omitted (removed in xgboost 2.x).
    """
    return xgb.XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        reg_alpha=1.0,
        reg_lambda=2.0,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        early_stopping_rounds=20,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
    )
