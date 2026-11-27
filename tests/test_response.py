import numpy as np
import optuna
import pytest
from optuna.distributions import FloatDistribution, IntDistribution
from sklearn.metrics import log_loss

from uplift.response import arm_log_loss, arm_models_oof, search_space, tune

PARAMS = {"n_estimators": 30, "num_leaves": 7, "min_child_samples": 10}


def _data(n=600, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 2))
    t = np.tile([0, 1, 2], n // 3)
    y = np.where(t == 1, x[:, 0] > 0, np.where(t == 2, x[:, 0] <= 0, rng.random(n) < 0.2))
    folds = np.arange(n) % 5
    return x, t, y.astype(int), folds


@pytest.fixture(scope="module")
def mail_pred():
    x, t, y, folds = _data()
    return x, arm_models_oof(x, t, y, folds, PARAMS, seed=0)


def test_mail_prediction_has_one_column_per_mail(mail_pred):
    x, pred = mail_pred
    assert pred.shape == (len(x), 2)


@pytest.mark.parametrize(
    ("column", "positive", "high"),
    [(0, True, True), (0, False, False), (1, True, False), (1, False, True)],
    ids=["mens_positive", "mens_negative", "womens_positive", "womens_negative"],
)
def test_mail_columns_follow_each_arm_own_response(mail_pred, column, positive, high):
    x, pred = mail_pred
    mean = pred[(x[:, 0] > 0) == positive, column].mean()
    assert mean > 0.8 if high else mean < 0.2


def test_arm_log_loss_scores_each_mail_on_its_own_customers():
    t = np.array([1, 1, 2, 2, 0])
    y = np.array([1, 0, 1, 0, 1])
    pred = np.array([[0.9, 0.0], [0.2, 0.0], [0.0, 0.6], [0.0, 0.3], [0.5, 0.5]])
    expected = log_loss([1, 0], [0.9, 0.2]) + log_loss([1, 0], [0.6, 0.3])
    assert np.isclose(arm_log_loss(pred, t, y), expected)


def _space_bounds():
    trial = optuna.create_study().ask()
    search_space(trial)
    return {
        name: (d.low, d.high)
        for name, d in trial.distributions.items()
        if isinstance(d, FloatDistribution | IntDistribution)
    }


def test_tune_runs_requested_trials():
    x, t, y, folds = _data(n=300)
    _, trials = tune(x, t, y, folds, n_trials=3, seed=0)
    assert len(trials) == 3


def test_tune_returns_params_inside_search_space():
    x, t, y, folds = _data(n=300)
    params, _ = tune(x, t, y, folds, n_trials=3, seed=0)
    outside = {
        k: v for k, (low, high) in _space_bounds().items() if not low <= (v := params[k]) <= high
    }
    assert outside == {}


def test_held_out_fold_labels_do_not_reach_its_predictions():
    rng = np.random.default_rng(1)
    n = 1500
    x = rng.normal(size=(n, 2))
    t = np.tile([0, 1, 2], n // 3)
    folds = np.arange(n) % 5
    y = np.where(folds == 0, 1, rng.random(n) < 0.2).astype(int)
    pred = arm_models_oof(x, t, y, folds, PARAMS, seed=0)
    assert pred[folds == 0].mean() < 0.4
