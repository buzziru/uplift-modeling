import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import log_loss

from uplift.oof import oof_predict
from uplift.policy import MAILS


def classifier(params: dict, seed: int) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**params, random_state=seed, verbose=-1)


def arm_models_oof(
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
    params: dict,
    seed: int,
    arms: tuple[int, ...] = MAILS,
) -> np.ndarray:
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome)

    def fit_predict(train: np.ndarray, test: np.ndarray) -> np.ndarray:
        pred = np.empty((int(test.sum()), len(arms)))
        for j, arm in enumerate(arms):
            rows = train & (treatment == arm)
            model = classifier(params, seed)
            model.fit(x[rows], outcome[rows])
            pred[:, j] = np.asarray(model.predict_proba(x[test]))[:, 1]
        return pred

    return oof_predict(fit_predict, folds)


def arm_log_loss(
    pred: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    arms: tuple[int, ...] = MAILS,
) -> float:
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome)
    return float(
        sum(
            log_loss(outcome[treatment == arm], pred[treatment == arm, j], labels=[0, 1])
            for j, arm in enumerate(arms)
        )
    )


def search_space(trial: optuna.trial.BaseTrial) -> dict:
    return {
        "num_leaves": trial.suggest_int("num_leaves", 7, 63, log=True),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "subsample_freq": 1,
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
    }


def tune(
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
    n_trials: int,
    seed: int,
) -> tuple[dict, pd.DataFrame]:
    def objective(trial: optuna.Trial) -> float:
        pred = arm_models_oof(x, treatment, outcome, folds, search_space(trial), seed)
        return arm_log_loss(pred, treatment, outcome)

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    return {**study.best_params, "subsample_freq": 1}, study.trials_dataframe()
