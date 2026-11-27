import duckdb
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.db import (
    ALLOWED,
    BINARY_COLUMNS,
    TREATMENTS,
    build_tables,
    category_fix_counts,
    check_tables,
    load_frame,
    profile,
    tables_markdown,
    write_db,
)


@pytest.fixture
def raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "recency": [1, 5, 12],
            "history_segment": ["1) $0 - $100", "2) $100 - $200", "1) $0 - $100"],
            "history": [50.0, 150.0, 30.0],
            "mens": [1, 0, 1],
            "womens": [0, 1, 1],
            "zip_code": ["Urban", "Rural", "Surburban"],
            "newbie": [1, 0, 0],
            "channel": ["Web", "Phone", "Multichannel"],
            "segment": ["No E-Mail", "Mens E-Mail", "Womens E-Mail"],
            "visit": [0, 1, 1],
            "conversion": [0, 0, 1],
            "spend": [0.0, 0.0, 29.99],
        }
    )


def test_build_tables_ids_follow_row_order(raw):
    assert build_tables(raw)["customers"]["customer_id"].tolist() == [0, 1, 2]


# Hillstrom segment 순서(No, Mens, Womens E-Mail)에 0, 1, 2를 붙이는 적재 규약
def test_build_tables_maps_treatment_id(raw):
    assert build_tables(raw)["assignments"]["treatment_id"].tolist() == [0, 1, 2]


def test_build_tables_drops_segment(raw):
    assert "segment" not in build_tables(raw)["customers"].columns


@st.composite
def raw_rows(draw) -> dict:
    visit = draw(st.sampled_from([0, 1]))
    conversion = draw(st.sampled_from([0, visit]))
    return {
        "recency": draw(st.integers(1, 12)),
        **{col: draw(st.sampled_from(sorted(values))) for col, values in ALLOWED.items()},
        "history": draw(st.floats(0, 1e4)),
        **{col: draw(st.sampled_from([0, 1])) for col in BINARY_COLUMNS},
        "segment": draw(st.sampled_from(TREATMENTS["name"].tolist())),
        "visit": visit,
        "conversion": conversion,
        "spend": draw(st.floats(0.01, 1e3)) if conversion else 0.0,
    }


