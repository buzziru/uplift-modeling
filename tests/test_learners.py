from typing import get_args

import numpy as np
import pytest

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


def test_tune_returns_fixed_params_of_the_method_space():
    x, t, y, folds = _planted(n=900)
    params, trials = tune("t_learner", x, t, y, folds, n_trials=2, seed=0)
    assert len(trials) == 2
    assert params["subsample_freq"] == 1
    assert 7 <= params["num_leaves"] <= 63


def test_method_type_lists_every_learner():
    assert get_args(Method) == tuple(METHODS)
