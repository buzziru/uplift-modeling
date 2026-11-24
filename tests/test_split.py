import pandas as pd
import pytest

from uplift.split import SplitConfig, check_splits, funnel_strata, make_splits

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


def test_make_splits_keeps_strata_ratio_and_passes_checks(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    assert check_splits(splits, folds, ids) == []
    test = splits.loc[splits["split"] == "test", "customer_id"]
    assert len(test) == 180
    test_share = strata[ids.isin(test)].value_counts() / strata.value_counts()
    assert test_share.between(0.25, 0.35).all()


def test_make_splits_is_deterministic_and_folds_differ_by_seed(data):
    ids, strata = data
    s1, f1 = make_splits(ids, strata, CFG)
    s2, f2 = make_splits(ids, strata, CFG)
    pd.testing.assert_frame_equal(s1, s2)
    pd.testing.assert_frame_equal(f1, f2)
    a = f1[f1["seed"] == 42].set_index("customer_id")["fold"]
    b = f1[f1["seed"] == 154].set_index("customer_id")["fold"]
    assert (a != b.loc[a.index]).any()


def test_check_splits_reports_missing_fold_rows(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    errors = check_splits(splits, folds.iloc[1:], ids)
    assert errors == ["seed 42의 fold가 학습 고객을 한 번씩 덮지 않음"]