@settings(deadline=None, max_examples=30)
@given(rows=st.lists(raw_rows(), min_size=1, max_size=20))
def test_build_tables_joins_back_to_raw_rows(rows):
    raw = pd.DataFrame(rows)
    tables = build_tables(raw)
    joined = (
        tables["customers"]
        .merge(tables["assignments"], on="customer_id")
        .merge(TREATMENTS.rename(columns={"name": "segment"}), on="treatment_id")
        .merge(tables["outcomes"], on="customer_id")
        .sort_values("customer_id")
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(pd.DataFrame(joined[raw.columns]), raw, check_dtype=False)


def test_build_tables_rejects_unknown_segment(raw):
    raw.loc[0, "segment"] = "SMS"
    with pytest.raises(ValueError, match="SMS"):
        build_tables(raw)


def test_write_db_round_trip(raw, tmp_path):
    path = tmp_path / "test.duckdb"
    write_db(build_tables(raw), path)
    with duckdb.connect(str(path)) as con:
        n = con.execute(
            "SELECT count(*) FROM assignments JOIN outcomes USING (customer_id)"
        ).fetchone()
    assert n == (3,)


# profile 테스트의 기대값은 raw fixture 세 행에서 손으로 센 개수, 평균, 최솟값이다.
# 비율 허용 오차는 적재 요약(artifacts/data/profile.json)이 적는 소수 넷째 자리다
@pytest.fixture
def prof(raw):
    tables = build_tables(raw)
    tables["splits"] = pd.DataFrame({"customer_id": [0, 1, 2], "split": ["train", "train", "test"]})
    return profile(tables)


def test_profile_counts_split_cell(prof):
    assert prof["splits"]["test/Womens E-Mail"] == {"n": 1, "visit": 1, "conversion": 1}


@pytest.mark.parametrize(
    ("treatment", "key", "value"),
    [
        ("Womens E-Mail", "n", 1),
        ("Womens E-Mail", "spend_mean", 29.99),
        ("Mens E-Mail", "visit_rate", 1.0),
    ],
)
def test_profile_summarises_treatment(prof, treatment, key, value):
    assert prof["by_treatment"][treatment][key] == value


def test_profile_counts_table_rows(prof):
    assert prof["rows"]["customers"] == 3


def test_profile_counts_missing_values(raw):
    tables = build_tables(raw)
    tables["customers"].loc[0, "history"] = float("nan")
    tables["splits"] = pd.DataFrame({"customer_id": [0, 1, 2], "split": ["train"] * 3})
    assert profile(tables)["missing"]["history"] == 1


@pytest.mark.parametrize(
    ("section", "column", "expected"),
    [
        ("numeric_range", "recency", {"min": 1, "max": 12}),
        ("categories", "zip_code", ["Rural", "Suburban", "Urban"]),
        ("binary_rate", "womens", pytest.approx(2 / 3, abs=1e-4)),
    ],
)
def test_profile_describes_column(prof, section, column, expected):
    assert prof[section][column] == expected


def test_profile_counts_boundary_values(prof):
    assert prof["boundary_counts"] == {
        "history_min": {"value": 30.0, "count": 1},
        "spend_positive_min": {"value": 29.99, "count": 1},
        "spend_max": {"value": 29.99, "count": 1},
    }


def test_tables_markdown_lists_every_table(raw):
    tables = build_tables(raw)
    md = tables_markdown(tables, head=2)
    assert [name for name in tables if f"## {name}" not in md] == []


def test_category_fix_counts_typo(raw):
    assert category_fix_counts(raw) == {"zip_code": {"Surburban": 1}}


def test_build_tables_fixes_zip_code_typo(raw):
    assert set(build_tables(raw)["customers"]["zip_code"]) == {"Urban", "Rural", "Suburban"}


@pytest.mark.parametrize(
    ("column", "value"),
    [
        *((column, "x") for column in ALLOWED),
        *((column, 2) for column in [*BINARY_COLUMNS, "visit", "conversion"]),
        ("recency", 0),
        ("recency", 13),
        ("spend", -1.0),
        ("history", -1.0),
    ],
)
def test_build_tables_rejects_out_of_range_values(raw, column, value):
    raw.loc[0, column] = value
    with pytest.raises(ValueError, match=rf"(?<![a-z_]){column}(?![a-z_])"):
        build_tables(raw)


def _visit_without_conversion_but_spend(tables):
    tables["outcomes"].loc[1, "spend"] = 5.0


def _conversion_without_visit(tables):
    tables["outcomes"].loc[0, ["visit", "conversion", "spend"]] = [0, 1, 10.0]


def _duplicate_customer(tables):
    for name in ["customers", "assignments", "outcomes"]:
        tables[name] = pd.concat([tables[name], tables[name].iloc[:1]], ignore_index=True)


def _unknown_treatment(tables):
    tables["assignments"].loc[0, "treatment_id"] = 3


def _missing_outcome(tables):
    tables["outcomes"] = tables["outcomes"].iloc[1:]


@pytest.mark.parametrize(
    "break_rule",
    [
        _visit_without_conversion_but_spend,
        _conversion_without_visit,
        _duplicate_customer,
        _unknown_treatment,
        _missing_outcome,
    ],
)
def test_check_tables_reports_single_violation(raw, break_rule):
    tables = build_tables(raw)
    break_rule(tables)
    assert len(check_tables(tables)) == 1


@pytest.mark.parametrize("name", ["assignments", "outcomes"])
def test_check_tables_names_table_with_key_mismatch(raw, name):
    tables = build_tables(raw)
    tables[name] = tables[name].iloc[1:]
    assert [name in e for e in check_tables(tables)] == [True]


def test_load_frame_joins_by_customer_id(raw, tmp_path):
    path = tmp_path / "test.duckdb"
    write_db(build_tables(raw), path)
    with duckdb.connect(str(path)) as con:
        df = load_frame(con)
    assert df["customer_id"].tolist() == [0, 1, 2]
    assert df.loc[2, ["channel", "treatment_id", "spend"]].tolist() == ["Multichannel", 2, 29.99]


@pytest.mark.parametrize(("split", "ids"), [("train", [0, 2]), (None, [0, 1, 2])])
def test_load_frame_filters_split(raw, tmp_path, split, ids):
    tables = build_tables(raw)
    tables["splits"] = pd.DataFrame({"customer_id": [0, 1, 2], "split": ["train", "test", "train"]})
    path = tmp_path / "split.duckdb"
    write_db(tables, path)
    with duckdb.connect(str(path)) as con:
        assert load_frame(con, split)["customer_id"].tolist() == ids
