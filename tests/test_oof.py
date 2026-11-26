import numpy as np
import pandas as pd
import pytest

from uplift.features import feature_matrix
from uplift.oof import oof_predict, outcome_model_oof, within_arm_r2


def test_oof_predict_never_uses_own_fold():
    folds = np.array([0, 1, 2, 0, 1, 2])

    def fit_predict(train, test):
        assert not (train & test).any()
        return np.column_stack([np.flatnonzero(test), folds[train].sum() * np.ones(test.sum())])

    out = oof_predict(fit_predict, folds)
    assert out[:, 0].tolist() == list(range(6))


def test_outcome_model_oof_gives_three_arm_probabilities():
    rng = np.random.default_rng(0)
    n = 1500
    x = rng.random(n)
    t = rng.integers(0, 3, n)
    p = np.column_stack([0.1 + 0.0 * x, 0.1 + 0.6 * x, 0.6 - 0.5 * x])[np.arange(n), t]
    y = (rng.random(n) < p).astype(int)
    mu = outcome_model_oof(pd.DataFrame({"x": x}), t, y, np.arange(n) % 5)
    assert mu.shape == (n, 3)
    assert ((mu > 0) & (mu < 1)).all()
    hi, lo = x > 0.8, x < 0.2
    assert mu[hi, 1].mean() > mu[lo, 1].mean()
    assert mu[hi, 2].mean() < mu[lo, 2].mean()


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
    assert feature_matrix(df).columns.tolist() == [
        "recency",
        "history",
        "mens",
        "womens",
        "newbie",
        "zip_code_Urban",
        "channel_Web",
    ]


R2_N = 300
R2_T = np.tile([0, 1, 2], R2_N // 3)
R2_Y = (np.random.default_rng(0).random(R2_N) < 0.3).astype(int)
R2_FOLDS = np.arange(R2_N) % 5


def _arm_mean(train, test):
    means = [R2_Y[train & (a == R2_T)].mean() for a in range(3)]
    return np.tile(means, (int(test.sum()), 1))


@pytest.mark.parametrize(
    ("pred", "r2"),
    [
        (np.tile(R2_Y[:, None], (1, 3)).astype(float), 1),
        (oof_predict(_arm_mean, R2_FOLDS), 0),
    ],
    ids=["exact", "arm_mean"],
)
def test_within_arm_r2_boundary_value(pred, r2):
    assert np.allclose(within_arm_r2(pred, R2_T, R2_Y, R2_FOLDS)["r2"], r2)


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
