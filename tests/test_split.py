import pandas as pd
import pytest

from uplift.split import SplitConfig, check_splits, funnel_strata, load_config, make_splits

CFG = SplitConfig(test_size=0.3, test_seed=42, cv_seeds=[42, 154], n_folds=5)


@pytest.fixture
def data():
    n = 600
    ids = pd.Series(range(n))
    treatment = ids % 3
    visit = (ids % 4 == 0).astype(int)
    conversion = ((ids % 20 == 0) & (visit == 1)).astype(int)
    df = pd.DataFrame({"treatment_id": treatment, "visit": visit, "conversion": conversion})
    return ids, funnel_strata(df)


def test_funnel_strata_separates_stage_within_treatment():
    df = pd.DataFrame(
        {"treatment_id": [0, 0, 0, 2], "visit": [0, 1, 1, 1], "conversion": [0, 0, 1, 1]}
    )
    s = funnel_strata(df)
    assert s.tolist() == [0, 1, 2, 8]


def _test_ids(data):
    ids, strata = data
    splits, _ = make_splits(ids, strata, CFG)
    return splits.loc[splits["split"] == "test", "customer_id"]


def test_make_splits_passes_check_splits(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    assert check_splits(splits, folds, ids) == []


def test_make_splits_test_size(data):
    assert len(_test_ids(data)) == 180


def test_make_splits_keeps_strata_ratio(data):
    ids, strata = data
    test_share = strata[ids.isin(_test_ids(data))].value_counts() / strata.value_counts()
    assert test_share.between(0.25, 0.35).all()


def test_make_splits_is_deterministic(data):
    ids, strata = data
    first = make_splits(ids, strata, CFG)
    second = make_splits(ids, strata, CFG)
    pd.testing.assert_frame_equal(pd.concat(first), pd.concat(second))


def test_make_splits_folds_differ_by_seed(data):
    ids, strata = data
    _, f1 = make_splits(ids, strata, CFG)
    a = f1[f1["seed"] == 42].set_index("customer_id")["fold"]
    b = f1[f1["seed"] == 154].set_index("customer_id")["fold"]
    assert (a != b.loc[a.index]).any()


def test_check_splits_reports_missing_fold_rows(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    errors = check_splits(splits, folds.iloc[1:], ids)
    assert errors == ["seed 42의 fold가 학습 고객을 한 번씩 덮지 않음"]


def test_check_splits_reports_duplicate_split_rows(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    doubled = pd.concat([splits, splits.iloc[:1]])
    assert check_splits(doubled, folds, ids) == ["splits가 고객마다 한 행이 아님"]


def test_load_config_reads_yaml(tmp_path):
    path = tmp_path / "splits.yaml"
    path.write_text(
        "test_size: 0.3\ntest_seed: 42\ncv_seeds: [42, 154]\nn_folds: 5\n", encoding="utf-8"
    )
    assert load_config(path) == CFG


def test_load_config_rejects_missing_field(tmp_path):
    path = tmp_path / "splits.yaml"
    path.write_text("test_size: 0.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="test_seed"):
        load_config(path)
