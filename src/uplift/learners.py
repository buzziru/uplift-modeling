from collections.abc import Callable
from typing import Any

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from causalml.inference.meta import (
    BaseDRLearner,
    BaseSClassifier,
    BaseTClassifier,
    BaseXClassifier,
)
from causalml.inference.tree import UpliftRandomForestClassifier

from uplift.oof import oof_predict
from uplift.policy import CONTROL, MENS, WOMENS, best_action
from uplift.response import search_space as lgbm_space
from uplift.value import PROPENSITY, policy_value

MAILS = (MENS, WOMENS)
PAIR_PROPENSITY = PROPENSITY / (2 * PROPENSITY)
FitPredict = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
Make = Callable[[dict, int], FitPredict]


def _clf(params: dict, seed: int) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**params, random_state=seed, verbose=-1)


def _reg(params: dict, seed: int) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(**params, random_state=seed, verbose=-1)


def _pair_p(n: int) -> dict[int, np.ndarray]:
    return {mail: np.full(n, PAIR_PROPENSITY) for mail in MAILS}


def _meta(build: Callable[[dict, int], Any], propensity: bool) -> Make:
    def make(params: dict, seed: int) -> FitPredict:
        def fit_predict(x, t, y, x_new):
            model = build(params, seed)
            if propensity:
                model.fit(x, treatment=t, y=y, p=_pair_p(len(t)))
                return np.asarray(model.predict(x_new, p=_pair_p(len(x_new))))
            model.fit(x, treatment=t, y=y)
            return np.asarray(model.predict(x_new))

        return fit_predict

    return make


def _urf(params: dict, seed: int) -> FitPredict:
    def fit_predict(x, t, y, x_new):
        model = UpliftRandomForestClassifier(control_name=str(CONTROL), random_state=seed, **params)
        model.fit(x, treatment=np.asarray(t).astype(str), y=y)
        return np.asarray(model.predict(x_new))

    return fit_predict


def _class_transformation(params: dict, seed: int) -> FitPredict:
    def fit_predict(x, t, y, x_new):
        out = np.empty((len(x_new), len(MAILS)))
        for j, mail in enumerate(MAILS):
            rows = np.isin(t, [CONTROL, mail])
            treated = t[rows] == mail
            z = (treated == (y[rows] == 1)).astype(int)
            model = _clf(params, seed).fit(x[rows], z)
            out[:, j] = 2 * np.asarray(model.predict_proba(x_new))[:, 1] - 1
        return out

    return fit_predict


def _transformed_outcome(params: dict, seed: int) -> FitPredict:
    p = PAIR_PROPENSITY

    def fit_predict(x, t, y, x_new):
        out = np.empty((len(x_new), len(MAILS)))
        for j, mail in enumerate(MAILS):
            rows = np.isin(t, [CONTROL, mail])
            w = (t[rows] == mail).astype(float)
            target = y[rows] * (w - p) / (p * (1 - p))
            out[:, j] = np.asarray(_reg(params, seed).fit(x[rows], target).predict(x_new))
        return out

    return fit_predict


def urf_space(trial: optuna.trial.BaseTrial) -> dict:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 20, 100),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 100, 1000, log=True),
        "max_features": trial.suggest_int("max_features", 3, 9),
    }


METHODS: dict[str, tuple[Make, Callable[[optuna.trial.BaseTrial], dict]]] = {
    "s_learner": (
        _meta(lambda p, s: BaseSClassifier(learner=_clf(p, s), control_name=CONTROL), False),
        lgbm_space,
    ),
    "t_learner": (
        _meta(lambda p, s: BaseTClassifier(learner=_clf(p, s), control_name=CONTROL), False),
        lgbm_space,
    ),
    "x_learner": (
        _meta(
            lambda p, s: BaseXClassifier(
                outcome_learner=_clf(p, s), effect_learner=_reg(p, s), control_name=CONTROL
            ),
            True,
        ),
        lgbm_space,
    ),
    "dr_learner": (
        _meta(lambda p, s: BaseDRLearner(learner=_reg(p, s), control_name=CONTROL), True),
        lgbm_space,
    ),
    "uplift_rf": (_urf, urf_space),
    "class_transformation": (_class_transformation, lgbm_space),
    "transformed_outcome": (_transformed_outcome, lgbm_space),
}


def uplift_oof(
    method: str,
    params: dict,
    seed: int,
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
) -> np.ndarray:
    fit_predict = METHODS[method][0](params, seed)
    t = np.asarray(treatment)
    y = np.asarray(outcome)
    return oof_predict(lambda tr, te: fit_predict(x[tr], t[tr], y[tr], x[te]), folds)


def tune(
    method: str,
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
    n_trials: int,
    seed: int,
) -> tuple[dict, pd.DataFrame]:
    space = METHODS[method][1]

    def objective(trial: optuna.Trial) -> float:
        uplift = uplift_oof(method, space(trial), seed, x, treatment, outcome, folds)
        return policy_value(best_action(uplift), treatment, outcome, "hajek")

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    return space(optuna.trial.FixedTrial(study.best_params)), study.trials_dataframe()
