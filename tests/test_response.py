import numpy as np
import optuna
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.methods import LgbmParams
from uplift.policy import CONTROL, MENS, WOMENS
from uplift.response import arm_log_loss, arm_models_oof, search_space, tune

PARAMS: LgbmParams = {"n_estimators": 30, "num_leaves": 7, "min_child_samples": 10}


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


@pytest.fixture(scope="module")
def reordered_pred():
    x, t, y, folds = _data()
    return x, arm_models_oof(x, t, y, folds, PARAMS, seed=0, arms=(WOMENS, CONTROL, MENS))


def test_arm_models_oof_gives_one_column_per_requested_arm(reordered_pred):
    x, pred = reordered_pred
    assert pred.shape == (len(x), 3)


def test_arm_models_oof_orders_columns_by_requested_arms(reordered_pred):
    x, pred = reordered_pred
    positive = x[:, 0] > 0
    assert min(pred[~positive, 0].mean(), pred[positive, 2].mean()) > 0.8


LOSS_T = np.array([1, 1, 2, 2, 0, 0])
LOSS_Y = np.array([1, 0, 1, 0, 1, 0])
PROBS = arrays(np.float64, (len(LOSS_T), 2), elements=st.floats(min_value=0.01, max_value=0.99))


@settings(max_examples=30, deadline=None)
@given(PROBS, PROBS)
def test_arm_log_loss_ignores_control_rows_and_other_mail_column(pred, other):
    own = np.arange(len(LOSS_T))[LOSS_T > 0], LOSS_T[LOSS_T > 0] - 1
    other[own] = pred[own]
    assert arm_log_loss(other, LOSS_T, LOSS_Y) == pytest.approx(arm_log_loss(pred, LOSS_T, LOSS_Y))


@settings(max_examples=30, deadline=None)
@given(PROBS)
def test_arm_log_loss_sums_each_mail_log_loss_on_its_own_customers(pred):
    expected = 0.0
    for arm in (MENS, WOMENS):
        y, p = LOSS_Y[arm == LOSS_T], pred[arm == LOSS_T, arm - 1]
        expected -= np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    assert arm_log_loss(pred, LOSS_T, LOSS_Y) == pytest.approx(expected)


@pytest.fixture(scope="module")
def tuned_params():
    x, t, y, folds = _data(n=300)
    params, _ = tune(x, t, y, folds, n_trials=1, seed=0)
    return params


def test_tune_fixes_subsample_freq(tuned_params):
    assert tuned_params["subsample_freq"] == 1


def test_tune_returns_every_search_space_param(tuned_params):
    assert set(tuned_params) == set(search_space(optuna.create_study().ask()))


def test_held_out_fold_labels_do_not_reach_its_predictions():
    rng = np.random.default_rng(1)
    n = 1500
    x = rng.normal(size=(n, 2))
    t = np.tile([0, 1, 2], n // 3)
    folds = np.arange(n) % 5
    y = np.where(folds == 0, 1, rng.random(n) < 0.2).astype(int)
    pred = arm_models_oof(x, t, y, folds, PARAMS, seed=0)
    assert pred[folds == 0].mean() < 0.4
