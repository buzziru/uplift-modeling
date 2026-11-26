import pandas as pd

from uplift.train_data import TrainData, from_parquet, to_parquet


def _data():
    frame = pd.DataFrame({"customer_id": [3, 1, 2], "visit": [1, 0, 1]})
    folds = pd.DataFrame(
        {"customer_id": [1, 2, 3, 1, 2, 3], "seed": [42] * 3 + [7] * 3, "fold": [0, 1, 2, 2, 1, 0]}
    )
    return TrainData(frame, folds)


def test_fold_array_follows_frame_order():
    data = _data()
    assert data.fold_array(42).tolist() == [2, 0, 1]
    assert data.fold_array(7).tolist() == [0, 2, 1]


def test_sample_keeps_matching_folds_and_parquet_round_trip(tmp_path):
    small = _data().sample(2)
    assert set(small.folds["customer_id"]) == set(small.frame["customer_id"])
    to_parquet(small, tmp_path)
    back = from_parquet(tmp_path)
    pd.testing.assert_frame_equal(back.frame, small.frame)
