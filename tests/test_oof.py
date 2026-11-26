import duckdb
import numpy as np
import pandas as pd

from uplift.features import feature_matrix
from uplift.oof import load_folds, oof_predict, outcome_model_oof, within_arm_r2


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


def test_feature_matrix_one_hot_without_reference_level():
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


def test_load_folds_reads_one_seed():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE folds AS SELECT * FROM (VALUES (2, 42, 1), (1, 42, 0), (1, 7, 3)) t(customer_id, seed, fold)"
    )
    assert load_folds(con, 42).to_dict() == {1: 0, 2: 1}


def test_within_arm_r2_is_one_for_exact_and_zero_for_arm_mean():
    rng = np.random.default_rng(0)
    n = 300
    t = np.tile([0, 1, 2], n // 3)
    y = (rng.random(n) < 0.3).astype(int)
    folds = np.arange(n) % 5
    exact = np.tile(y[:, None], (1, 3)).astype(float)
    assert np.allclose(within_arm_r2(exact, t, y, folds)["r2"], 1)

    def arm_mean(train, test):
        return np.tile([y[train & (t == a)].mean() for a in range(3)], (int(test.sum()), 1))

    assert np.allclose(within_arm_r2(oof_predict(arm_mean, folds), t, y, folds)["r2"], 0)
