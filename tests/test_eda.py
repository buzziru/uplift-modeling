import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
from scipy import stats

from uplift.eda import (
    bootstrap_mean_ci,
    buyer_sample_size,
    category_shares,
    cramers_v,
    cramers_v_matrix,
    effects_below_zero,
    funnel_ratio_ci,
    group_means,
    incremental_composition,
    n_per_arm,
    numeric_summary,
    outcome_summary,
    product_segment,
    profile_above_floor,
    segment_effects,
    segment_profile,
    share_table,
    spearman_matrix,
    stacked_effects,
    stacked_means,
    threshold_effects,
)


def test_numeric_summary_reports_mode_share():
    df = pd.DataFrame({"h": [29.99, 29.99, 29.99, 50.0, 100.0]})
    row = numeric_summary(df, ["h"]).iloc[0]
    expected = {"mode": 29.99, "mode_share": 0.6, "min": 29.99, "max": 100.0}
    assert {k: row[k] for k in expected} == pytest.approx(expected)


def test_category_shares_counts_each_level():
    out = category_shares(pd.DataFrame({"a": ["x", "y", "x", "x"]}), ["a"])
    assert out.set_index("level")["n"].to_dict() == {"x": 3, "y": 1}


@st.composite
def category_frames(draw, min_levels=1):
    n = draw(st.integers(min_value=2, max_value=30))
    k = draw(st.integers(min_value=1, max_value=3))
    levels = st.sampled_from(["x", "y", "z"])
    df = pd.DataFrame({f"c{j}": draw(st.lists(levels, min_size=n, max_size=n)) for j in range(k)})
    assume(all(df[c].nunique() >= min_levels for c in df.columns))
    return df


@settings(max_examples=30, deadline=None)
@given(category_frames())
def test_category_shares_sum_to_one_per_column(df):
    out = category_shares(df, list(df.columns))
    assert pd.Series(out.groupby("column")["share"].sum()).tolist() == pytest.approx(
        [1.0] * df.shape[1]
    )


@settings(max_examples=30, deadline=None)
@given(category_frames())
def test_category_shares_counts_sum_to_rows_per_column(df):
    out = category_shares(df, list(df.columns))
    assert pd.Series(out.groupby("column")["n"].sum()).tolist() == [len(df)] * df.shape[1]


def test_outcome_summary_buyer_stats_use_only_positive_spend():
    df = pd.DataFrame(
        {
            "t": [0, 0, 0, 1, 1, 1],
            "visit": [1, 1, 0, 1, 1, 1],
            "conversion": [1, 0, 0, 1, 1, 0],
            "spend": [50.0, 0, 0, 100.0, 100.0, 0],
        }
    )
    out = outcome_summary(df, "t").set_index("t")
    expected = pd.DataFrame(
        {
            "visit_rate": [2 / 3, 1.0],
            "buyers": [1, 2],
            "spend_mean": [50.0 / 3, 200.0 / 3],
            "buyer_spend_mean": [50.0, 100.0],
            "buyers_at_max": [1, 2],
        },
        index=pd.Index([0, 1], name="t"),
    )
    pd.testing.assert_frame_equal(
        pd.DataFrame(out[list(expected.columns)]), expected, check_dtype=False
    )


CRAMER_A = pd.Series(["x", "y"] * 50)


@pytest.mark.parametrize(
    ("b", "v"),
    [(CRAMER_A, 1.0), (pd.Series(["p"] * 50 + ["q"] * 50), 0.0)],
    ids=["identical", "independent"],
)
def test_cramers_v_boundary_value(b, v):
    assert cramers_v(CRAMER_A, b) == pytest.approx(v)


@settings(max_examples=30, deadline=None)
@given(category_frames(min_levels=2))
def test_cramers_v_stays_within_unit_interval(df):
    v = cramers_v(df.iloc[:, 0], df.iloc[:, -1])
    assert -1e-12 <= v <= 1 + 1e-12


@settings(max_examples=15, deadline=None)
@given(category_frames(min_levels=2))
def test_cramers_v_matrix_is_symmetric(df):
    m = cramers_v_matrix(df, list(df.columns)).to_numpy()
    assert np.allclose(m, m.T)


@settings(max_examples=15, deadline=None)
@given(category_frames(min_levels=2))
def test_cramers_v_matrix_diagonal_is_one(df):
    m = cramers_v_matrix(df, list(df.columns)).to_numpy()
    assert np.allclose(np.diag(m), 1.0)


@pytest.fixture(scope="module")
def mean_ci():
    groups = {"a": np.array([1.0, 2.0, 3.0, 4.0]), "b": np.array([10.0, 10.0, 10.0])}
    return bootstrap_mean_ci(groups, n_boot=2000).set_index("group")


