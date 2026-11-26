import json
import subprocess
import uuid
from datetime import UTC, datetime
from io import StringIO

import duckdb
import pandas as pd

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


def record_metrics(con: duckdb.DuckDBPyConnection, run_id: str, metrics: pd.DataFrame) -> None:
    rows = metrics.assign(run_id=run_id).reindex(
        columns=["run_id", "model_id", "metric", "fold", "value"]
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
        predictions.assign(run_id=run_id).reindex(columns=columns),
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


def load_run_config(con: duckdb.DuckDBPyConnection, run_id: str) -> dict:
    row = con.execute("SELECT config FROM runs WHERE run_id = ?", [run_id]).fetchone()
    if row is None:
        raise KeyError(f"{run_id} 실행이 없다")
    return json.loads(row[0])
