import numpy as np
import pandas as pd
import pytest

from uplift.randomization import ate_diff, smd_table, srm_test


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
