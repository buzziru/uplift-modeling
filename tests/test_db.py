import duckdb
import pandas as pd
import pytest

from uplift.db import (
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


def test_build_tables_maps_treatment_id(raw):
    assert build_tables(raw)["assignments"]["treatment_id"].tolist() == [0, 1, 2]


def test_build_tables_drops_segment(raw):
    assert "segment" not in build_tables(raw)["customers"].columns


def test_build_tables_keeps_rows_aligned_by_customer_id(raw):
    tables = build_tables(raw)
    customer = tables["customers"].set_index("customer_id").loc[2]
    outcome = tables["outcomes"].set_index("customer_id").loc[2]
    assert customer["channel"] == "Multichannel"
    assert customer["history"] == 30.0
    assert outcome["spend"] == 29.99


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


def test_profile_counts_missing_values(prof):
    assert prof["missing"]["recency"] == 0


def test_profile_describes_columns(prof):
    described = {
        "range": prof["numeric_range"]["recency"],
        "zip": prof["categories"]["zip_code"],
        "womens": prof["binary_rate"]["womens"],
        "dtype": prof["dtypes"]["customers"]["recency"],
    }
    assert described == {
        "range": {"min": 1, "max": 12},
        "zip": ["Rural", "Suburban", "Urban"],
        "womens": round(2 / 3, 4),
        "dtype": "int64",
    }


def test_profile_counts_boundary_values(prof):
    assert prof["boundary_counts"] == {
        "history_min": {"value": 30.0, "count": 1},
        "spend_positive_min": {"value": 29.99, "count": 1},
        "spend_max": {"value": 29.99, "count": 1},
    }


def test_tables_markdown_lists_every_table(raw):
    md = tables_markdown(build_tables(raw), head=2)
    for name in ["customers", "treatments", "assignments", "outcomes"]:
        assert f"## {name}" in md


def test_build_tables_fixes_zip_code_typo(raw):
    assert category_fix_counts(raw) == {"zip_code": {"Surburban": 1}}
    assert set(build_tables(raw)["customers"]["zip_code"]) == {"Urban", "Rural", "Suburban"}


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("channel", "Mail", "channel에 허용되지 않은 값 ['Mail']"),
        ("recency", 13, "recency가 1~12 밖"),
        ("visit", 2, "visit이 0/1 밖"),
        ("spend", -1.0, "spend에 음수"),
        ("history", -1.0, "history에 음수"),
        ("mens", 2, "mens이 0/1 밖"),
    ],
)
def test_build_tables_rejects_out_of_range_values(raw, column, value, message):
    raw.loc[0, column] = value
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        build_tables(raw)


def test_check_tables_reports_funnel_violations(raw):
    tables = build_tables(raw)
    tables["outcomes"].loc[0, ["visit", "conversion", "spend"]] = [0, 1, 10.0]
    tables["outcomes"].loc[1, "spend"] = 5.0
    errors = check_tables(tables)
    assert "구매했는데 방문하지 않은 행" in errors
    assert "spend > 0과 conversion = 1이 어긋남" in errors


def test_check_tables_reports_key_mismatch(raw):
    tables = build_tables(raw)
    tables["outcomes"] = tables["outcomes"].iloc[1:]
    assert check_tables(tables) == ["outcomes의 customer_id 집합이 customers와 다름"]


def test_load_frame_joins_by_customer_id(raw, tmp_path):
    path = tmp_path / "test.duckdb"
    write_db(build_tables(raw), path)
    with duckdb.connect(str(path)) as con:
        df = load_frame(con)
    assert df["customer_id"].tolist() == [0, 1, 2]
    assert df.loc[2, ["channel", "treatment_id", "spend"]].tolist() == ["Multichannel", 2, 29.99]


def test_load_frame_filters_split(raw, tmp_path):
    tables = build_tables(raw)
    tables["splits"] = pd.DataFrame({"customer_id": [0, 1, 2], "split": ["train", "test", "train"]})
    path = tmp_path / "split.duckdb"
    write_db(tables, path)
    with duckdb.connect(str(path)) as con:
        assert load_frame(con, "train")["customer_id"].tolist() == [0, 2]
        assert len(load_frame(con)) == 3