def test_bootstrap_mean_ci_covers_group_mean(mean_ci):
    row = mean_ci.loc["a"]
    assert (row["mean"], row["ci_low"] <= 2.5 <= row["ci_high"]) == (pytest.approx(2.5), True)


def test_bootstrap_mean_ci_constant_group(mean_ci):
    assert mean_ci.loc["b", "ci_low"] == pytest.approx(10.0)


def test_bootstrap_mean_ci_adds_pairwise_diff(mean_ci):
    row = mean_ci.loc["a - b"]
    assert (row["mean"], row["ci_high"] < 0) == (pytest.approx(-7.5), True)


def test_product_segment_labels_each_combination():
    df = pd.DataFrame({"mens": [1, 0, 1], "womens": [0, 1, 1]})
    assert product_segment(df).tolist() == ["mens_only", "womens_only", "both"]


def test_segment_profile_shares():
    df = pd.DataFrame(
        {
            "g": ["a", "a", "b"],
            "history": [50.0, 150.0, 300.0],
            "recency": [1, 3, 5],
            "newbie": [1, 0, 1],
            "channel": ["Web", "Multichannel", "Phone"],
        }
    )
    out = segment_profile(df, "g").set_index("g")
    expected = pd.DataFrame(
        {"n": [2, 1], "history_median": [100.0, 300.0], "multichannel_share": [0.5, 0.0]},
        index=pd.Index(["a", "b"], name="g"),
    )
    pd.testing.assert_frame_equal(
        pd.DataFrame(out[list(expected.columns)]), expected, check_dtype=False
    )


