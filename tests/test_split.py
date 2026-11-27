from pathlib import Path

import numpy as np
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


ALL_CELLS = [(t, v, c) for t in (2, 0, 1) for v, c in [(1, 1), (0, 0), (1, 0)]]


@pytest.mark.parametrize(
    "rows",
    [ALL_CELLS * 2, ALL_CELLS[:1], ALL_CELLS[::2]],
    ids=["all_cells_twice", "one_row", "some_cells"],
)
def test_funnel_strata_separates_every_treatment_and_stage(rows):
    df = pd.DataFrame(rows, columns=["treatment_id", "visit", "conversion"])
    cells = list(zip(df["treatment_id"], df["visit"], df["conversion"], strict=True))
    pairs = set(zip(cells, funnel_strata(df), strict=True))
    assert len(pairs) == len(set(cells)) == len({s for _, s in pairs})


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
    assert ["42" in e for e in errors] == [True]


def test_check_splits_reports_customer_twice_in_a_seed(data):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    seed_154 = folds[folds["seed"] == 154]
    errors = check_splits(splits, pd.concat([folds, seed_154.iloc[:1]]), ids)
    assert ["154" in e for e in errors] == [True]


def _test_row(splits):
    return int(np.flatnonzero(splits["split"].to_numpy() == "test")[0])


@pytest.mark.parametrize("change", ["duplicate", "missing"])
def test_check_splits_reports_split_rows_not_one_per_customer(data, change):
    ids, strata = data
    splits, folds = make_splits(ids, strata, CFG)
    row = _test_row(splits)
    broken = (
        pd.concat([splits, splits.iloc[[row]]])
        if change == "duplicate"
        else splits.drop(splits.index[row])
    )
    assert len(check_splits(broken, folds, ids)) == 1


def test_split_config_file_loads_with_its_model():
    load_config(Path(__file__).resolve().parents[1] / "scripts" / "splits.yaml")
