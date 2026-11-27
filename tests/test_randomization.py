import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
from scipy import stats

from uplift.randomization import (
    ate_diff,
    funnel_ratios,
    precision_at_test_size,
    smd_table,
    srm_test,
)

EQUAL = pd.Series({0: 1, 1: 1, 2: 1})


@pytest.mark.parametrize(
    ("counts", "mismatch"),
    [({0: 1000, 1: 1010, 2: 990}, False), ({0: 1000, 1: 1200, 2: 800}, True)],
    ids=["balanced", "skewed"],
)
def test_srm_test_flags_mismatch(counts, mismatch):
    assert srm_test(pd.Series(counts), EQUAL)["mismatch"] is mismatch


COUNTS = st.lists(st.integers(min_value=1, max_value=10_000), min_size=3, max_size=3)
RATIOS = st.lists(st.integers(min_value=1, max_value=5), min_size=3, max_size=3)


@settings(max_examples=50, deadline=None)
@given(COUNTS, RATIOS)
def test_srm_test_expected_keeps_total_count(counts, ratio):
    expected = srm_test(pd.Series(counts), pd.Series(ratio))["expected"]
    assert sum(expected.values()) == pytest.approx(sum(counts), abs=0.2)


@settings(max_examples=50, deadline=None)
@given(COUNTS, RATIOS)
def test_srm_test_expected_is_proportional_to_ratio(counts, ratio):
    expected = srm_test(pd.Series(counts), pd.Series(ratio))["expected"]
    per_unit = [expected[i] / ratio[i] for i in range(3)]
    assert per_unit == pytest.approx([per_unit[0]] * 3, abs=0.1)


def test_srm_test_matches_counts_to_ratio_by_arm():
    out = srm_test(pd.Series({2: 1000, 1: 1000, 0: 2000}), pd.Series({0: 2, 1: 1, 2: 1}))
    assert out["chi2"] == pytest.approx(0.0)


@pytest.fixture
def numeric_smd():
    x = pd.DataFrame({"h": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0]})
    return smd_table(x, pd.Series([0, 0, 0, 1, 1, 1])).iloc[0]


# SMD = 평균 차 / sqrt((처치군 분산 + 대조군 분산) / 2) (Austin, 2009). 두 군 분산 1, 평균 차 1
def test_smd_table_numeric_smd_is_standardized_mean_gap(numeric_smd):
    assert numeric_smd["smd"] == pytest.approx(1.0)


def test_smd_table_numeric_row_has_no_level(numeric_smd):
    assert pd.isna(numeric_smd["level"])


@pytest.mark.parametrize(
    ("treated", "balanced"),
    [([2.0, 3.0, 4.0], False), ([1.05, 2.05, 3.05], True)],
    ids=["smd_one", "smd_005"],
)
def test_smd_table_balanced_below_threshold(treated, balanced):
    x = pd.DataFrame({"h": [1.0, 2.0, 3.0, *treated]})
    row = smd_table(x, pd.Series([0, 0, 0, 1, 1, 1])).iloc[0]
    assert bool(row["balanced"]) is balanced


def test_smd_table_row_per_level_treatment():
    x = pd.DataFrame({"zip": ["A", "B", "A", "A", "B", "B", "A", "B", "A"]})
    out = smd_table(x, pd.Series([0, 0, 0, 1, 1, 1, 2, 2, 2]))
    cells = set(zip(out["treatment"], out["level"], strict=True))
    assert cells == {(1, "A"), (1, "B"), (2, "A"), (2, "B")}


@st.composite
def two_level_trials(draw):
    n = draw(st.integers(min_value=0, max_value=36))
    level = np.r_[[0, 1, 0, 1], draw(arrays(np.int64, n, elements=st.integers(0, 1)))]
    t = np.r_[[0, 0, 1, 1], draw(arrays(np.int64, n, elements=st.integers(0, 1)))]
    return pd.DataFrame({"zip": np.where(level == 1, "A", "B")}), pd.Series(t)


@settings(max_examples=50, deadline=None)
@given(two_level_trials())
def test_smd_table_binary_levels_symmetric(trial):
    out = smd_table(*trial)
    smd = dict(zip(out["level"], out["smd"], strict=True))
    assert smd["A"] == pytest.approx(-smd["B"])


# 효과는 처치군 평균 - 대조군 평균. control=2면 대조군 평균은 0.5
def test_ate_diff_subtracts_given_control():
    y = pd.Series([0, 0, 1, 1, 0, 1])
    t = pd.Series([0, 0, 1, 1, 2, 2])
    out = ate_diff(y, t, control=2)
    assert dict(zip(out["treatment"], out["effect"], strict=True)) == {0: -0.5, 1: 0.5}


