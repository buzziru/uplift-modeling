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


def test_build_tables_assigns_row_order_ids_and_treatments(raw):
    tables = build_tables(raw)
    assert tables["customers"]["customer_id"].tolist() == [0, 1, 2]
    assert tables["assignments"]["treatment_id"].tolist() == [0, 1, 2]
    assert len(tables["customers"]) == len(tables["assignments"]) == len(tables["outcomes"])
    assert "segment" not in tables["customers"].columns


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


def test_profile_counts_by_treatment(raw):
    tables = build_tables(raw)
    tables["splits"] = pd.DataFrame({"customer_id": [0, 1, 2], "split": ["train", "train", "test"]})
    p = profile(tables)
    assert p["splits"]["test/Womens E-Mail"] == {"n": 1, "visit": 1, "conversion": 1}
    assert p["rows"]["customers"] == 3
    assert p["by_treatment"]["Womens E-Mail"]["n"] == 1
    assert p["by_treatment"]["Womens E-Mail"]["spend_mean"] == 29.99
    assert p["by_treatment"]["Mens E-Mail"]["visit_rate"] == 1.0
    assert p["missing"]["recency"] == 0
    assert p["numeric_range"]["recency"] == {"min": 1, "max": 12}
    assert p["categories"]["zip_code"] == ["Rural", "Suburban", "Urban"]
    assert p["binary_rate"]["womens"] == round(2 / 3, 4)
    assert p["dtypes"]["customers"]["recency"] == "int64"
    assert p["boundary_counts"]["history_min"] == {"value": 30.0, "count": 1}
    assert p["boundary_counts"]["spend_positive_min"] == {"value": 29.99, "count": 1}


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