@pytest.fixture
def trial() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    n = 3000
    t = np.tile([0, 1, 2], n // 3)
    seg = np.repeat(["a", "b"], n // 2)
    visit = (rng.random(n) < 0.1 + 0.1 * (t == 1) + 0.05 * (t == 2) * (seg == "b")).astype(int)
    conversion = visit * (rng.random(n) < 0.3)
    return pd.DataFrame(
        {
            "seg": seg,
            "treatment_id": t,
            "visit": visit,
            "conversion": conversion,
            "spend": conversion * 100.0,
        }
    )


@settings(max_examples=30, deadline=None)
@given(arrays(np.float64, st.integers(min_value=2, max_value=30), elements=st.floats(0, 100)))
def test_group_means_gives_normal_95_interval(y):
    assume(np.ptp(y) > 1e-3)
    row = group_means(pd.DataFrame({"g": "a", "y": y}), "g", ["y"]).iloc[0]
    low, high = stats.norm.interval(0.95, loc=y.mean(), scale=stats.sem(y))
    expected = {"mean": y.mean(), "ci_low": low, "ci_high": high}
    assert {k: row[k] for k in expected} == pytest.approx(expected, abs=1e-9)


def test_segment_effects_has_three_comparisons_per_level(trial):
    assert len(segment_effects(trial, "seg", "visit")) == 6


# 비교 이름 "A - B"는 A 평균 - B 평균. 처치군 방문율 None 0.5, Mens 1, Womens 0
def test_segment_effects_subtracts_comparison_reference():
    df = pd.DataFrame(
        {"seg": ["a"] * 6, "treatment_id": [0, 0, 1, 1, 2, 2], "visit": [0, 1, 1, 1, 0, 0]}
    )
    out = segment_effects(df, "seg", "visit")
    effects = dict(zip(out["comparison"], out["effect"], strict=True))
    assert effects == pytest.approx({"Mens - None": 0.5, "Womens - None": -0.5, "Mens - Womens": 1})


def test_incremental_composition_keeps_only_comparisons_with_no_mail(trial):
    out = incremental_composition(segment_effects(trial, "seg", "visit"), "seg")
    assert set(out["comparison"]) == {"Mens - None", "Womens - None"}


@pytest.mark.parametrize("name", ["Mens - None", "Womens - None"])
@pytest.mark.parametrize("column", ["share", "n_share"])
def test_incremental_composition_shares_sum_to_one(trial, name, column):
    out = incremental_composition(segment_effects(trial, "seg", "visit"), "seg")
    assert out.loc[out["comparison"] == name, column].sum() == pytest.approx(1.0)


# 방문 효과 0.75 - 0.25, 구매 효과 0.25 - 0, 비는 구매 효과 / 방문 효과
def test_funnel_ratio_ci_point_is_ratio_of_effects():
    arms = {
        1: ([1, 1, 1, 0], [1, 0, 0, 0]),
        0: ([0, 0, 1, 0], [0, 0, 0, 0]),
    }
    df = pd.DataFrame(
        [
            {"seg": "a", "treatment_id": t, "visit": v, "conversion": c}
            for t, (visit, conversion) in arms.items()
            for v, c in zip(visit * 5, conversion * 5, strict=True)
        ]
    )
    row = funnel_ratio_ci(df, "seg", 1, n_boot=50).iloc[0]
    expected = {"visit_effect": 0.5, "conversion_effect": 0.25, "conversion_per_visit": 0.5}
    assert {k: row[k] for k in expected} == pytest.approx(expected)


def test_threshold_effects_row_per_cell(trial):
    assert len(threshold_effects(trial, [50.0, 150.0])) == 4


def test_threshold_effects_zero_above_max(trial):
    out = threshold_effects(trial, [50.0, 150.0])
    assert np.abs(out.loc[out["threshold"] == 150.0, "effect"].to_numpy()).max() == 0


# 2((z_0.975 + z_0.8) sd / mde)^2 = 2(1.96 + 0.84)^2 = 15.7, 올려서 16
def test_n_per_arm_matches_formula():
    assert n_per_arm(sd=1.0, mde=1.0) == 16


def test_share_table_labels_columns_with_variable_name():
    df = pd.DataFrame({"mens": [1, 1, 0, 0], "womens": [0, 1, 1, 1]})
    expected = pd.DataFrame(
        {"womens=0": [0.0, 0.5], "womens=1": [1.0, 0.5]}, index=pd.Index([0, 1], name="mens")
    )
    pd.testing.assert_frame_equal(
        share_table(df, "mens", "womens"), expected, check_names=False, check_like=True
    )


def test_spearman_matrix_ranks_history_segment():
    df = pd.DataFrame(
        {"history": [10.0, 150.0, 300.0], "history_segment": ["1) a", "2) b", "3) c"]}
    )
    out = spearman_matrix(df, ["history", "history_segment"])
    assert out.loc["history", "history_segment"] == pytest.approx(1.0)


def test_profile_above_floor_uses_level_minimum():
    df = pd.DataFrame(
        {
            "p": ["both", "both", "one", "one", "one"],
            "history": [200.0, 400.0, 30.0, 250.0, 500.0],
            "recency": [1, 2, 3, 4, 5],
            "newbie": [0, 1, 0, 1, 0],
            "channel": ["Web"] * 5,
        }
    )
    out = profile_above_floor(df, "p", "both").set_index("p")
    expected = pd.DataFrame(
        {"n": [2, 2], "history_floor": [200.0, 200.0], "level_median_ratio": [1.0, 300.0 / 375.0]},
        index=pd.Index(["both", "one"], name="p"),
    )
    pd.testing.assert_frame_equal(
        pd.DataFrame(out[list(expected.columns)]), expected, check_dtype=False
    )


def test_stacked_means_labels_rows(trial):
    assert set(stacked_means(trial, ["seg"], ["visit"])["label"]) == {"seg: a", "seg: b"}


def test_stacked_effects_row_per_outcome(trial):
    assert len(stacked_effects(trial, ["seg"], ["visit", "spend"])) == 12


BUYERS = pd.DataFrame(
    {
        "treatment_id": [0, 0, 1, 1, 2, 2, 2],
        "conversion": [1, 0, 1, 0, 0, 0, 0],
        "spend": [10.0, 0, 30.0, 0, 0, 0, 0],
    }
)


def test_buyer_sample_size_sizes_buyers_by_buyer_spend_sd():
    row = buyer_sample_size(BUYERS, 10.0).iloc[0]
    assert row["buyers_per_arm"] == n_per_arm(sd=math.sqrt(200), mde=10.0)


def test_buyer_sample_size_doubles_customers_when_mailed_conversion_halves():
    mailed_no_buy = pd.DataFrame(
        {"treatment_id": [1] * 5, "conversion": [0] * 5, "spend": [0.0] * 5}
    )
    rows = [
        buyer_sample_size(df, 10.0).iloc[0]["customers_per_arm"]
        for df in (BUYERS, pd.concat([BUYERS, mailed_no_buy], ignore_index=True))
    ]
    assert rows[1] == pytest.approx(2 * rows[0])


def test_buyer_sample_size_reports_current_arm_size_range():
    row = buyer_sample_size(BUYERS, 10.0).iloc[0]
    assert (row["current_customers_per_arm_min"], row["current_customers_per_arm_max"]) == (2, 3)


def test_effects_below_zero_keeps_only_clearly_negative_rows():
    effects = pd.DataFrame(
        {
            "comparison": ["Mens - None", "Mens - None", "Mens - Womens"],
            "ci_high": [-0.01, 0.02, -0.03],
        }
    )
    assert effects_below_zero(effects, ["Mens - None"])["ci_high"].tolist() == [-0.01]
