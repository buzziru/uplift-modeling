from collections.abc import Callable

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from uplift.policy import N_ARMS


def load_folds(con: duckdb.DuckDBPyConnection, seed: int) -> pd.Series:
    folds = con.execute(
        "SELECT customer_id, fold FROM folds WHERE seed = $seed ORDER BY customer_id",
        {"seed": seed},
    ).df()
    return pd.Series(folds["fold"].to_numpy(), index=folds["customer_id"], name="fold")


def oof_predict(
    fit_predict: Callable[[np.ndarray, np.ndarray], np.ndarray], folds: np.ndarray
) -> np.ndarray:
    folds = np.asarray(folds)
    out = None
    for fold in np.unique(folds):
        test = folds == fold
        pred = fit_predict(~test, test)
        if out is None:
            out = np.empty((len(folds), *pred.shape[1:]))
        out[test] = pred
    assert out is not None
    return out


def outcome_model_oof(
    features: pd.DataFrame, treatment: np.ndarray, outcome: np.ndarray, folds: np.ndarray
) -> np.ndarray:
    x = features.to_numpy()
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome)

    def fit_predict(train: np.ndarray, test: np.ndarray) -> np.ndarray:
        pred = np.empty((int(test.sum()), N_ARMS))
        for arm in range(N_ARMS):
            rows = train & (treatment == arm)
            model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
            model.fit(x[rows], outcome[rows])
            pred[:, arm] = model.predict_proba(x[test])[:, 1]
        return pred

    return oof_predict(fit_predict, folds)