@st.composite
def two_arm_outcomes(draw):
    values = st.floats(min_value=-10, max_value=10)
    y0 = draw(arrays(np.float64, st.integers(min_value=2, max_value=20), elements=values))
    y1 = draw(arrays(np.float64, st.integers(min_value=2, max_value=20), elements=values))
    assume(np.ptp(y0) > 1e-3 and np.ptp(y1) > 1e-3)
    return y0, y1


def _ate_se(y0, y1):
    y = pd.Series(np.r_[y0, y1])
    t = pd.Series(np.r_[np.zeros(len(y0), int), np.ones(len(y1), int)])
    return float(ate_diff(y, t).iloc[0]["se"])


@settings(max_examples=50, deadline=None)
@given(two_arm_outcomes(), st.floats(min_value=-10, max_value=10))
def test_ate_diff_se_ignores_common_shift(arms, c):
    y0, y1 = arms
    assert _ate_se(y0 + c, y1 + c) == pytest.approx(_ate_se(y0, y1))


@settings(max_examples=50, deadline=None)
@given(two_arm_outcomes(), st.floats(min_value=-10, max_value=10).filter(lambda c: abs(c) > 0.01))
def test_ate_diff_se_scales_with_outcome(arms, c):
    y0, y1 = arms
    assert _ate_se(c * y0, c * y1) == pytest.approx(abs(c) * _ate_se(y0, y1))


@settings(max_examples=50, deadline=None)
@given(two_arm_outcomes(), st.integers(min_value=2, max_value=20))
def test_ate_diff_se_gets_nothing_from_constant_control(arms, n_control):
    _, y1 = arms
    assert _ate_se(np.zeros(n_control), y1) == pytest.approx(_ate_se(np.zeros(2), y1))


@settings(max_examples=50, deadline=None)
@given(two_arm_outcomes())
def test_ate_diff_matches_welch_t_statistic(arms):
    y0, y1 = arms
    y = pd.Series(np.r_[y0, y1])
    t = pd.Series(np.r_[np.zeros(len(y0), int), np.ones(len(y1), int)])
    row = ate_diff(y, t).iloc[0]
    welch, _ = stats.ttest_ind(y1, y0, equal_var=False)
    assert row["effect"] / row["se"] == pytest.approx(welch)


@settings(max_examples=30, deadline=None)
@given(two_arm_outcomes())
def test_precision_at_actual_size_equals_ate_se(arms):
    y0, y1 = arms
    y = pd.Series(np.r_[y0, y1])
    t = pd.Series(np.r_[np.zeros(len(y0), int), np.ones(len(y1), int)])
    sizes = pd.Series({0: len(y0), 1: len(y1)})
    se = precision_at_test_size(y, t, sizes).iloc[0]["se_test"]
    assert se == pytest.approx(_ate_se(y0, y1))


def test_precision_at_test_size_uses_95_interval_and_80_power():
    y = pd.Series([0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0])
    t = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    row = precision_at_test_size(y, t, pd.Series({0: 25, 1: 25})).iloc[0]
    z95, z80 = stats.norm.ppf(0.975), stats.norm.ppf(0.8)
    ratios = {
        "ci_half_width": row["ci_half_width"] / row["se_test"],
        "mde_80": row["mde_80"] / row["se_test"],
    }
    assert ratios == pytest.approx({"ci_half_width": z95, "mde_80": z95 + z80})


@settings(max_examples=30, deadline=None)
@given(
    arrays(np.float64, 8, elements=st.floats(min_value=0, max_value=1)),
    st.integers(min_value=1, max_value=10),
)
def test_precision_at_test_size_shrinks_with_square_root_of_size(y, c):
    t = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    assume(np.ptp(y[:4]) > 1e-3)
    se = [
        precision_at_test_size(pd.Series(y), t, pd.Series({0: m * 10, 1: m * 10})).iloc[0][
            "se_test"
        ]
        for m in (1, c)
    ]
    assert se[1] == pytest.approx(se[0] / math.sqrt(c))


# 대조군 기준선은 합의 비(전환 수 / 방문 수)다. 고객별 비의 평균이 아니다
def test_funnel_ratios_adds_control_baseline():
    effect = pd.DataFrame(
        {"visit": [0.1], "conversion": [0.01], "spend": [1.0]}, index=["Mens vs None"]
    )
    control = pd.DataFrame(
        {"visit": [1, 1, 0, 0], "conversion": [1, 0, 0, 0], "spend": [50.0, 0, 0, 0]}
    )
    expected = pd.DataFrame(
        {"conversion_per_visit": [0.1, 0.5], "spend_per_conversion": [100.0, 50.0]},
        index=["Mens vs None", "Control baseline"],
    )
    pd.testing.assert_frame_equal(funnel_ratios(effect, control), expected, check_like=True)
