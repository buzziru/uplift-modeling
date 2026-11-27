import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.train_data import TrainData, from_parquet, to_parquet


def _data():
    frame = pd.DataFrame({"customer_id": [3, 1, 2], "visit": [1, 0, 1]})
    folds = pd.DataFrame(
        {"customer_id": [1, 2, 3, 1, 2, 3], "seed": [42] * 3 + [7] * 3, "fold": [0, 1, 2, 2, 1, 0]}
    )
    return TrainData(frame, folds)


# frame 고객 순서(3, 1, 2)로 _data()의 folds 표를 손으로 읽은 값
@pytest.mark.parametrize(("seed", "folds"), [(42, [2, 0, 1]), (7, [0, 2, 1])])
def test_fold_array_follows_frame_order(seed, folds):
    assert _data().fold_array(seed).tolist() == folds


@st.composite
def sampled(draw) -> tuple[TrainData, TrainData, int]:
    ids = draw(st.lists(st.integers(0, 10**6), min_size=1, max_size=30, unique=True))
    frame = pd.DataFrame({"customer_id": ids, "visit": [i % 2 for i in range(len(ids))]})
    folds = pd.DataFrame(
        {
            "customer_id": ids * 2,
            "seed": [42] * len(ids) + [7] * len(ids),
            "fold": [i % 3 for i in range(2 * len(ids))],
        }
    )
    n = draw(st.integers(0, len(ids)))
    data = TrainData(frame, folds)
    return data, data.sample(n, seed=draw(st.integers(0, 2**32 - 1))), n


@settings(deadline=None, max_examples=50)
@given(case=sampled())
def test_sample_takes_n_rows_in_original_order(case):
    data, small, n = case
    ids = data.frame["customer_id"].tolist()
    kept = small.frame["customer_id"].tolist()
    assert len(kept) == n
    assert kept == [i for i in ids if i in set(kept)]


@settings(deadline=None, max_examples=50)
@given(case=sampled())
def test_sample_keeps_folds_of_sampled_customers(case):
    _, small, _ = case
    assert set(small.folds["customer_id"]) == set(small.frame["customer_id"])


@pytest.mark.parametrize("part", ["frame", "folds"])
def test_parquet_round_trip(tmp_path, part):
    data = _data()
    to_parquet(data, tmp_path)
    pd.testing.assert_frame_equal(getattr(from_parquet(tmp_path), part), getattr(data, part))
