import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb
import numpy as np
import pandas as pd
import yaml
from matplotlib.figure import Figure
from pydantic import BaseModel

from uplift import runs
from uplift.policy import MAILS
from uplift.train_data import TrainData, from_duckdb, from_parquet


class Smoke(BaseModel):
    sample_size: int
    n_trials: int
    n_boot: int
    seed: int = 0


class ExperimentConfig(BaseModel):
    experiment_id: str
    outcome: str
    seeds: list[int]
    hpo_seed: int
    n_trials: int
    n_boot: int
    run_on: Literal["local", "kaggle"] = "local"
    smoke: Smoke


@dataclass
class Computed:
    config: dict
    tables: dict[str, pd.DataFrame]
    metrics: pd.DataFrame
    predictions: pd.DataFrame


def load_config[C: ExperimentConfig](here: Path, model: type[C]) -> C:
    return model(**yaml.safe_load((here / "config.yaml").read_text(encoding="utf-8")))


def with_smoke[C: ExperimentConfig](cfg: C) -> C:
    return cfg.model_copy(update={"n_trials": cfg.smoke.n_trials, "n_boot": cfg.smoke.n_boot})


def train_data(cfg: ExperimentConfig, db: Path, data: Path | None, smoke: bool) -> TrainData:
    if data is None and cfg.run_on == "kaggle":
        raise RuntimeError("이 실험은 Kaggle에서 compute한다: scripts/kaggle.py push")
    if data is None:
        with duckdb.connect(str(db), read_only=True) as con:
            loaded = from_duckdb(con)
    else:
        loaded = from_parquet(data)
    return loaded.sample(cfg.smoke.sample_size, cfg.smoke.seed) if smoke else loaded


def predictions(
    model_id: str, customer_id: pd.Series, folds: np.ndarray, scores: np.ndarray
) -> pd.DataFrame:
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "model_id": model_id,
                    "customer_id": customer_id,
                    "treatment_id": arm,
                    "fold": folds,
                    "score": scores[:, j],
                }
            )
            for j, arm in enumerate(MAILS)
        ],
        ignore_index=True,
    )


def trial_table(trials: pd.DataFrame) -> pd.DataFrame:
    return trials.reindex(
        columns=["number", "value"] + [c for c in trials.columns if c.startswith("params_")]
    )


def record(rec: duckdb.DuckDBPyConnection, cfg: ExperimentConfig, computed: Computed) -> str:
    run_id = runs.record_run(rec, cfg.experiment_id, cfg.model_dump() | computed.config)
    for name, table in computed.tables.items():
        runs.record_table(rec, run_id, name, table)
    runs.record_metrics(rec, run_id, computed.metrics)
    runs.record_predictions(rec, run_id, computed.predictions)
    return run_id


def write_outputs(
    out: Path, tables: dict[str, pd.DataFrame], figures: dict[str, Figure], metrics: dict
) -> None:
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(out / "tables" / f"{name}.csv", index=False)
    for name, fig in figures.items():
        fig.savefig(out / "figures" / f"{name}.png", dpi=150)
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


Command = Callable[[argparse.Namespace], None]


def parser(
    compute: Command, export: Command, smoke: Command, export_nargs: int | str
) -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    comp = sub.add_parser("compute")
    comp.add_argument("--data", type=Path)
    comp.add_argument("--db", type=Path)
    comp.add_argument("--smoke", action="store_true")
    comp.set_defaults(func=compute)
    sub.add_parser("export").set_defaults(func=export)
    sub.choices["export"].add_argument("run_ids", nargs=export_nargs)
    sub.add_parser("smoke").set_defaults(func=smoke)
    sub.choices["smoke"].add_argument("out", type=Path)
    return root, comp


def run_compute[C: ExperimentConfig](
    cfg: C,
    args: argparse.Namespace,
    db: Path,
    code: list[str],
    compute: Callable[[C, TrainData], Computed],
) -> None:
    if args.smoke and args.db is None:
        raise RuntimeError("smoke 설정의 compute는 --db로 따로 기록한다")
    runs.require_clean(code)
    run_cfg = with_smoke(cfg) if args.smoke else cfg
    data = train_data(run_cfg, db, args.data, args.smoke)
    with duckdb.connect(str(args.db or db)) as rec:
        print(record(rec, run_cfg, compute(run_cfg, data)))
