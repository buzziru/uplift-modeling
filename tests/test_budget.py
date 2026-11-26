import numpy as np
import pandas as pd

from uplift.budget import budget_differences, judge_budget


def test_true_uplift_beats_baseline_rate_under_budget():
    rng = np.random.default_rng(0)
    n = 30_000
    t = rng.integers(0, 3, n)
    base = rng.uniform(0.05, 0.6, n)
    effect = np.where(base < 0.2, 0.3, 0.0)
    y = (rng.uniform(size=n) < base + effect * (t > 0)).astype(float)
    uplift = np.column_stack([effect, effect / 2])
    response = np.column_stack([base, base])
    table = budget_differences(uplift, response, t, y, (0.2, 1.0), n_boot=50, seed=1)
    low = table.set_index("ratio").loc[0.2]
    full = table.set_index("ratio").loc[1.0]
    assert low["sends"] == 6000
    assert low["low"] > 0
    assert abs(low["estimate"] - (low["uplift_value"] - low["response_value"])) < 1e-12
    assert abs(full["estimate"]) < 0.02


def test_judge_marks_winner_by_floor_and_seed_range():
    rows = (
        [(0.1, s, d) for s, d in zip([1, 2, 3], [0.010, 0.011, 0.012], strict=True)]
        + [(0.2, s, d) for s, d in zip([1, 2, 3], [-0.006, -0.005, -0.004], strict=True)]
        + [(0.3, s, d) for s, d in zip([1, 2, 3], [0.010, -0.010, 0.012], strict=True)]
    )
    diffs = pd.DataFrame(rows, columns=["ratio", "seed", "estimate"])
    judged = judge_budget(diffs, 0.0038).set_index("ratio")
    assert judged.loc[0.1, "winner"] == "uplift"
    assert judged.loc[0.1, "threshold"] == 0.0038
    assert judged.loc[0.2, "winner"] == "response"
    assert judged.loc[0.3, "winner"] == "tie"
    assert np.isclose(judged.loc[0.3, "threshold"], 0.022)
