import subprocess

import duckdb
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift import runs
from uplift.methods import LgbmParams
from uplift.runs import (
    RunResult,
    common_config,
    load_run_config,
    load_scores,
    load_table,
    merge_records,
    record_metrics,
    record_predictions,
    record_run,
    record_table,
    require_clean,
)


def test_record_run_stores_experiment():
    con = duckdb.connect()
    record_run(con, "EXP-001", {"seed": 42})
    assert con.execute("SELECT experiment_id FROM runs").fetchone() == ("EXP-001",)


def test_record_metrics_stores_values():
    con = duckdb.connect()
    record_metrics(
        con,
        "r1",
        pd.DataFrame({"model_id": ["m"], "metric": ["ipw"], "fold": [None], "value": [0.2]}),
    )
    assert con.execute("SELECT run_id, value FROM metrics").fetchall() == [("r1", 0.2)]


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


@st.composite
def _tables(draw):
    n = draw(st.integers(1, 5))
    column = st.lists
    text = st.text(st.characters(codec="utf-8", exclude_categories=["Cs"]), max_size=8)
    return pd.DataFrame(
        {
            "i": draw(column(st.integers(-(2**53), 2**53), min_size=n, max_size=n)),
            "f": draw(column(st.floats(-1e9, 1e9, allow_nan=False), min_size=n, max_size=n)),
            "s": draw(column(text, min_size=n, max_size=n)),
            "b": draw(column(st.booleans(), min_size=n, max_size=n)),
        }
    )


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_tables())
def test_record_table_round_trip_keeps_values_and_dtypes(table):
    con = duckdb.connect()
    record_table(con, "r1", "t", table)
    pd.testing.assert_frame_equal(load_table(con, "r1", "t"), table, rtol=1e-13)


def test_load_table_reads_tables_recorded_before_dtype_schema():
    con = duckdb.connect()
    con.execute(runs.RUN_TABLES_DDL)
    con.execute("INSERT INTO run_tables VALUES (?, ?, ?)", ["r1", "t", '[{"seed":42,"width":0.5}]'])
    assert load_table(con, "r1", "t").to_dict("records") == [{"seed": 42, "width": 0.5}]


PARAMS: LgbmParams = {
    "num_leaves": 7,
    "learning_rate": 0.1,
    "n_estimators": 30,
    "min_child_samples": 10,
    "subsample": 1.0,
    "subsample_freq": 1,
    "colsample_bytree": 1.0,
}


class _Cfg(RunResult):
    seed: int


def test_load_run_config_round_trips_recorded_config():
    con = duckdb.connect()
    cfg = _Cfg(seed=1, best_params=PARAMS, n_customers=10)
    run_id = record_run(con, "EXP", cfg.model_dump(exclude_none=True))
    assert load_run_config(con, run_id, _Cfg) == cfg


def test_load_run_config_missing_run_raises():
    con = duckdb.connect()
    record_run(con, "EXP", {"seed": 1, "best_params": PARAMS, "n_customers": 1})
    with pytest.raises(KeyError, match="r9"):
        load_run_config(con, "r9", _Cfg)


def test_load_table_missing_raises():
    con = duckdb.connect()
    record_table(con, "r1", "diffs", pd.DataFrame({"a": [1]}))
    with pytest.raises(KeyError):
        load_table(con, "r1", "missing")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init")
    (tmp_path / "run.py").write_text("a", encoding="utf-8")
    git("add", "run.py")
    git("commit", "-m", "init")
    monkeypatch.setattr(runs, "ROOT", tmp_path)
    return tmp_path


def test_require_clean_passes_committed(repo):
    require_clean(["run.py"])


def test_require_clean_stops_on_uncommitted_change(repo):
    (repo / "run.py").write_text("b", encoding="utf-8")
    with pytest.raises(RuntimeError):
        require_clean(["run.py"])


def test_require_clean_ignores_other_paths(repo):
    (repo / "run.py").write_text("b", encoding="utf-8")
    require_clean(["other"])


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "run.duckdb"
    with duckdb.connect(str(path)) as src:
        run_id = record_run(src, "EXP", {"a": 1})
        record_table(src, run_id, "t", pd.DataFrame({"v": [1]}))
    return path, run_id


def test_merge_records_copies_runs_and_tables(source):
    path, run_id = source
    con = duckdb.connect()
    merge_records(con, path)
    assert load_table(con, run_id, "t")["v"].tolist() == [1]


def test_merge_records_rejects_runs_already_merged(source):
    path, run_id = source
    con = duckdb.connect()
    merge_records(con, path)
    with pytest.raises(RuntimeError, match=run_id):
        merge_records(con, path)


def _scores_con():
    con = duckdb.connect()
    preds = pd.DataFrame(
        {
            "model_id": "m",
            "customer_id": [1, 1, 2, 2],
            "treatment_id": [1, 2, 1, 2],
            "fold": 0,
            "score": [0.1, 0.2, 0.3, 0.4],
        }
    )
    record_predictions(con, "r", preds)
    return con


def test_load_scores_pivots_arms_in_given_order():
    scores = load_scores(_scores_con(), "r", "m", (2, 1))
    assert scores.loc[1].tolist() == [0.2, 0.1]


def test_load_scores_missing_model_raises():
    with pytest.raises(KeyError, match="other"):
        load_scores(_scores_con(), "r", "other", (1, 2))


def test_load_scores_rejects_missing_arm():
    with pytest.raises(KeyError, match="3"):
        load_scores(_scores_con(), "r", "m", (1, 3))


def test_load_scores_follows_customer_order():
    scores = load_scores(_scores_con(), "r", "m", (1, 2), pd.Index([2, 1]))
    assert scores.index.tolist() == [2, 1]


def test_load_scores_missing_customer_raises():
    with pytest.raises(KeyError, match="1명"):
        load_scores(_scores_con(), "r", "m", (1, 2), pd.Index([1, 9]))


def test_record_metrics_rejects_missing_column():
    with pytest.raises(KeyError, match="fold"):
        record_metrics(
            duckdb.connect(),
            "r",
            pd.DataFrame({"model_id": ["m"], "metric": ["x"], "value": [1.0]}),
        )


def _runs_with(*runs_):
    con = duckdb.connect()
    ids = [
        record_run(
            con, "EXP", {"n_customers": 10, "best_params": PARAMS | {"num_leaves": 7 + i}} | r
        )
        for i, r in enumerate(runs_)
    ]
    return con, ids


def test_common_config_maps_parts_despite_different_run_results():
    con, ids = _runs_with({"seed": 1, "part": "a"}, {"seed": 1, "part": "b"})
    _, by_part = common_config(con, ids, _Cfg)
    assert by_part == {"a": ids[0], "b": ids[1]}


def test_common_config_rejects_mixed_settings():
    con, ids = _runs_with({"seed": 1, "part": "a"}, {"seed": 2, "part": "b"})
    with pytest.raises(ValueError, match=ids[1]):
        common_config(con, ids, _Cfg)


def test_common_config_rejects_repeated_part():
    con, ids = _runs_with({"seed": 1, "part": "dup"}, {"seed": 1, "part": "dup"})
    with pytest.raises(ValueError, match="dup"):
        common_config(con, ids, _Cfg)


def test_common_config_rejects_run_without_part():
    con, ids = _runs_with({"seed": 1, "part": "a"}, {"seed": 1})
    with pytest.raises(ValueError, match=ids[1]):
        common_config(con, ids, _Cfg)
