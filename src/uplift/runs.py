import json
import subprocess
import uuid
from datetime import UTC, datetime

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
    rows = metrics.assign(run_id=run_id)[["run_id", "model_id", "metric", "fold", "value"]]
    _insert(con, "metrics", METRICS_DDL, rows)


def record_predictions(
    con: duckdb.DuckDBPyConnection, run_id: str, predictions: pd.DataFrame
) -> None:
    columns = ["run_id", "model_id", "customer_id", "treatment_id", "fold", "score"]
    _insert(con, "predictions", PREDICTIONS_DDL, predictions.assign(run_id=run_id)[columns])
