"""Variance Inflation Factor (VIF) analysis using sklearn LinearRegression.

Computes VIF for each feature in a DataFrame to detect multicollinearity.
VIF > 10 indicates problematic multicollinearity; VIF > 100 is severe.

Uses sklearn.linear_model.LinearRegression R^2 method to avoid
adding heavy external dependencies.
"""

import pandas as pd
from sklearn.linear_model import LinearRegression


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """Compute VIF for each feature using sklearn LinearRegression R^2 method.

    VIF_i = 1 / (1 - R^2_i) where R^2_i is from regressing feature i on all others.
    VIF > 10 indicates problematic multicollinearity.
    VIF > 100 indicates severe multicollinearity.

    Args:
        X: Feature DataFrame (must have no NaN values).
    Returns:
        DataFrame with columns ['feature', 'VIF'], sorted by VIF descending.
    """
    features = X.columns.tolist()
    vif_data = []

    for feature in features:
        y_col = X[feature].values
        X_others = X.drop(columns=[feature]).values

        reg = LinearRegression()
        reg.fit(X_others, y_col)
        r_squared = reg.score(X_others, y_col)

        if r_squared >= 1.0:
            vif = float('inf')
        else:
            vif = round(1.0 / (1.0 - r_squared), 2)

        vif_data.append({'feature': feature, 'VIF': vif})

    result = pd.DataFrame(vif_data)
    result = result.sort_values('VIF', ascending=False).reset_index(drop=True)
    return result
