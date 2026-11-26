import argparse

import numpy as np
import pandas as pd
import pytest

from uplift import experiment
from uplift.experiment import ExperimentConfig, Smoke

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
    assert out[["customer_id", "treatment_id", "score"]].values.tolist() == [
        [7, 1, 0.1],
        [8, 1, 0.3],
        [7, 2, 0.2],
        [8, 2, 0.4],
    ]


def _unreachable(cfg: ExperimentConfig, data) -> experiment.Computed:
    raise AssertionError("smoke db 확인 전에 계산하면 안 된다")


def test_run_compute_smoke_requires_db(tmp_path):
    args = argparse.Namespace(smoke=True, db=None, data=None)
    with pytest.raises(RuntimeError, match="--db"):
        experiment.run_compute(CFG, args, tmp_path / "x.duckdb", [], _unreachable)
