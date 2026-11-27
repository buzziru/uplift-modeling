import functools
from typing import get_args

import numpy as np
import optuna
import pytest

from uplift.learners import METHODS, Method, tune, uplift_oof
from uplift.methods import LgbmParams, UrfParams

SMALL: LgbmParams = {
    "n_estimators": 60,
    "num_leaves": 7,
    "min_child_samples": 20,
    "learning_rate": 0.1,
}
SMALL_URF: UrfParams = {
    "n_estimators": 20,
    "max_depth": 4,
    "min_samples_leaf": 50,
    "max_features": 3,
}


def _planted(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    t = np.tile([0, 1, 2], n // 3)
    p = 0.2 + 0.4 * ((t == 1) & (x[:, 0] > 0))
    y = (rng.random(n) < p).astype(int)
    return x, t, y, np.arange(n) % 5


def _params(method):
    return SMALL_URF if method == "uplift_rf" else SMALL


@functools.cache
def _planted_uplift(method):
    x, t, y, folds = _planted()
    return x, uplift_oof(method, _params(method), 0, x, t, y, folds)


@pytest.mark.parametrize("method", list(METHODS))
def test_each_method_gives_one_column_per_mail(method):
    x, uplift = _planted_uplift(method)
    assert uplift.shape == (len(x), 2)


@pytest.mark.parametrize("method", list(METHODS))
def test_each_method_recovers_planted_mens_effect(method):
    x, uplift = _planted_uplift(method)
    positive = x[:, 0] > 0
    assert uplift[positive, 0].mean() - uplift[~positive, 0].mean() > 0.2


@pytest.mark.parametrize("method", list(METHODS))
def test_each_method_finds_no_womens_effect(method):
    _, uplift = _planted_uplift(method)
    assert abs(uplift[:, 1].mean()) < 0.1


@pytest.mark.parametrize("method", list(METHODS))
def test_same_seed_gives_same_uplift(method):
    x, t, y, folds = _planted(n=900)
    first = uplift_oof(method, _params(method), 0, x, t, y, folds)
    second = uplift_oof(method, _params(method), 0, x, t, y, folds)
    np.testing.assert_array_equal(first, second)


@pytest.fixture(scope="module")
def tuned():
    x, t, y, folds = _planted(n=900)
    return tune("t_learner", x, t, y, folds, n_trials=1, seed=0)


def test_tune_keeps_fixed_params_of_method_space(tuned):
    params, _ = tuned
    trial = optuna.create_study().ask()
    space = METHODS["t_learner"].space(trial)
    fixed = {k: v for k, v in space.items() if k not in trial.distributions}
    assert {k: params[k] for k in fixed} == fixed


def test_method_type_lists_every_learner():
    assert get_args(Method) == tuple(METHODS)
