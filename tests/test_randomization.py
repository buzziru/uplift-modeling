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


def test_srm_test_passes_design_ratio_and_flags_mismatch():
    ratio = pd.Series({0: 1, 1: 1, 2: 1})
    ok = srm_test(pd.Series({0: 1000, 1: 1010, 2: 990}), ratio)
    bad = srm_test(pd.Series({0: 1000, 1: 1200, 2: 800}), ratio)
    assert not ok["mismatch"]
    assert bad["mismatch"]
    assert ok["expected"] == {0: 1000.0, 1: 1000.0, 2: 1000.0}


def test_smd_table_numeric_matches_formula():
    x = pd.DataFrame({"h": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0]})
    t = pd.Series([0, 0, 0, 1, 1, 1])
    row = smd_table(x, t).iloc[0]
    assert row["level"] is None
    assert row["smd"] == pytest.approx(1.0)
    assert not row["balanced"]


def test_smd_table_categorical_has_one_row_per_level_and_treatment():
    x = pd.DataFrame({"zip": ["A", "B", "A", "A", "B", "B", "A", "B", "A"]})
    t = pd.Series([0, 0, 0, 1, 1, 1, 2, 2, 2])
    out = smd_table(x, t)
    assert set(zip(out["treatment"], out["level"])) == {(1, "A"), (1, "B"), (2, "A"), (2, "B")}
    a1 = out[(out["treatment"] == 1) & (out["level"] == "A")]["smd"].item()
    b1 = out[(out["treatment"] == 1) & (out["level"] == "B")]["smd"].item()
    assert a1 == pytest.approx(-b1)


def test_ate_diff_effect_and_interval():
    y = pd.Series([0, 0, 1, 1, 1, 1, 0, 1])
    t = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    row = ate_diff(y, t).iloc[0]
    assert row["effect"] == pytest.approx(0.25)
    se = np.sqrt(pd.Series([1, 1, 0, 1]).var() / 4 + pd.Series([0, 0, 1, 1]).var() / 4)
    assert row["se"] == pytest.approx(se)
    assert row["ci_low"] < row["effect"] < row["ci_high"]


def test_precision_at_test_size_scales_with_test_size():
    y = pd.Series([0.0, 1.0] * 50 + [0.0, 0.0, 1.0, 1.0] * 25)
    t = pd.Series([0] * 100 + [1] * 100)
    row = precision_at_test_size(y, t, pd.Series({0: 25, 1: 25})).iloc[0]
    se = np.sqrt(y[t == 1].var() / 25 + y[t == 0].var() / 25)
    assert row["se_test"] == pytest.approx(se)
    assert row["ci_half_width"] == pytest.approx(Z95 * se)
    assert row["mde_80"] == pytest.approx((Z95 + Z80) * se)


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
