from typing import get_args

import numpy as np
import optuna
import pytest
from optuna.distributions import FloatDistribution, IntDistribution

from uplift.learners import METHODS, Method, tune, uplift_oof

SMALL = {"n_estimators": 60, "num_leaves": 7, "min_child_samples": 20, "learning_rate": 0.1}
SMALL_URF = {"n_estimators": 20, "max_depth": 4, "min_samples_leaf": 50, "max_features": 3}


def _planted(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    t = np.tile([0, 1, 2], n // 3)
    p = 0.2 + 0.4 * ((t == 1) & (x[:, 0] > 0))
    y = (rng.random(n) < p).astype(int)
    return x, t, y, np.arange(n) % 5


@pytest.mark.parametrize("method", list(METHODS))
def test_each_method_recovers_planted_mens_effect(method):
    x, t, y, folds = _planted()
    params = SMALL_URF if method == "uplift_rf" else SMALL
    uplift = uplift_oof(method, params, 0, x, t, y, folds)
    assert uplift.shape == (len(t), 2)
    positive = x[:, 0] > 0
    assert uplift[positive, 0].mean() - uplift[~positive, 0].mean() > 0.2
    assert abs(uplift[:, 1].mean()) < 0.1


@pytest.mark.parametrize("method", list(METHODS))
def test_same_seed_gives_same_uplift(method):
    x, t, y, folds = _planted(n=900)
    params = SMALL_URF if method == "uplift_rf" else SMALL
    first = uplift_oof(method, params, 0, x, t, y, folds)
    second = uplift_oof(method, params, 0, x, t, y, folds)
    np.testing.assert_array_equal(first, second)


@pytest.fixture(scope="module")
def tuned():
    x, t, y, folds = _planted(n=900)
    return tune("t_learner", x, t, y, folds, n_trials=2, seed=0)


def _space(method):
    trial = optuna.create_study().ask()
    space = METHODS[method][1](trial)
    return space, trial.distributions


def test_tune_runs_requested_trials(tuned):
    _, trials = tuned
    assert len(trials) == 2


def test_tune_returns_params_inside_method_space(tuned):
    params, _ = tuned
    _, dists = _space("t_learner")
    outside = {
        k: v
        for k, d in dists.items()
        if isinstance(d, FloatDistribution | IntDistribution)
        and not d.low <= (v := params[k]) <= d.high
    }
    assert outside == {}


def test_tune_keeps_fixed_params_of_method_space(tuned):
    params, _ = tuned
    space, dists = _space("t_learner")
    fixed = {k: v for k, v in space.items() if k not in dists}
    assert {k: params[k] for k in fixed} == fixed


def test_method_type_lists_every_learner():
    assert get_args(Method) == tuple(METHODS)
