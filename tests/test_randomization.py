import numpy as np
import pandas as pd
import pytest

from uplift.randomization import (
    Z80,
    Z95,
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


def test_srm_test_expected_follows_ratio():
    out = srm_test(pd.Series({0: 1000, 1: 1010, 2: 990}), EQUAL)
    assert out["expected"] == {0: 1000.0, 1: 1000.0, 2: 1000.0}


def test_smd_table_numeric_matches_formula():
    x = pd.DataFrame({"h": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0]})
    t = pd.Series([0, 0, 0, 1, 1, 1])
    row = smd_table(x, t).iloc[0]
    assert row["level"] is None
    assert row["smd"] == pytest.approx(1.0)
    assert not row["balanced"]


@pytest.fixture
def zip_smd():
    x = pd.DataFrame({"zip": ["A", "B", "A", "A", "B", "B", "A", "B", "A"]})
    return smd_table(x, pd.Series([0, 0, 0, 1, 1, 1, 2, 2, 2]))


def test_smd_table_row_per_level_treatment(zip_smd):
    cells = set(zip(zip_smd["treatment"], zip_smd["level"], strict=True))
    assert cells == {(1, "A"), (1, "B"), (2, "A"), (2, "B")}


def test_smd_table_binary_levels_symmetric(zip_smd):
    smd = zip_smd[zip_smd["treatment"] == 1].set_index("level")["smd"]
    assert smd["A"] == pytest.approx(-smd["B"])


@pytest.fixture
def ate_row():
    y = pd.Series([0, 0, 1, 1, 1, 1, 0, 1])
    t = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    return ate_diff(y, t).iloc[0]


def test_ate_diff_effect_is_mean_diff(ate_row):
    assert ate_row["effect"] == pytest.approx(0.25)


def test_ate_diff_se_unpooled(ate_row):
    se = np.sqrt(pd.Series([1, 1, 0, 1]).var() / 4 + pd.Series([0, 0, 1, 1]).var() / 4)
    assert ate_row["se"] == pytest.approx(se)


def test_ate_diff_ci_brackets_effect(ate_row):
    assert ate_row["ci_low"] < ate_row["effect"] < ate_row["ci_high"]


def test_precision_at_test_size_scales_with_test_size():
    y = pd.Series([0.0, 1.0] * 50 + [0.0, 0.0, 1.0, 1.0] * 25)
    t = pd.Series([0] * 100 + [1] * 100)
    row = precision_at_test_size(y, t, pd.Series({0: 25, 1: 25})).iloc[0]
    se = np.sqrt(y[t == 1].var() / 25 + y[t == 0].var() / 25)
    assert row["se_test"] == pytest.approx(se)
    assert row["ci_half_width"] == pytest.approx(Z95 * se)
    assert row["mde_80"] == pytest.approx((Z95 + Z80) * se)
    assert (row["n_treatment"], row["n_control"]) == (25, 25)


def test_funnel_ratios_adds_control_baseline():
    effect = pd.DataFrame(
        {"visit": [0.1], "conversion": [0.01], "spend": [1.0]}, index=["Mens vs None"]
    )
    control = pd.DataFrame(
        {"visit": [1, 1, 0, 0], "conversion": [1, 0, 0, 0], "spend": [50.0, 0, 0, 0]}
    )
    out = funnel_ratios(effect, control)
    assert out.loc["Mens vs None"].tolist() == pytest.approx([0.1, 100.0])
    assert out.loc["Control baseline"].tolist() == pytest.approx([0.5, 50.0])
