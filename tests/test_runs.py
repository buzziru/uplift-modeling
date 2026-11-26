import subprocess

import duckdb
import pandas as pd
import pydantic
import pytest

from uplift import runs
from uplift.runs import (
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


def test_record_table_round_trip():
    con = duckdb.connect()
    table = pd.DataFrame(
        {"seed": [42, 154], "comparison": ["a - b", "c - d"], "width": [0.1, 1 / 3]}
    )
    record_table(con, "r1", "diffs", table)
    pd.testing.assert_frame_equal(load_table(con, "r1", "diffs"), table)


def test_load_run_config_returns_config():
    con = duckdb.connect()
    run_id = record_run(con, "EXP-001", {"n_boot": 5})
    assert load_run_config(con, run_id) == {"n_boot": 5}


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


def test_load_scores_pivots_arms_in_given_order():
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
    scores = load_scores(con, "r", "m", (2, 1))
    assert scores.loc[1].tolist() == [0.2, 0.1]
    with pytest.raises(KeyError):
        load_scores(con, "r", "other", (1, 2))


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


class _Cfg(pydantic.BaseModel):
    seed: int


def _runs_with(configs):
    con = duckdb.connect()
    return con, [record_run(con, "EXP", c) for c in configs]


def test_common_config_maps_parts():
    con, ids = _runs_with([{"seed": 1, "part": "a"}, {"seed": 1, "part": "b"}])
    cfg, by_part = common_config(con, ids, _Cfg)
    assert (cfg, by_part) == (_Cfg(seed=1), {"a": ids[0], "b": ids[1]})


def test_common_config_rejects_mixed_settings():
    con, ids = _runs_with([{"seed": 1, "part": "a"}, {"seed": 2, "part": "b"}])
    with pytest.raises(ValueError, match="서로 다르다"):
        common_config(con, ids, _Cfg)


def test_common_config_rejects_repeated_part():
    con, ids = _runs_with([{"seed": 1, "part": "a"}, {"seed": 1, "part": "a"}])
    with pytest.raises(ValueError, match="여럿"):
        common_config(con, ids, _Cfg)
