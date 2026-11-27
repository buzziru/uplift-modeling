from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import matplotlib as mpl
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
from pydantic import TypeAdapter

from uplift.methods import LgbmParams, Method, Params, UrfParams
from uplift.oof import oof_predict
from uplift.policy import CONTROL, MAILS, best_action
from uplift.response import classifier as _clf
from uplift.response import search_space as lgbm_space
from uplift.value import PROPENSITY, policy_value

# causalml은 import 때 plt.style.use("fivethirtyeight")로 matplotlib 전역 설정을 바꾼다
mpl.rcdefaults()

PAIR_PROPENSITY = PROPENSITY / (2 * PROPENSITY)
FitPredict = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def _reg(params: LgbmParams, seed: int) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(**params, random_state=seed, verbose=-1)


def _pair_p(n: int) -> dict[int, np.ndarray]:
    return {mail: np.full(n, PAIR_PROPENSITY) for mail in MAILS}


# causalml 메타 학습기는 클래스마다 fit·predict 시그니처가 달라 하나의 Protocol로 맞출 수 없다
def _meta(
    build: Callable[[LgbmParams, int], Any], propensity: bool
) -> Callable[[LgbmParams, int], FitPredict]:
    def make(params: LgbmParams, seed: int) -> FitPredict:
        def fit_predict(x, t, y, x_new):
            model = build(params, seed)
            if propensity:
                model.fit(x, treatment=t, y=y, p=_pair_p(len(t)))
                return np.asarray(model.predict(x_new, p=_pair_p(len(x_new))))
            model.fit(x, treatment=t, y=y)
            return np.asarray(model.predict(x_new))

        return fit_predict

    return make


def _dr(params: LgbmParams, seed: int) -> FitPredict:
    def fit_predict(x, t, y, x_new):
        model = BaseDRLearner(learner=_reg(params, seed), control_name=CONTROL)
        model.fit(x, treatment=t, y=y, p=_pair_p(len(t)), seed=seed)
        return np.asarray(model.predict(x_new, p=_pair_p(len(x_new))))

    return fit_predict


def _urf(params: UrfParams, seed: int) -> FitPredict:
    def fit_predict(x, t, y, x_new):
        model = UpliftRandomForestClassifier(control_name=str(CONTROL), random_state=seed, **params)
        model.fit(x, treatment=np.asarray(t).astype(str), y=y)
        return np.asarray(model.predict(x_new))

    return fit_predict


def _class_transformation(params: LgbmParams, seed: int) -> FitPredict:
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


def _transformed_outcome(params: LgbmParams, seed: int) -> FitPredict:
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


def urf_space(trial: optuna.trial.BaseTrial) -> UrfParams:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 20, 100),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 100, 1000, log=True),
        "max_features": trial.suggest_int("max_features", 3, 9),
    }


@dataclass(frozen=True)
class Spec[P: (LgbmParams, UrfParams)]:
    make: Callable[[P, int], FitPredict]
    space: Callable[[optuna.trial.BaseTrial], P]
    params: TypeAdapter[P]

    def build(self, params: Params, seed: int) -> FitPredict:
        return self.make(self.params.validate_python(params), seed)


LGBM = TypeAdapter(LgbmParams)
URF = TypeAdapter(UrfParams)

METHODS: dict[Method, Spec[LgbmParams] | Spec[UrfParams]] = {
    "s_learner": Spec(
        _meta(lambda p, s: BaseSClassifier(learner=_clf(p, s), control_name=CONTROL), False),
        lgbm_space,
        LGBM,
    ),
    "t_learner": Spec(
        _meta(lambda p, s: BaseTClassifier(learner=_clf(p, s), control_name=CONTROL), False),
        lgbm_space,
        LGBM,
    ),
    "x_learner": Spec(
        _meta(
            lambda p, s: BaseXClassifier(
                outcome_learner=_clf(p, s), effect_learner=_reg(p, s), control_name=CONTROL
            ),
            True,
        ),
        lgbm_space,
        LGBM,
    ),
    "dr_learner": Spec(_dr, lgbm_space, LGBM),
    "uplift_rf": Spec(_urf, urf_space, URF),
    "class_transformation": Spec(_class_transformation, lgbm_space, LGBM),
    "transformed_outcome": Spec(_transformed_outcome, lgbm_space, LGBM),
}


def uplift_oof(
    method: Method,
    params: Params,
    seed: int,
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
) -> np.ndarray:
    fit_predict = METHODS[method].build(params, seed)
    t = np.asarray(treatment)
    y = np.asarray(outcome)
    return oof_predict(lambda tr, te: fit_predict(x[tr], t[tr], y[tr], x[te]), folds)


def tune(
    method: Method,
    x: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    folds: np.ndarray,
    n_trials: int,
    seed: int,
) -> tuple[Params, pd.DataFrame]:
    space = METHODS[method].space

    def objective(trial: optuna.Trial) -> float:
        uplift = uplift_oof(method, space(trial), seed, x, treatment, outcome, folds)
        return policy_value(best_action(uplift), treatment, outcome, "hajek")

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    return space(optuna.trial.FixedTrial(study.best_params)), study.trials_dataframe()
