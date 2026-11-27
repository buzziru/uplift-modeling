import pandas as pd
import pytest

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


SAMPLE_IDS = [3, 1, 2, 9, 5]


def sampled(n: int) -> tuple[TrainData, TrainData]:
    frame = pd.DataFrame({"customer_id": SAMPLE_IDS, "visit": [1, 0, 1, 0, 1]})
    folds = pd.DataFrame(
        {
            "customer_id": SAMPLE_IDS * 2,
            "seed": [42] * 5 + [7] * 5,
            "fold": [i % 3 for i in range(10)],
        }
    )
    data = TrainData(frame, folds)
    return data, data.sample(n, seed=0)


@pytest.mark.parametrize("n", [0, 2, 5])
def test_sample_takes_n_rows(n):
    _, small = sampled(n)
    assert len(small.frame) == n


@pytest.mark.parametrize("n", [2, 4])
def test_sample_keeps_original_order(n):
    data, small = sampled(n)
    ids = data.frame["customer_id"].tolist()
    kept = small.frame["customer_id"].tolist()
    assert kept == [i for i in ids if i in set(kept)]


@pytest.mark.parametrize("n", [0, 2, 5])
def test_sample_keeps_folds_of_sampled_customers(n):
    _, small = sampled(n)
    assert set(small.folds["customer_id"]) == set(small.frame["customer_id"])


@pytest.mark.parametrize("part", ["frame", "folds"])
def test_parquet_round_trip(tmp_path, part):
    data = _data()
    to_parquet(data, tmp_path)
    pd.testing.assert_frame_equal(getattr(from_parquet(tmp_path), part), getattr(data, part))
