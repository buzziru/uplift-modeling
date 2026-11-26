import subprocess

import duckdb
import pandas as pd
import pytest

from uplift.runs import (
    load_run_config,
    load_table,
    merge_records,
    record_metrics,
    record_predictions,
    record_run,
    record_table,
    require_clean,
    stage,
)


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


def test_record_table_round_trip_and_config():
    con = duckdb.connect()
    run_id = record_run(con, "EXP-001", {"n_boot": 5})
    table = pd.DataFrame(
        {"seed": [42, 154], "comparison": ["a - b", "c - d"], "width": [0.1, 1 / 3]}
    )
    record_table(con, run_id, "diffs", table)
    pd.testing.assert_frame_equal(load_table(con, run_id, "diffs"), table)
    assert load_run_config(con, run_id) == {"n_boot": 5}
    with pytest.raises(KeyError):
        load_table(con, run_id, "missing")


def test_require_clean_stops_on_uncommitted_change(tmp_path, monkeypatch):
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
    monkeypatch.chdir(tmp_path)
    require_clean(["run.py"])
    (tmp_path / "run.py").write_text("b", encoding="utf-8")
    with pytest.raises(RuntimeError):
        require_clean(["run.py"])
    require_clean(["other"])


def test_stage_reuses_parent_only_when_settings_and_files_unchanged(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init")
    (tmp_path / "hpo.py").write_text("a", encoding="utf-8")
    git("add", "hpo.py")
    git("commit", "-m", "init")
    monkeypatch.chdir(tmp_path)
    con = duckdb.connect()
    calls = []

    def compute():
        calls.append(1)
        return pd.DataFrame({"v": [len(calls)]})

    parent = record_run(con, "EXP", {"stages": {"hpo": {"n_trials": 50}}})
    stage(con, parent, "hpo", compute, ["hpo.py"], {"n_trials": 50})
    child = record_run(con, "EXP", {"stages": {"hpo": {"n_trials": 50}}})
    reused = stage(con, child, "hpo", compute, ["hpo.py"], {"n_trials": 50}, parent=parent)
    assert len(calls) == 1 and reused["v"].tolist() == [1]
    assert load_table(con, child, "hpo")["v"].tolist() == [1]

    other = record_run(con, "EXP", {"stages": {"hpo": {"n_trials": 10}}})
    stage(con, other, "hpo", compute, ["hpo.py"], {"n_trials": 10}, parent=parent)
    assert len(calls) == 2

    (tmp_path / "hpo.py").write_text("b", encoding="utf-8")
    git("commit", "-am", "change")
    changed = record_run(con, "EXP", {"stages": {"hpo": {"n_trials": 50}}})
    stage(con, changed, "hpo", compute, ["hpo.py"], {"n_trials": 50}, parent=parent)
    assert len(calls) == 3


def test_merge_records_copies_runs_once(tmp_path):
    source = tmp_path / "run.duckdb"
    with duckdb.connect(str(source)) as src:
        run_id = record_run(src, "EXP", {"a": 1})
        record_table(src, run_id, "t", pd.DataFrame({"v": [1]}))
    con = duckdb.connect()
    assert merge_records(con, source) == [run_id]
    assert load_table(con, run_id, "t")["v"].tolist() == [1]
    with pytest.raises(RuntimeError):
        merge_records(con, source)
