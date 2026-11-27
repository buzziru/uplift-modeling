import numpy as np
import pandas as pd


def choose_method(scores: pd.DataFrame, order: list[str], floor: float) -> tuple[pd.DataFrame, str]:
    wide = scores.pivot(index="seed", columns="method", values="value")
    methods = [str(m) for m in wide.columns]
    values = wide.to_numpy(dtype=float)
    means = values.mean(axis=0)
    lead = int(np.argmax(means))
    rows = []
    for j, method in enumerate(methods):
        diff = values[:, lead] - values[:, j]
        seed_range = float(diff.max() - diff.min())
        threshold = max(seed_range, floor)
        rows.append(
            {
                "method": method,
                "mean": float(means[j]),
                "mean_diff": float(diff.mean()),
                "seed_range": seed_range,
                "threshold": threshold,
                "distinguishable": bool(diff.mean() >= threshold),
            }
        )
    table = pd.DataFrame(rows).sort_values("mean", ascending=False, kind="stable").reset_index(drop=True)
    tied = [m for m, d in zip(table["method"], table["distinguishable"], strict=True) if not d]
    return table, min(tied, key=order.index)
