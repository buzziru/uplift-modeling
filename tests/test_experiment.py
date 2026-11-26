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


def test_with_smoke_uses_smoke_budget():
    smoke = experiment.with_smoke(CFG)
    assert (smoke.n_trials, smoke.n_boot) == (2, 20)


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


def test_trial_table_keeps_params():
    trials = pd.DataFrame({"number": [0], "value": [0.5], "params_a": [1], "state": ["COMPLETE"]})
    assert list(experiment.trial_table(trials).columns) == ["number", "value", "params_a"]


def test_write_outputs_writes_tables_and_metrics(tmp_path):
    experiment.write_outputs(tmp_path, {"t": pd.DataFrame({"a": [1]})}, {}, {"k": 1})
    assert (
        (tmp_path / "tables" / "t.csv").exists(),
        (tmp_path / "metrics.json").read_text(encoding="utf-8"),
    ) == (
        True,
        '{\n  "k": 1\n}',
    )


@pytest.mark.parametrize("command", ["compute", "export", "smoke"])
def test_parser_dispatches_command(command):
    called = []

    def handler(name):
        return lambda args: called.append(name)

    root, _ = experiment.parser(
        handler("compute"), handler("export"), handler("smoke"), export_nargs="+"
    )
    argv = {"compute": ["compute"], "export": ["export", "r1"], "smoke": ["smoke", "out"]}[command]
    args = root.parse_args(argv)
    args.func(args)
    assert called == [command]


def _unreachable(cfg: ExperimentConfig, data) -> experiment.Computed:
    raise AssertionError("smoke db 확인 전에 계산하면 안 된다")


def test_run_compute_smoke_requires_db(tmp_path):
    args = argparse.Namespace(smoke=True, db=None, data=None)
    with pytest.raises(RuntimeError, match="--db"):
        experiment.run_compute(CFG, args, tmp_path / "x.duckdb", [], _unreachable)
