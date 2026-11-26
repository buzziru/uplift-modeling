import duckdb
import pandas as pd

from uplift.runs import record_metrics, record_predictions, record_run


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


def test_record_predictions_appends_rows_with_run_id():
    con = duckdb.connect()
    rows = pd.DataFrame(
        {
            "model_id": "m",
            "customer_id": [1, 2],
            "treatment_id": [1, 2],
            "fold": [0, 1],
            "score": [0.1, 0.2],
        }
    )
    record_predictions(con, "r1", rows)
    record_predictions(con, "r2", rows)
    out = con.execute(
        "SELECT run_id, count(*) FROM predictions GROUP BY run_id ORDER BY run_id"
    ).fetchall()
    assert out == [("r1", 2), ("r2", 2)]
