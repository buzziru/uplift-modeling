import argparse
import importlib.util
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from uplift import experiment, runs
from uplift.experiment import ExperimentConfig, Smoke

EXPERIMENTS = sorted((Path(__file__).resolve().parents[1] / "experiments").glob("*/config.yaml"))

CFG = ExperimentConfig(
    experiment_id="EXP-X",
    outcome="visit",
    seeds=[1],
    hpo_seed=1,
    n_trials=50,
    n_boot=1000,
    run_on="kaggle",
    smoke=Smoke(sample_size=10, n_trials=2, n_boot=20),
)


def test_train_data_kaggle_requires_data(tmp_path):
    with pytest.raises(RuntimeError, match="Kaggle"):
        experiment.train_data(CFG, tmp_path / "x.duckdb", None, smoke=False)


def test_predictions_long_format_per_mail():
    out = experiment.predictions(
        "m", pd.Series([7, 8]), np.array([0, 1]), np.array([[0.1, 0.2], [0.3, 0.4]])
    )
    rows = {tuple(r) for r in out[["customer_id", "treatment_id", "score"]].values.tolist()}
    assert rows == {(7, 1, 0.1), (8, 1, 0.3), (7, 2, 0.2), (8, 2, 0.4)}


def test_with_smoke_uses_smoke_trials_and_boot():
    smoked = experiment.with_smoke(CFG)
    assert (smoked.n_trials, smoked.n_boot) == (2, 20)


class _Record(ExperimentConfig, runs.RunResult):
    pass


def test_record_stores_config_and_result_readable_as_one_record(monkeypatch):
    monkeypatch.setattr(runs, "git_commit", lambda: "abc")
    result = runs.RunResult(
        best_params={
            "num_leaves": 7,
            "learning_rate": 0.1,
            "n_estimators": 30,
            "min_child_samples": 10,
            "subsample": 1.0,
            "subsample_freq": 1,
            "colsample_bytree": 1.0,
        },
        n_customers=10,
    )
    computed = experiment.Computed(
        result=result,
        tables={},
        metrics=pd.DataFrame(columns=["model_id", "metric", "fold", "value"]),
        predictions=pd.DataFrame(
            columns=["model_id", "customer_id", "treatment_id", "fold", "score"]
        ),
    )
    con = duckdb.connect()
    run_id = experiment.record(con, CFG, computed)
    expected = _Record(**CFG.model_dump(), **result.model_dump())
    assert runs.load_run_config(con, run_id, _Record) == expected


@pytest.mark.parametrize("config", EXPERIMENTS, ids=lambda p: p.parent.name)
def test_experiment_config_file_loads_with_its_model(config):
    spec = importlib.util.spec_from_file_location(config.parent.name, config.parent / "run.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"{config.parent}/run.py를 불러오지 못했다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    experiment.load_config(config.parent, module.Config)


def _unreachable(cfg: ExperimentConfig, data) -> experiment.Computed:
    raise AssertionError("smoke db 확인 전에 계산하면 안 된다")


def test_run_compute_smoke_requires_db(tmp_path):
    args = argparse.Namespace(smoke=True, db=None, data=None)
    with pytest.raises(RuntimeError, match="--db"):
        experiment.run_compute(CFG, args, tmp_path / "x.duckdb", [], _unreachable)
