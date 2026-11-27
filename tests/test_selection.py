import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.learners import Method
from uplift.selection import choose_method, seed_gap

ORDER: list[Method] = ["s_learner", "t_learner", "x_learner"]


def _scores(values):
    return pd.DataFrame(
        [
            {"method": m, "seed": s, "value": v}
            for m, vs in values.items()
            for s, v in zip([42, 154, 1592], vs, strict=True)
        ]
    )


@pytest.mark.parametrize(
    ("diff", "expected"),
    [
        ([0.010, 0.011, 0.012], {"mean_diff": 0.011, "seed_range": 0.002, "threshold": 0.0038}),
        ([0.010, -0.010, 0.012], {"mean_diff": 0.004, "seed_range": 0.022, "threshold": 0.022}),
    ],
    ids=["floor", "seed_range"],
)
def test_seed_gap_takes_larger_of_range_and_floor(diff, expected):
    assert seed_gap(np.array(diff), 0.0038) == pytest.approx(expected)


VALUES = st.floats(min_value=-1, max_value=1)
DIFFS = arrays(np.float64, st.integers(min_value=1, max_value=10), elements=VALUES)


@settings(max_examples=50, deadline=None)
@given(DIFFS, st.floats(min_value=0, max_value=1))
def test_seed_gap_threshold_covers_floor_and_range(diff, floor):
    gap = seed_gap(diff, floor)
    assert gap["threshold"] >= max(floor, gap["seed_range"])


@settings(max_examples=50, deadline=None)
@given(DIFFS)
def test_seed_gap_mean_lies_within_range(diff):
    mean = seed_gap(diff, 0.0)["mean_diff"]
    assert diff.min() - 1e-12 <= mean <= diff.max() + 1e-12


def test_picks_simplest_method_within_threshold_of_leader():
    _, chosen = choose_method(
        _scores(
            {
                "s_learner": [0.180, 0.181, 0.179],
                "t_learner": [0.181, 0.183, 0.182],
                "x_learner": [0.15, 0.15, 0.15],
            }
        ),
        ORDER,
        0.0038,
    )
    assert chosen == "s_learner"


def test_marks_clearly_worse_method_distinguishable():
    table, _ = choose_method(
        _scores({"s_learner": [0.180, 0.181, 0.179], "x_learner": [0.15, 0.15, 0.15]}),
        ORDER,
        0.0038,
    )
    assert table.loc[table["method"] == "x_learner", "distinguishable"].item()


def test_floor_applies_when_pair_range_is_small():
    table, chosen = choose_method(
        _scores({"s_learner": [0.170, 0.170, 0.170], "t_learner": [0.175, 0.175, 0.175]}),
        ORDER,
        0.0038,
    )
    row = table.set_index("method").loc["s_learner"]
    assert (row["seed_range"], row["threshold"], chosen) == (0, 0.0038, "t_learner")


def test_pair_range_widens_threshold_beyond_floor():
    _, chosen = choose_method(
        _scores({"s_learner": [0.170, 0.180, 0.172], "t_learner": [0.180, 0.181, 0.180]}),
        ORDER,
        0.0038,
    )
    assert chosen == "s_learner"


def test_rejects_method_missing_from_order():
    with pytest.raises(ValueError, match="dr_learner"):
        choose_method(_scores({"dr_learner": [0.1, 0.1, 0.1]}), ORDER, 0.0038)


def test_table_sorts_methods_by_mean_descending():
    table, _ = choose_method(
        _scores(
            {
                "s_learner": [0.15, 0.15, 0.15],
                "t_learner": [0.18, 0.18, 0.18],
                "x_learner": [0.16, 0.16, 0.16],
            }
        ),
        ORDER,
        0.0038,
    )
    assert table["method"].tolist() == ["t_learner", "x_learner", "s_learner"]


@settings(max_examples=30, deadline=None)
@given(
    arrays(np.float64, (3, 3), elements=st.floats(min_value=0, max_value=1)),
    st.floats(min_value=1e-4, max_value=0.1),
)
def test_leader_is_never_distinguishable_from_itself(values, floor):
    table, _ = choose_method(_scores(dict(zip(ORDER, values.T, strict=True))), ORDER, floor)
    assert not table.iloc[0]["distinguishable"]
