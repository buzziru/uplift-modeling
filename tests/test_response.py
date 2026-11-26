import numpy as np
from sklearn.metrics import log_loss

from uplift.response import arm_log_loss, arm_models_oof, tune

PARAMS = {"n_estimators": 30, "num_leaves": 7, "min_child_samples": 10}


def _data(n=600, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 2))
    t = np.tile([0, 1, 2], n // 3)
    y = np.where(t == 1, x[:, 0] > 0, np.where(t == 2, x[:, 0] <= 0, rng.random(n) < 0.2))
    folds = np.arange(n) % 5
    return x, t, y.astype(int), folds


def test_mail_columns_follow_each_arm_own_response():
    x, t, y, folds = _data()
    pred = arm_models_oof(x, t, y, folds, PARAMS, seed=0)
    assert pred.shape == (len(t), 2)
    positive = x[:, 0] > 0
    assert pred[positive, 0].mean() > 0.8
    assert pred[~positive, 0].mean() < 0.2
    assert pred[positive, 1].mean() < 0.2
    assert pred[~positive, 1].mean() > 0.8


def test_arm_log_loss_scores_each_mail_on_its_own_customers():
    t = np.array([1, 1, 2, 2, 0])
    y = np.array([1, 0, 1, 0, 1])
    pred = np.array([[0.9, 0.0], [0.2, 0.0], [0.0, 0.6], [0.0, 0.3], [0.5, 0.5]])
    expected = log_loss([1, 0], [0.9, 0.2]) + log_loss([1, 0], [0.6, 0.3])
    assert np.isclose(arm_log_loss(pred, t, y), expected)


def test_tune_returns_params_inside_search_space():
    x, t, y, folds = _data(n=300)
    params, trials = tune(x, t, y, folds, n_trials=3, seed=0)
    assert len(trials) == 3
    assert 7 <= params["num_leaves"] <= 63
    assert 0.01 <= params["learning_rate"] <= 0.1
    assert 100 <= params["n_estimators"] <= 1000
    assert 20 <= params["min_child_samples"] <= 500
    assert 0.5 <= params["subsample"] <= 1 and params["subsample_freq"] == 1
    assert 0.5 <= params["colsample_bytree"] <= 1


def test_held_out_fold_labels_do_not_reach_its_predictions():
    rng = np.random.default_rng(1)
    n = 1500
    x = rng.normal(size=(n, 2))
    t = np.tile([0, 1, 2], n // 3)
    folds = np.arange(n) % 5
    y = np.where(folds == 0, 1, rng.random(n) < 0.2).astype(int)
    pred = arm_models_oof(x, t, y, folds, PARAMS, seed=0)
    assert pred[folds == 0].mean() < 0.4
