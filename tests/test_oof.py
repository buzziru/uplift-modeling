import functools

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.features import feature_matrix
from uplift.oof import oof_predict, outcome_model_oof, within_arm_r2

FOLD_LABELS = arrays(np.int64, st.integers(min_value=1, max_value=40), elements=st.integers(-3, 50))


@settings(max_examples=50, deadline=None)
@given(FOLD_LABELS)
def test_oof_predict_places_each_prediction_on_its_own_row(folds):
    out = oof_predict(lambda train, test: np.flatnonzero(test).astype(float), folds)
    assert out.tolist() == list(range(len(folds)))


@settings(max_examples=50, deadline=None)
@given(FOLD_LABELS)
def test_oof_predict_trains_without_the_held_out_fold(folds):
    overlaps = []

    def fit_predict(train, test):
        overlaps.append(bool((train & test).any()))
        return np.zeros(int(test.sum()))

    oof_predict(fit_predict, folds)
    assert not any(overlaps)


def test_oof_predict_rejects_empty_folds():
    with pytest.raises(ValueError, match="folds"):
        oof_predict(lambda train, test: np.zeros(test.sum()), np.array([], dtype=int))


@functools.cache
def _outcome_oof():
    rng = np.random.default_rng(0)
    n = 1500
    x = rng.random(n)
    t = rng.integers(0, 3, n)
    p = np.column_stack([0.1 + 0.0 * x, 0.1 + 0.6 * x, 0.6 - 0.5 * x])[np.arange(n), t]
    y = (rng.random(n) < p).astype(int)
    return x, outcome_model_oof(pd.DataFrame({"x": x}), t, y, np.arange(n) % 5)


def test_outcome_model_oof_gives_one_column_per_arm():
    x, mu = _outcome_oof()
    assert mu.shape == (len(x), 3)


def test_outcome_model_oof_gives_probabilities():
    _, mu = _outcome_oof()
    assert ((mu > 0) & (mu < 1)).all()


@pytest.mark.parametrize(("arm", "rises"), [(1, True), (2, False)], ids=["mens", "womens"])
def test_outcome_model_oof_follows_planted_response(arm, rises):
    x, mu = _outcome_oof()
    gap = mu[x > 0.8, arm].mean() - mu[x < 0.2, arm].mean()
    assert gap > 0 if rises else gap < 0


def test_feature_matrix_drops_reference_level():
    df = pd.DataFrame(
        {
            "recency": [1, 2],
            "history": [10.0, 20.0],
            "mens": [1, 0],
            "womens": [0, 1],
            "newbie": [1, 1],
            "zip_code": ["Rural", "Urban"],
            "channel": ["Web", "Phone"],
        }
    )
    assert set(feature_matrix(df).columns) == {
        "recency",
        "history",
        "mens",
        "womens",
        "newbie",
        "zip_code_Urban",
        "channel_Web",
    }


R2_T = np.array([0, 0, 1, 1, 2, 2] * 2)
R2_Y = np.array([1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1])
R2_FOLDS = np.repeat([0, 1], 6)
OOF_ARM_MEAN = np.array([1, 1, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1, 1, 0, 0])


def _mu(own):
    mu = np.tile((1 - R2_Y)[:, None], (1, 3)).astype(float)
    mu[np.arange(len(R2_T)), R2_T] = own
    return mu


# 기준 예측은 다른 fold의 같은 처치군 평균이다(OOF_ARM_MEAN은 R2_Y에서 손으로 구함). 그 예측이면 r2 = 0
def test_within_arm_r2_is_zero_for_oof_arm_mean():
    result = within_arm_r2(_mu(OOF_ARM_MEAN), R2_T, R2_Y, R2_FOLDS)
    assert result["r2"].tolist() == pytest.approx([0.0] * 3)


R2_OUTCOMES = arrays(np.float64, len(R2_T), elements=st.floats(min_value=0, max_value=1))
R2_PREDS = arrays(np.float64, (len(R2_T), 3), elements=st.floats(min_value=0, max_value=1))


def _arms_vary(y):
    return all(np.ptp(y[arm == R2_T]) > 1e-3 for arm in range(3))


@settings(max_examples=50, deadline=None)
@given(R2_OUTCOMES, R2_PREDS)
def test_within_arm_r2_is_one_for_exact_own_arm_prediction(y, mu):
    assume(_arms_vary(y))
    mu[np.arange(len(R2_T)), R2_T] = y
    assert within_arm_r2(mu, R2_T, y, R2_FOLDS)["r2"].tolist() == pytest.approx([1.0] * 3)


@settings(max_examples=50, deadline=None)
@given(R2_OUTCOMES, R2_PREDS, R2_PREDS)
def test_within_arm_r2_ignores_other_arm_columns(y, mu, other):
    assume(_arms_vary(y))
    own = np.arange(len(R2_T)), R2_T
    other[own] = mu[own]
    before = within_arm_r2(mu, R2_T, y, R2_FOLDS)["r2"].tolist()
    assert within_arm_r2(other, R2_T, y, R2_FOLDS)["r2"].tolist() == pytest.approx(before)


@pytest.fixture
def segment_columns():
    df = pd.DataFrame(
        {
            "recency": [1, 2, 3],
            "history": [10.0, 20.0, 30.0],
            "mens": [1, 0, 1],
            "womens": [0, 1, 1],
            "newbie": [0, 1, 0],
            "zip_code": ["Urban", "Rural", "Urban"],
            "channel": ["Web", "Phone", "Web"],
        }
    )
    return feature_matrix(df, product="segment")


def test_feature_matrix_segment_drops_product_flags(segment_columns):
    assert {"mens", "womens"} & set(segment_columns.columns) == set()


def test_feature_matrix_segment_one_hot(segment_columns):
    product = segment_columns[[c for c in segment_columns.columns if c.startswith("product_")]]
    assert (product.shape[1], bool((product.sum(axis=1) <= 1).all())) == (2, True)
