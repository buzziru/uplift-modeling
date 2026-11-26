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


def record_metrics(con: duckdb.DuckDBPyConnection, run_id: str, metrics: pd.DataFrame) -> None:
    con.execute(METRICS_DDL)
    rows = metrics.assign(run_id=run_id)[["run_id", "model_id", "metric", "fold", "value"]]
    con.register("new_metrics", rows)
    con.execute("INSERT INTO metrics SELECT * FROM new_metrics")
    con.unregister("new_metrics")
