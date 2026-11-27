import functools
from itertools import permutations

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.policy import all_mens, fixed, top_k, uniform
from uplift.value import choose_estimator, compare_estimators, policy_value, value_interval

POTENTIAL = np.array([[0, 1, 0], [1, 1, 1], [0, 0, 0], [0, 0, 1], [1, 0, 1], [0, 1, 0]])
CHOICE = np.array([1, 1, 2, 2, 0, 1])
PRED = np.array([0.7, 0.8, 0.3, 0.6, 0.6, 0.6])
# 참 정책 가치: 고객마다 정책이 고른 처치의 잠재 결과 POTENTIAL[i, CHOICE[i]]의 평균
TRUE_VALUE = 5 / 6


def assignments():
    seen = set()
    for perm in permutations([0, 0, 1, 1, 2, 2]):
        if perm not in seen:
            seen.add(perm)
            yield np.array(perm)


def estimates(estimator, pred=None):
    policy = fixed(CHOICE)
    mu = None if pred is None else np.repeat(pred[:, None], 3, axis=1)
    values = []
    for t in assignments():
        y = POTENTIAL[np.arange(6), t]
        if estimator == "hajek" and not (t == CHOICE).any():
            continue
        values.append(policy_value(policy, t, y, estimator, mu))
    return np.array(values)


def test_ipw_is_unbiased_over_all_assignments():
    assert estimates("ipw").mean() == pytest.approx(TRUE_VALUE)


def test_hajek_varies_less_than_ipw_over_all_assignments():
    assert estimates("hajek").std() < estimates("ipw").std()


@pytest.mark.parametrize("pred", [PRED, np.full(6, 0.5)], ids=["model", "constant"])
def test_aipw_is_unbiased_over_all_assignments(pred):
    assert estimates("aipw", pred).mean() == pytest.approx(TRUE_VALUE)


def test_aipw_varies_less_with_better_prediction():
    stds = [estimates("aipw", PRED).std(), estimates("aipw", np.full(6, 0.5)).std()]
    assert stds[0] < stds[1] < estimates("ipw").std()


ARM = st.integers(min_value=0, max_value=2)
UNIT = st.floats(min_value=0, max_value=1)


@st.composite
def trials(draw, with_mu=False):
    n = draw(st.integers(min_value=3, max_value=40))
    t = draw(arrays(np.int64, n, elements=ARM))
    y = draw(arrays(np.float64, n, elements=UNIT))
    policy = fixed(draw(arrays(np.int64, n, elements=ARM)))
    if not with_mu:
        return t, y, policy
    return t, y, policy, draw(arrays(np.float64, (n, 3), elements=UNIT))


def _matched(policy, t):
    return bool(policy[np.arange(len(t)), t].any())


@settings(max_examples=50, deadline=None)
@given(trials())
def test_aipw_with_zero_prediction_equals_ipw(trial):
    t, y, policy = trial
    assert policy_value(policy, t, y, "aipw", np.zeros((len(t), 3))) == pytest.approx(
        policy_value(policy, t, y, "ipw")
    )


@settings(max_examples=50, deadline=None)
@given(trials())
def test_hajek_stays_within_outcome_range(trial):
    t, y, policy = trial
    assume(_matched(policy, t))
    value = policy_value(policy, t, y, "hajek")
    assert y.min() - 1e-9 <= value <= y.max() + 1e-9


@settings(max_examples=50, deadline=None)
@given(trials(), st.floats(min_value=-10, max_value=10))
def test_hajek_shifts_with_outcome(trial, c):
    t, y, policy = trial
    assume(_matched(policy, t))
    assert policy_value(policy, t, y + c, "hajek") == pytest.approx(
        policy_value(policy, t, y, "hajek") + c, abs=1e-9
    )


@settings(max_examples=50, deadline=None)
@given(trials(with_mu=True), st.floats(min_value=-10, max_value=10))
def test_aipw_shifts_with_outcome_and_prediction(trial, c):
    t, y, policy, mu = trial
    assert policy_value(policy, t, y + c, "aipw", mu + c) == pytest.approx(
        policy_value(policy, t, y, "aipw", mu) + c, abs=1e-9
    )


@settings(max_examples=50, deadline=None)
@given(trials())
def test_uniform_policy_ipw_is_outcome_mean(trial):
    t, y, _ = trial
    assert policy_value(uniform(len(t)), t, y, "ipw") == pytest.approx(y.mean())


@pytest.mark.parametrize("estimator", ["ipw", "hajek"])
def test_interval_with_baseline_estimates_value_difference(estimator):
    t = np.tile([0, 1, 2], 20)
    y = np.tile([0.0, 1.0, 0.5, 0.2, 0.9], 12)
    policy = fixed(np.where(np.arange(60) % 3 == 0, (t + 1) % 3, t))
    baseline = fixed(np.where(np.arange(60) % 2 == 0, t, (t + 2) % 3))
    result = value_interval(policy, t, y, estimator, baseline=baseline, n_boot=2)
    assert result["estimate"] == pytest.approx(
        policy_value(policy, t, y, estimator) - policy_value(baseline, t, y, estimator)
    )


@settings(max_examples=30, deadline=None)
@given(trials(), st.floats(min_value=0.5, max_value=0.9))
def test_higher_level_does_not_narrow_interval(trial, level):
    t, y, policy = trial
    low, high = (
        value_interval(policy, t, y, "ipw", n_boot=50, level=lv) for lv in (level, level + 0.09)
    )
    assert high["high"] - high["low"] >= low["high"] - low["low"] - 1e-12


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
    return compare_estimators(policy, t, y, p, n_boot=1000), truth


def test_estimator_intervals_cover_planted_policy_value():
    table, truth = _planted_table()
    assert bool(((table["low"] <= truth) & (truth <= table["high"])).all())


@pytest.mark.parametrize("estimator", ["hajek", "aipw"])
def test_estimator_se_below_ipw(estimator):
    table, _ = _planted_table()
    se = dict(zip(table["method"], table["se"], strict=True))
    assert se[estimator] < se["ipw"]


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


def test_choose_estimator_keeps_ipw_base_when_hajek_ties():
    assert choose_estimator(_widths([1.0], [1.0], [1.0]), 0.25)["base"] == "ipw"


def test_choose_estimator_takes_aipw_exactly_at_margin():
    assert choose_estimator(_widths([1.0], [2.0], [0.75]), 0.25)["estimator"] == "aipw"


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
