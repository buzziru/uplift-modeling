import duckdb
import pandas as pd

from uplift.runs import record_metrics, record_run


def test_record_run_and_metrics():
    con = duckdb.connect()
    run_id = record_run(con, "EXP-001", {"seed": 42})
    record_metrics(
        con,
        run_id,
        pd.DataFrame({"model_id": ["m"], "metric": ["ipw"], "fold": [None], "value": [0.2]}),
    )
    assert con.execute("SELECT experiment_id FROM runs").fetchone() == ("EXP-001",)
    assert con.execute("SELECT run_id, value FROM metrics").fetchall() == [(run_id, 0.2)]
