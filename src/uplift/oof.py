from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from uplift.policy import N_ARMS


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


def within_arm_r2(
    mu: np.ndarray, treatment: np.ndarray, outcome: np.ndarray, folds: np.ndarray
) -> pd.DataFrame:
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome, dtype=float)

    def arm_mean(train: np.ndarray, test: np.ndarray) -> np.ndarray:
        means = [outcome[train & (treatment == arm)].mean() for arm in range(N_ARMS)]
        return np.tile(means, (int(test.sum()), 1))

    rows = np.arange(len(treatment))
    own = mu[rows, treatment]
    base = oof_predict(arm_mean, folds)[rows, treatment]
    return pd.DataFrame(
        [
            {
                "treatment_id": arm,
                "r2": float(
                    1 - np.mean((outcome[k] - own[k]) ** 2) / np.mean((outcome[k] - base[k]) ** 2)
                ),
            }
            for arm in range(N_ARMS)
            for k in [treatment == arm]
        ]
    )


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
