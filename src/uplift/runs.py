import json
import subprocess
import uuid
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import duckdb
import pandas as pd
from pydantic import BaseModel

RUNS_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    created_at TIMESTAMP,
    config JSON,
    git_commit VARCHAR
)
"""
METRICS_DDL = """
CREATE TABLE IF NOT EXISTS metrics (
    run_id VARCHAR,
    model_id VARCHAR,
    metric VARCHAR,
    fold INTEGER,
    value DOUBLE
)
"""
PREDICTIONS_DDL = """
CREATE TABLE IF NOT EXISTS predictions (
    run_id VARCHAR,
    model_id VARCHAR,
    customer_id BIGINT,
    treatment_id INTEGER,
    fold INTEGER,
    score DOUBLE
)
"""


RUN_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS run_tables (
    run_id VARCHAR,
    name VARCHAR,
    data JSON
)
"""


def require_clean(paths: list[str]) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths], capture_output=True, text=True, check=True
    ).stdout
    if status.strip():
        raise RuntimeError(f"커밋하지 않은 변경이 있어 실행을 기록할 수 없다:\n{status}")


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def record_run(con: duckdb.DuckDBPyConnection, experiment_id: str, config: dict) -> str:
    con.execute(RUNS_DDL)
    run_id = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
        [run_id, experiment_id, datetime.now(UTC), json.dumps(config), git_commit()],
    )
    return run_id


def _insert(con: duckdb.DuckDBPyConnection, table: str, ddl: str, rows: pd.DataFrame) -> None:
    con.execute(ddl)
    con.register("new_rows", rows)
    con.execute(f"INSERT INTO {table} SELECT * FROM new_rows")
    con.unregister("new_rows")


def _columns(rows: pd.DataFrame, columns: list) -> pd.DataFrame:
    missing = [c for c in columns if c not in rows.columns]
    if missing:
        raise KeyError(f"열이 없다: {missing}")
    return rows.reindex(columns=columns)


def record_metrics(con: duckdb.DuckDBPyConnection, run_id: str, metrics: pd.DataFrame) -> None:
    rows = _columns(
        metrics.assign(run_id=run_id), ["run_id", "model_id", "metric", "fold", "value"]
    )
    _insert(con, "metrics", METRICS_DDL, rows)


def record_predictions(
    con: duckdb.DuckDBPyConnection, run_id: str, predictions: pd.DataFrame
) -> None:
    columns = ["run_id", "model_id", "customer_id", "treatment_id", "fold", "score"]
    _insert(
        con,
        "predictions",
        PREDICTIONS_DDL,
        _columns(predictions.assign(run_id=run_id), columns),
    )


def record_table(
    con: duckdb.DuckDBPyConnection, run_id: str, name: str, table: pd.DataFrame
) -> None:
    con.execute(RUN_TABLES_DDL)
    data = table.to_json(orient="records", double_precision=15)
    con.execute("INSERT INTO run_tables VALUES (?, ?, ?)", [run_id, name, data])


def load_table(con: duckdb.DuckDBPyConnection, run_id: str, name: str) -> pd.DataFrame:
    row = con.execute(
        "SELECT data FROM run_tables WHERE run_id = ? AND name = ?", [run_id, name]
    ).fetchone()
    if row is None:
        raise KeyError(f"{run_id}에 {name} 표가 없다")
    return pd.read_json(StringIO(row[0]), orient="records")


def load_scores(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    model_id: str,
    arms: tuple[int, ...],
    customers: pd.Index | None = None,
) -> pd.DataFrame:
    rows = con.execute(
        "SELECT customer_id, treatment_id, score FROM predictions WHERE run_id = ? AND model_id = ?",
        [run_id, model_id],
    ).df()
    if rows.empty:
        raise KeyError(f"{run_id}에 {model_id} 예측이 없다")
    wide = _columns(
        rows.pivot(index="customer_id", columns="treatment_id", values="score"), list(arms)
    )
    if customers is None:
        return wide
    missing = customers.difference(wide.index)
    if len(missing):
        raise KeyError(f"{run_id} {model_id}에 고객 {len(missing)}명의 예측이 없다")
    return wide.loc[customers]


def common_config[M: BaseModel](
    con: duckdb.DuckDBPyConnection, run_ids: list[str], model: type[M], part_key: str = "part"
) -> tuple[M, dict[str, str]]:
    raw = {r: load_run_config(con, r) for r in run_ids}
    configs = {r: model(**c) for r, c in raw.items()}
    dumps = {json.dumps(c.model_dump(), sort_keys=True) for c in configs.values()}
    if len(dumps) > 1:
        raise ValueError(f"실행들의 설정이 서로 다르다: {run_ids}")
    parts = [raw[r][part_key] for r in run_ids]
    if len(set(parts)) < len(parts):
        raise ValueError(f"같은 {part_key}의 실행이 여럿이다: {parts}")
    return configs[run_ids[0]], dict(zip(parts, run_ids, strict=True))


def load_run_config(con: duckdb.DuckDBPyConnection, run_id: str) -> dict:
    row = con.execute("SELECT config FROM runs WHERE run_id = ?", [run_id]).fetchone()
    if row is None:
        raise KeyError(f"{run_id} 실행이 없다")
    return json.loads(row[0])


RECORD_TABLES = {
    "runs": RUNS_DDL,
    "metrics": METRICS_DDL,
    "predictions": PREDICTIONS_DDL,
    "run_tables": RUN_TABLES_DDL,
}


def merge_records(con: duckdb.DuckDBPyConnection, source: Path) -> list[str]:
    con.execute(f"ATTACH '{source.as_posix()}' AS src (READ_ONLY)")
    try:
        run_ids = [r[0] for r in con.execute("SELECT run_id FROM src.runs").fetchall()]
        known = {r[0] for r in con.execute(RUNS_DDL + "; SELECT run_id FROM runs").fetchall()}
        if known & set(run_ids):
            raise RuntimeError(f"이미 합친 실행이다: {sorted(known & set(run_ids))}")
        present = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src'"
            ).fetchall()
        }
        for table, ddl in RECORD_TABLES.items():
            con.execute(ddl)
            if table in present:
                con.execute(f"INSERT INTO {table} SELECT * FROM src.{table}")
    finally:
        con.execute("DETACH src")
    return run_ids
