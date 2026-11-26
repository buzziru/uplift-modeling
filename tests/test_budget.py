import numpy as np
import pandas as pd
import pytest

from uplift.budget import budget_differences, judge_budget


@pytest.fixture(scope="module")
def planted_table():
    rng = np.random.default_rng(0)
    n = 30_000
    t = rng.integers(0, 3, n)
    base = rng.uniform(0.05, 0.6, n)
    effect = np.where(base < 0.2, 0.3, 0.0)
    y = (rng.uniform(size=n) < base + effect * (t > 0)).astype(float)
    uplift = np.column_stack([effect, effect / 2])
    response = np.column_stack([base, base])
    table = budget_differences(uplift, response, t, y, (0.2, 1.0), n_boot=50, seed=1)
    return table.set_index("send_ratio")


def test_budget_differences_sends_ratio_of_customers(planted_table):
    assert planted_table.loc[0.2, "sends"] == 6000


def test_budget_differences_estimate_is_value_gap(planted_table):
    row = planted_table.loc[0.2]
    assert row["estimate"] == pytest.approx(row["uplift_value"] - row["response_value"])


def test_budget_differences_true_uplift_wins_small_budget(planted_table):
    assert planted_table.loc[0.2, "low"] > 0


def test_budget_differences_full_send_is_tie(planted_table):
    assert abs(planted_table.loc[1.0, "estimate"]) < 0.02


@pytest.mark.parametrize(
    ("diffs", "winner", "threshold"),
    [
        ([0.010, 0.011, 0.012], "uplift", 0.0038),
        ([-0.006, -0.005, -0.004], "response", 0.0038),
        ([0.010, -0.010, 0.012], "tie", 0.022),
    ],
    ids=["floor_uplift", "floor_response", "seed_range_tie"],
)
def test_judge_budget_picks_winner(diffs, winner, threshold):
    table = pd.DataFrame({"send_ratio": 0.1, "seed": [1, 2, 3], "estimate": diffs})
    row = judge_budget(table, 0.0038).iloc[0]
    assert (row["winner"], row["threshold"]) == (winner, pytest.approx(threshold))
