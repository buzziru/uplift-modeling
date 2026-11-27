import numpy as np
import pandas as pd

from uplift import policy, value
from uplift.selection import seed_gap

RATIOS = tuple(i / 10 for i in range(1, 10))


def budget_differences(
    uplift: np.ndarray,
    response: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    ratios: tuple[float, ...],
    n_boot: int,
    seed: int,
) -> pd.DataFrame:
    n = len(treatment)
    rows = []
    for ratio in ratios:
        sends = round(ratio * n)
        ours = policy.top_k(uplift, sends)
        theirs = policy.top_k(response, sends)
        interval = value.value_interval(
            ours, treatment, outcome, "hajek", baseline=theirs, n_boot=n_boot, seed=seed
        )
        rows.append(
            {
                "send_ratio": ratio,
                "sends": sends,
                "uplift_value": value.policy_value(ours, treatment, outcome, "hajek"),
                "response_value": value.policy_value(theirs, treatment, outcome, "hajek"),
                **interval,
                "seed": seed,
            }
        )
    return pd.DataFrame(rows)


def judge_budget(differences: pd.DataFrame, floor: float) -> pd.DataFrame:
    table = pd.DataFrame(
        [
            {"send_ratio": ratio, **seed_gap(group.to_numpy(dtype=float), floor)}
            for ratio, group in differences.groupby("send_ratio")["estimate"]
        ]
    )
    table["winner"] = np.select(
        [table["mean_diff"] >= table["threshold"], -table["mean_diff"] >= table["threshold"]],
        ["uplift", "response"],
        "tie",
    )
    return table
