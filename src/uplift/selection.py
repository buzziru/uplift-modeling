from typing import TypedDict

import numpy as np
import pandas as pd

from uplift.learners import Method


class Gap(TypedDict):
    mean_diff: float
    seed_range: float
    threshold: float


def seed_gap(diff: np.ndarray, floor: float) -> Gap:
    seed_range = float(diff.max() - diff.min())
    return {
        "mean_diff": float(diff.mean()),
        "seed_range": seed_range,
        "threshold": max(seed_range, floor),
    }


def choose_method(
    scores: pd.DataFrame, order: list[Method], floor: float
) -> tuple[pd.DataFrame, Method]:
    wide = scores.pivot(index="seed", columns="method", values="value")
    unknown = set(wide.columns) - set(order)
    if unknown:
        raise ValueError(f"order에 없는 학습기: {sorted(unknown)}")
    values = wide.to_numpy(dtype=float)
    means = values.mean(axis=0)
    lead = int(np.argmax(means))
    rows = []
    for j, method in enumerate(wide.columns):
        gap = seed_gap(values[:, lead] - values[:, j], floor)
        rows.append(
            {
                "method": str(method),
                "mean": float(means[j]),
                **gap,
                "distinguishable": gap["mean_diff"] >= gap["threshold"],
            }
        )
    table = pd.DataFrame(rows).sort_values("mean", ascending=False, kind="stable")
    table = table.reset_index(drop=True)
    undecided = set(table.loc[~table["distinguishable"], "method"])
    return table, next(m for m in order if m in undecided)
