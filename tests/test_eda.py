import numpy as np
import pandas as pd
import pytest

from uplift.eda import (
    bootstrap_mean_ci,
    buyer_sample_size,
    category_shares,
    cramers_v,
    cramers_v_matrix,
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
    stacked_by_segment,
    threshold_effects,
)


def test_numeric_summary_reports_mode_share():
    df = pd.DataFrame({"h": [29.99, 29.99, 29.99, 50.0, 100.0]})
    row = numeric_summary(df, ["h"]).iloc[0]
    assert row["mode"] == 29.99
    assert row["mode_share"] == pytest.approx(0.6)
    assert (row["min"], row["max"]) == (29.99, 100.0)


def test_category_shares_sum_to_one_per_column():
    df = pd.DataFrame({"a": ["x", "y", "x", "x"], "b": [0, 1, 1, 1]})
    out = category_shares(df, ["a", "b"])
    for col in ["a", "b"]:
        assert out.loc[out["column"] == col, "share"].sum() == pytest.approx(1.0)
    assert out[(out["column"] == "a") & (out["level"] == "x")]["n"].item() == 3


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
    assert out.loc[0, "buyers"] == 1
    assert out.loc[0, "buyer_spend_mean"] == pytest.approx(50.0)
    assert out.loc[1, "spend_mean"] == pytest.approx(200.0 / 3)
    assert out.loc[1, "buyers_at_max"] == 2
    assert out.loc[0, "visit_rate"] == pytest.approx(2 / 3)


def test_cramers_v_is_one_for_identical_and_zero_for_independent():
    a = pd.Series(["x", "y"] * 50)
    assert cramers_v(a, a) == pytest.approx(1.0)
    b = pd.Series(["p"] * 50 + ["q"] * 50)
    assert cramers_v(a, b) == pytest.approx(0.0)


def test_cramers_v_matrix_is_symmetric():
    df = pd.DataFrame({"a": list("xyxyxy"), "b": list("ppqqpq"), "c": list("uuuvvv")})
    m = cramers_v_matrix(df, ["a", "b", "c"]).to_numpy()
    assert np.allclose(m, m.T)


def test_bootstrap_mean_ci_covers_mean_and_adds_pairwise_difference():
    groups = {"a": np.array([1.0, 2.0, 3.0, 4.0]), "b": np.array([10.0, 10.0, 10.0])}
    out = bootstrap_mean_ci(groups, n_boot=2000).set_index("group")
    assert out.loc["a", "mean"] == pytest.approx(2.5)
    assert out.loc["a", "ci_low"] <= 2.5 <= out.loc["a", "ci_high"]
    assert out.loc["b", "ci_low"] == pytest.approx(10.0)
    assert out.loc["a - b", "mean"] == pytest.approx(-7.5)
    assert out.loc["a - b", "ci_high"] < 0


def test_product_segment_labels_each_combination():
    df = pd.DataFrame({"mens": [1, 0, 1], "womens": [0, 1, 1]})
    assert product_segment(df).tolist() == ["mens_only", "womens_only", "both"]


def test_product_segment_rejects_no_purchase():
    with pytest.raises(KeyError):
        product_segment(pd.DataFrame({"mens": [0], "womens": [0]}))


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
    assert out.loc["a", "history_median"] == pytest.approx(100.0)
    assert out.loc["a", "multichannel_share"] == pytest.approx(0.5)
    assert out.loc["b", "n"] == 1


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


def test_group_means_interval_covers_mean(trial):
    out = group_means(trial, "seg", ["visit"])
    assert set(out["seg"]) == {"a", "b"}
    assert np.all(out["ci_low"].to_numpy() < out["mean"].to_numpy())
    assert np.all(out["mean"].to_numpy() < out["ci_high"].to_numpy())


def test_segment_effects_has_three_comparisons_per_level(trial):
    out = segment_effects(trial, "seg", "visit")
    assert len(out) == 6
    mens = out[(out["seg"] == "a") & (out["comparison"] == "Mens - None")]["effect"].item()
    a = trial[trial["seg"] == "a"]
    expected = a[a["treatment_id"] == 1]["visit"].mean() - a[a["treatment_id"] == 0]["visit"].mean()
    assert mens == pytest.approx(expected)


def test_incremental_composition_shares_sum_to_one(trial):
    out = incremental_composition(segment_effects(trial, "seg", "visit"), "seg")
    assert set(out["comparison"]) == {"Mens - None", "Womens - None"}
    for name in ["Mens - None", "Womens - None"]:
        assert out.loc[out["comparison"] == name, "share"].sum() == pytest.approx(1.0)


def test_funnel_ratio_ci_point_is_ratio_of_effects(trial):
    out = funnel_ratio_ci(trial, "seg", 1, n_boot=200).set_index("seg")
    row = out.loc["a"]
    assert row["conversion_per_visit"] == pytest.approx(
        row["conversion_effect"] / row["visit_effect"]
    )


def test_threshold_effects_one_row_per_threshold_and_treatment(trial):
    out = threshold_effects(trial, [50.0, 150.0])
    assert len(out) == 4
    assert np.abs(out.loc[out["threshold"] == 150.0, "effect"].to_numpy()).max() == 0


def test_n_per_arm_matches_formula():
    assert n_per_arm(sd=1.0, mde=1.0) == 16


def test_share_table_labels_columns_with_variable_name():
    df = pd.DataFrame({"mens": [1, 1, 0, 0], "womens": [0, 1, 1, 1]})
    out = share_table(df, "mens", "womens")
    assert list(out.columns) == ["womens=0", "womens=1"]
    assert out.loc[1, "womens=1"] == pytest.approx(0.5)


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
    assert out.loc["one", "n"] == 2
    assert out.loc["one", "history_floor"] == 200.0


def test_stacked_by_segment_labels_rows(trial):
    means = stacked_by_segment(trial, ["seg"], ["visit"], "means")
    effects = stacked_by_segment(trial, ["seg"], ["visit", "spend"], "effects")
    assert set(means["label"]) == {"seg: a", "seg: b"}
    assert len(effects) == 12


def test_buyer_sample_size_scales_by_conversion(trial):
    row = buyer_sample_size(trial, 10.0).iloc[0]
    assert row["customers_per_arm"] == pytest.approx(
        row["buyers_per_arm"] / row["mailed_conversion"]
    )
