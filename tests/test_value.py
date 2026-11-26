import functools
from itertools import permutations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.policy import all_mens, fixed, top_k, uniform
from uplift.value import choose_estimator, compare_methods, policy_value, value_interval

POTENTIAL = np.array([[0, 1, 0], [1, 1, 1], [0, 0, 0], [0, 0, 1], [1, 0, 1], [0, 1, 0]])
CHOICE = np.array([1, 1, 2, 2, 0, 1])
PRED = np.array([0.7, 0.8, 0.3, 0.6, 0.6, 0.6])


def assignments():
    seen = set()
    for perm in permutations([0, 0, 1, 1, 2, 2]):
        if perm not in seen:
            seen.add(perm)
            yield np.array(perm)


def estimates(method, pred=None):
    policy = fixed(CHOICE)
    mu = None if pred is None else np.repeat(pred[:, None], 3, axis=1)
    values = []
    for t in assignments():
        y = POTENTIAL[np.arange(6), t]
        if method == "hajek" and not (t == CHOICE).any():
            continue
        values.append(policy_value(policy, t, y, method, mu))
    return np.array(values)


def _summary(values):
    return {"n": len(values), "mean": values.mean(), "std": values.std()}


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("ipw", {"n": 90, "mean": 5 / 6, "std": 0.538}),
        ("hajek", {"n": 81, "mean": 0.841, "std": 0.245}),
    ],
)
def test_six_customer_example_over_all_assignments(method, expected):
    assert _summary(estimates(method)) == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize(
    ("pred", "std"), [(PRED, 0.203), (np.full(6, 0.5), 0.284), (np.zeros(6), 0.538)]
)
def test_aipw_six_customer_example(pred, std):
    aipw = estimates("aipw", pred)
    assert (aipw.mean(), aipw.std()) == pytest.approx((5 / 6, std), abs=1e-3)


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=3, max_value=60), st.integers(min_value=0, max_value=10**6))
def test_aipw_with_zero_prediction_equals_ipw(n, seed):
    rng = np.random.default_rng(seed)
    t = rng.integers(0, 3, n)
    y = rng.random(n)
    policy = fixed(rng.integers(0, 3, n))
    assert policy_value(policy, t, y, "aipw", np.zeros((n, 3))) == pytest.approx(
        policy_value(policy, t, y, "ipw")
    )


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=3, max_value=60), st.integers(min_value=0, max_value=10**6))
def test_hajek_stays_within_outcome_range(n, seed):
    rng = np.random.default_rng(seed)
    t = rng.integers(0, 3, n)
    y = rng.random(n)
    policy = fixed(t)
    value = policy_value(policy, t, y, "hajek")
    assert y.min() - 1e-12 <= value <= y.max() + 1e-12


def test_uniform_policy_ipw_is_mean_of_arm_contributions():
    t = np.array([0, 1, 2, 0, 1, 2])
    y = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 1.0])
    assert policy_value(uniform(6), t, y, "ipw") == pytest.approx(y.mean())


def planted(n=60_000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.random(n)
    t = rng.integers(0, 3, n)
    p = np.column_stack([0.1 + 0.3 * x, 0.15 + 0.3 * x, 0.1 + 0.5 * x])
    y = (rng.random(n) < p[np.arange(n), t]).astype(float)
    return t, y, p


@functools.cache
def _planted_table():
    t, y, p = planted()
    policy = top_k(p[:, 1:] - p[:, :1], k=len(t) // 2)
    truth = (policy * p).sum(axis=1).mean()
    return compare_methods(policy, t, y, p, n_boot=1000), truth


def test_estimator_intervals_cover_planted_policy_value():
    table, truth = _planted_table()
    assert bool(((table["low"] <= truth) & (truth <= table["high"])).all())


@pytest.mark.parametrize("method", ["hajek", "aipw"])
def test_estimator_se_below_ipw(method):
    table, _ = _planted_table()
    se = dict(zip(table["method"], table["se"], strict=True))
    assert se[method] < se["ipw"]


def test_difference_interval_covers_planted_difference():
    t, y, p = planted(seed=1)
    policy = top_k(p[:, 1:] - p[:, :1], k=len(t))
    baseline = all_mens(len(t))
    truth = ((policy - baseline) * p).sum(axis=1).mean()
    result = value_interval(policy, t, y, "aipw", p, baseline=baseline, n_boot=200)
    assert result["low"] <= truth <= result["high"]


def test_aipw_requires_mu():
    with pytest.raises(ValueError, match="mu"):
        policy_value(uniform(3), np.array([0, 1, 2]), np.ones(3), "aipw")


def _widths(ipw, hajek, aipw):
    return pd.DataFrame({"ipw": ipw, "hajek": hajek, "aipw": aipw})


@pytest.mark.parametrize(
    ("hajek", "aipw", "estimator"),
    [
        ([0.9, 0.9], [0.85, 0.85], "hajek"),
        ([0.9, 0.9], [0.81, 0.81], "aipw"),
        ([1.1, 1.1], [0.95, 0.95], "ipw"),
    ],
    ids=["hajek_base", "aipw_margin_met", "ipw_base"],
)
def test_choose_estimator_picks(hajek, aipw, estimator):
    assert choose_estimator(_widths([1.0, 1.0], hajek, aipw), 0.1)["estimator"] == estimator


def test_choose_estimator_counts_disagreement():
    result = choose_estimator(_widths([1.0, 1.0, 1.0], [0.8, 0.8, 1.1], [0.6, 0.95, 0.95]), 0.1)
    counts = {
        k: result[k]
        for k in ("base", "estimator", "hajek_vs_ipw_disagree", "aipw_vs_base_disagree")
    }
    assert counts == {
        "base": "hajek",
        "estimator": "hajek",
        "hajek_vs_ipw_disagree": 1,
        "aipw_vs_base_disagree": 1,
    }
