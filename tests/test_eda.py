import numpy as np
import pandas as pd
import pytest

from uplift.eda import (
    bootstrap_mean_ci,
    category_shares,
    cramers_v,
    cramers_v_matrix,
    numeric_summary,
    outcome_summary,
    product_segment,
    segment_profile,
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
