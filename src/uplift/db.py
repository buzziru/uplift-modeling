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
CATEGORY_FIXES = {"zip_code": {"Surburban": "Suburban"}}
ALLOWED = {
    "history_segment": {
        "1) $0 - $100",
        "2) $100 - $200",
        "3) $200 - $350",
        "4) $350 - $500",
        "5) $500 - $750",
        "6) $750 - $1,000",
        "7) $1,000 +",
    },
    "zip_code": {"Rural", "Suburban", "Urban"},
    "channel": {"Multichannel", "Phone", "Web"},
}
BINARY_COLUMNS = ["mens", "womens", "newbie"]


def build_tables(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = raw.reset_index(drop=True).replace(CATEGORY_FIXES)
    customer_id = pd.Series(range(len(df)), name="customer_id")
    ids = dict(zip(TREATMENTS["name"], TREATMENTS["treatment_id"], strict=True))
    unknown = sorted(set(df["segment"]) - ids.keys())
    if unknown:
        raise ValueError(f"알 수 없는 segment: {unknown}")
    treatment_id = [ids[s] for s in df["segment"]]

    tables = {
        "customers": pd.concat([customer_id, df[CUSTOMER_COLUMNS]], axis=1),
        "treatments": TREATMENTS.copy(),
        "assignments": pd.DataFrame({"customer_id": customer_id, "treatment_id": treatment_id}),
        "outcomes": pd.concat([customer_id, df[OUTCOME_COLUMNS]], axis=1),
    }
    errors = check_tables(tables)
    if errors:
        raise ValueError("품질 규칙 위반: " + "; ".join(errors))
    return tables


def category_fix_counts(raw: pd.DataFrame) -> dict:
    return {
        col: {old: int(pd.Series(raw[col] == old).sum()) for old in fixes}
        for col, fixes in CATEGORY_FIXES.items()
    }


def check_tables(tables: dict[str, pd.DataFrame]) -> list[str]:
    customers, outcomes = tables["customers"], tables["outcomes"]
    ids = customers["customer_id"]
    flags = {
        "visit": outcomes["visit"],
        "conversion": outcomes["conversion"],
        **{col: customers[col] for col in BINARY_COLUMNS},
    }
    unknown = {col: sorted(set(customers[col]) - allowed) for col, allowed in ALLOWED.items()}
    rules = [
        (not bool(ids.is_unique), "customer_id 중복"),
        *(
            (
                set(tables[name]["customer_id"]) != set(ids),
                f"{name}의 customer_id 집합이 customers와 다름",
            )
            for name in ["assignments", "outcomes"]
        ),
        (
            not bool(tables["assignments"]["treatment_id"].isin(TREATMENTS["treatment_id"]).all()),
            "treatment_id가 0, 1, 2 밖",
        ),
        *((bool(values), f"{col}에 허용되지 않은 값 {values}") for col, values in unknown.items()),
        *((not bool(s.isin([0, 1]).all()), f"{col}이 0/1 밖") for col, s in flags.items()),
        (not bool(customers["recency"].between(1, 12).all()), "recency가 1~12 밖"),
        *(
            (bool((s < 0).any()), f"{col}에 음수")
            for col, s in [("history", customers["history"]), ("spend", outcomes["spend"])]
        ),
        (
            bool(((outcomes["conversion"] == 1) & (outcomes["visit"] == 0)).any()),
            "구매했는데 방문하지 않은 행",
        ),
        (
            bool(((outcomes["spend"] > 0) != (outcomes["conversion"] == 1)).any()),
            "spend > 0과 conversion = 1이 어긋남",
        ),
    ]
    return [message for failed, message in rules if failed]


def load_frame(con: duckdb.DuckDBPyConnection, split: str | None = None) -> pd.DataFrame:
    filter_split = (
        ""
        if split is None
        else "INNER JOIN splits AS s ON c.customer_id = s.customer_id AND s.split = $split"
    )
    return con.execute(
        f"""
        SELECT c.*, a.treatment_id, o.visit, o.conversion, o.spend
        FROM customers AS c
        INNER JOIN assignments AS a ON c.customer_id = a.customer_id
        INNER JOIN outcomes AS o ON c.customer_id = o.customer_id
        {filter_split}
        ORDER BY c.customer_id
        """,
        {} if split is None else {"split": split},
    ).df()


def write_db(tables: dict[str, pd.DataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        for name, table in tables.items():
            con.register("_src", table)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _src")
            con.unregister("_src")


def profile(tables: dict[str, pd.DataFrame]) -> dict:
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
    split_summary = (
        tables["splits"]
        .merge(joined, on="customer_id")
        .groupby(["split", "name"])
        .agg(n=("customer_id", "size"), visit=("visit", "sum"), conversion=("conversion", "sum"))
    )
    return {
        "rows": {name: len(t) for name, t in tables.items()},
        "splits": {
            f"{split}/{name}": row for (split, name), row in split_summary.to_dict("index").items()
        },
        "dtypes": {name: {c: str(t[c].dtype) for c in t.columns} for name, t in tables.items()},
        "missing": {c: int(pd.isna(customers[c]).sum()) for c in CUSTOMER_COLUMNS},
        "numeric_range": {
            c: {"min": customers[c].min().item(), "max": customers[c].max().item()} for c in numeric
        },
        "categories": {c: sorted(set(customers[c].tolist())) for c in categorical},
        "binary_rate": {c: round(float(customers[c].mean()), 4) for c in binary},
        "boundary_counts": {
            "history_min": _boundary(pd.Series(tables["customers"]["history"]), "min"),
            "spend_positive_min": _boundary(joined.loc[joined["spend"] > 0, "spend"], "min"),
            "spend_max": _boundary(pd.Series(joined["spend"]), "max"),
        },
        "by_treatment": by_treatment.to_dict(orient="index"),
    }


def _boundary(values: pd.Series, side: str) -> dict:
    v = values.min() if side == "min" else values.max()
    return {"value": float(v), "count": int((values == v).sum())}


def tables_markdown(tables: dict[str, pd.DataFrame], head: int = 5) -> str:
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
