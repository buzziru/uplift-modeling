"""원본 Hillstrom 데이터를 분석 테이블로 나누고 DuckDB에 적재한다.

테이블 구성은 docs/DATA.md "분석 데이터는 데이터 구조와 분석 목적에 따라 테이블로 나눈다" 절을 따른다.
"""

from pathlib import Path

import duckdb
import pandas as pd

TREATMENTS = pd.DataFrame(
    {
        "treatment_id": [0, 1, 2],
        "name": ["No E-Mail", "Mens E-Mail", "Womens E-Mail"],
    }
)
CUSTOMER_COLUMNS = [
    "recency",
    "history_segment",
    "history",
    "mens",
    "womens",
    "zip_code",
    "newbie",
    "channel",
]
OUTCOME_COLUMNS = ["visit", "conversion", "spend"]


def build_tables(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """원본 한 테이블을 고객, 처치, 배정, 결과 테이블로 나눈다.

    원본에는 고객 ID가 없으므로 원본 CSV의 행 순서를 customer_id로 쓴다.
    """
    df = raw.reset_index(drop=True)
    customer_id = pd.Series(range(len(df)), name="customer_id")
    ids = dict(zip(TREATMENTS["name"], TREATMENTS["treatment_id"]))
    unknown = sorted(set(df["segment"]) - ids.keys())
    if unknown:
        raise ValueError(f"알 수 없는 segment: {unknown}")
    treatment_id = [ids[s] for s in df["segment"]]

    return {
        "customers": pd.concat([customer_id, df[CUSTOMER_COLUMNS]], axis=1),
        "treatments": TREATMENTS.copy(),
        "assignments": pd.DataFrame({"customer_id": customer_id, "treatment_id": treatment_id}),
        "outcomes": pd.concat([customer_id, df[OUTCOME_COLUMNS]], axis=1),
    }


def write_db(tables: dict[str, pd.DataFrame], path: Path) -> None:
    """테이블을 DuckDB 파일에 쓴다. 같은 이름의 테이블은 바꾼다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        for name, table in tables.items():
            con.register("_src", table)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _src")
            con.unregister("_src")


def profile(tables: dict[str, pd.DataFrame]) -> dict:
    """데이터 명세에 인용할 요약을 만든다."""
    customers = {c: tables["customers"][c].to_numpy() for c in CUSTOMER_COLUMNS}
    joined = (
        tables["assignments"]
        .merge(tables["outcomes"], on="customer_id")
        .merge(tables["treatments"], on="treatment_id")
    )
    by_treatment = (
        joined.groupby("name")
        .agg(
            n=("customer_id", "size"),
            visit_rate=("visit", "mean"),
            conversion_rate=("conversion", "mean"),
            spend_mean=("spend", "mean"),
        )
        .round(4)
    )
    numeric = ["recency", "history"]
    categorical = ["history_segment", "zip_code", "channel"]
    binary = ["mens", "womens", "newbie"]
    return {
        "rows": {name: len(t) for name, t in tables.items()},
        "dtypes": {name: {c: str(t[c].dtype) for c in t.columns} for name, t in tables.items()},
        "missing": {c: int(pd.isna(customers[c]).sum()) for c in CUSTOMER_COLUMNS},
        "numeric_range": {
            c: {"min": customers[c].min().item(), "max": customers[c].max().item()} for c in numeric
        },
        "categories": {c: sorted(set(customers[c].tolist())) for c in categorical},
        "binary_rate": {c: round(float(customers[c].mean()), 4) for c in binary},
        "by_treatment": by_treatment.to_dict(orient="index"),
    }


def tables_markdown(tables: dict[str, pd.DataFrame], head: int = 5) -> str:
    """테이블마다 열과 타입, 행 수, 앞 몇 행을 마크다운으로 만든다. DuckDB 파일을 열지 않고 보기 위한 것이다."""
    parts = [
        "# DuckDB 테이블 미리보기",
        "",
        "`scripts/build_db.py`가 적재할 때 만든다. 손으로 고치지 않는다.",
        "",
    ]
    for name, t in tables.items():
        cols = " | ".join(f"{c} ({t[c].dtype})" for c in t.columns)
        rows = [" | ".join(str(v) for v in row) for row in t.head(head).itertuples(index=False)]
        sep = " | ".join("---" for _ in t.columns)
        parts += [f"## {name} ({len(t):,}행)", "", f"| {cols} |", f"| {sep} |"]
        parts += [f"| {r} |" for r in rows]
        parts.append("")
    return "\n".join(parts)
