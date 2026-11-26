import argparse
from functools import partial
from pathlib import Path
from typing import Literal

import duckdb
import optuna
import pandas as pd
from pydantic import PositiveFloat, TypeAdapter

from uplift import experiment, learners, plots, policy, ranking, runs, value
from uplift.experiment import Computed, ExperimentConfig
from uplift.features import feature_matrix
from uplift.policy import MAILS
from uplift.selection import choose_method
from uplift.train_data import TrainData, from_duckdb

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
DB = ROOT / "data" / "uplift.duckdb"
CODE = [str(ROOT / "src"), str(HERE)]
POLICIES = ("chosen", "chosen - all_mens", "all_mens")


class Config(ExperimentConfig):
    floor: PositiveFloat
    order: list[learners.Method]
    feature_part: str
    feature_base: learners.Method = "t_learner"
    response_run: str


def parts(cfg: Config) -> list[str]:
    return [*cfg.order, cfg.feature_part]


def part_setup(cfg: Config, part: str) -> tuple[learners.Method, Literal["flags", "segment"]]:
    if part == cfg.feature_part:
        return cfg.feature_base, "segment"
    return TypeAdapter(learners.Method).validate_python(part), "flags"


def interval_metrics(values: pd.DataFrame) -> pd.DataFrame:
    long = values.melt(["seed", "part", "policy"], ["estimate", "low", "high"])
    return pd.DataFrame(
        {
            "model_id": long["part"] + "|" + long["policy"] + "_s" + long["seed"].astype(str),
            "metric": "hajek_" + long["variable"],
            "fold": pd.array([None] * len(long), dtype="Int64"),
            "value": long["value"],
        }
    )


def compute(cfg: Config, data: TrainData, part: str) -> Computed:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    method, product = part_setup(cfg, part)
    df = data.frame
    x = feature_matrix(df, product).to_numpy()
    t = df["treatment_id"].to_numpy()
    y = df[cfg.outcome].to_numpy()
    n = len(df)
    folds = {s: data.fold_array(s) for s in cfg.seeds}

    params, trials = learners.tune(method, x, t, y, folds[cfg.hpo_seed], cfg.n_trials, cfg.hpo_seed)

    all_mens = policy.all_mens(n)
    values, ranks, preds = [], [], []
    for s in cfg.seeds:
        uplift = learners.uplift_oof(method, params, s, x, t, y, folds[s])
        chosen = policy.best_action(uplift)
        sends = int((chosen.argmax(axis=1) != policy.CONTROL).sum())
        for name, pol, base in zip(
            POLICIES, [chosen, chosen, all_mens], [None, all_mens, None], strict=True
        ):
            interval = value.value_interval(
                pol, t, y, "hajek", baseline=base, n_boot=cfg.n_boot, seed=s
            )
            values.append({**interval, "seed": s, "part": part, "policy": name, "sends": sends})
        ranks.append(ranking.ranking_scores(uplift, t, y).assign(seed=s, part=part))
        preds.append(experiment.predictions(f"{part}_s{s}", df["customer_id"], folds[s], uplift))

    values = pd.DataFrame(values)
    return Computed(
        config={"part": part, "best_params": params, "n_customers": n},
        tables={
            "policy_values": values,
            "ranking": pd.concat(ranks, ignore_index=True),
            "hpo_trials": experiment.trial_table(trials).assign(part=part),
        },
        metrics=interval_metrics(values),
        predictions=pd.concat(preds, ignore_index=True),
    )


def same_send(
    cfg: Config,
    rec: duckdb.DuckDBPyConnection,
    data_con: duckdb.DuckDBPyConnection,
    run_id: str,
    part: str,
) -> pd.DataFrame:
    frame = from_duckdb(data_con).frame.set_index("customer_id")
    rows = []
    for s in cfg.seeds:
        uplift = runs.load_scores(rec, run_id, f"{part}_s{s}", MAILS)
        response = runs.load_scores(
            data_con, cfg.response_run, f"response_lgbm_s{s}", MAILS, uplift.index
        )
        df = frame.loc[uplift.index]
        chosen = policy.best_action(uplift.to_numpy())
        sends = int((chosen.argmax(axis=1) != policy.CONTROL).sum())
        matched = policy.top_k(response.to_numpy(), sends)
        t = df["treatment_id"].to_numpy()
        y = df[cfg.outcome].to_numpy()
        interval = value.value_interval(
            chosen, t, y, "hajek", baseline=matched, n_boot=cfg.n_boot, seed=s
        )
        rows.append({**interval, "seed": s, "part": part, "sends": sends})
    return pd.DataFrame(rows)


def method_tables(
    policy_values: pd.DataFrame, cfg: Config
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, str, float]:
    chosen_rows = policy_values[policy_values["policy"] == "chosen"]
    scores = (
        chosen_rows[chosen_rows["part"].isin(cfg.order)]
        .drop(columns="method")
        .rename(columns={"part": "method", "estimate": "value"})[["method", "seed", "value"]]
    )
    pair, choice = choose_method(scores, cfg.order, cfg.floor)
    all_mens = float(policy_values.loc[policy_values["policy"] == "all_mens", "estimate"].mean())
    wide = scores.pivot(index="method", columns="seed", values="value")
    feature = chosen_rows[chosen_rows["part"].isin([cfg.feature_base, cfg.feature_part])]
    feature_wide = feature.pivot(index="seed", columns="part", values="estimate")
    tables = {
        "method_scores": wide.assign(mean=wide.mean(axis=1)).reset_index(),
        "pair_thresholds": pair,
        "method_choice": pd.DataFrame(
            [
                {
                    "chosen": choice,
                    "leader": pair.loc[0, "method"],
                    "all_mens_value": all_mens,
                    "any_beats_all_mens": bool(pair["mean"].max() > all_mens),
                }
            ]
        ),
        "feature_compare": feature_wide.assign(
            diff=feature_wide[cfg.feature_part] - feature_wide[cfg.feature_base]
        ).reset_index(),
    }
    return tables, scores, choice, all_mens


def export(
    rec: duckdb.DuckDBPyConnection,
    data_con: duckdb.DuckDBPyConnection,
    run_ids: list[str],
    out: Path,
) -> None:
    cfg, by_part = runs.common_config(rec, run_ids, Config)
    tables = {
        name: pd.concat([runs.load_table(rec, r, name) for r in run_ids], ignore_index=True)
        for name in ["policy_values", "ranking", "hpo_trials"]
    }
    judged, scores, choice, all_mens = method_tables(tables["policy_values"], cfg)
    judged["response_same_send"] = same_send(cfg, rec, data_con, by_part[choice], choice)
    pair = judged["pair_thresholds"]
    metrics = {
        "run_ids": by_part,
        "chosen": choice,
        "leader": pair.loc[0, "method"],
        "any_beats_all_mens": bool(pair["mean"].max() > all_mens),
    }
    figure = plots.method_score_plot(scores, cfg.order, all_mens)
    experiment.write_outputs(out, tables | judged, {"method_scores": figure}, metrics)


def main() -> None:
    cfg = experiment.load_config(HERE, Config)

    def run_export(args: argparse.Namespace) -> None:
        with duckdb.connect(str(DB), read_only=True) as con:
            export(con, con, args.run_ids, ROOT / "artifacts" / cfg.experiment_id)

    def run_smoke(args: argparse.Namespace) -> None:
        smoke_cfg = experiment.with_smoke(cfg)
        with duckdb.connect(str(DB), read_only=True) as data_con, duckdb.connect() as rec:
            data = from_duckdb(data_con).sample(smoke_cfg.smoke.sample_size, smoke_cfg.smoke.seed)
            run_ids = [
                experiment.record(rec, smoke_cfg, compute(smoke_cfg, data, part))
                for part in parts(cfg)
            ]
            export(rec, data_con, run_ids, args.out)

    def run_compute(args: argparse.Namespace) -> None:
        experiment.run_compute(cfg, args, DB, CODE, partial(compute, part=args.part))

    root, comp = experiment.parser(run_compute, run_export, run_smoke, export_nargs="+")
    comp.add_argument("--part", required=True, choices=parts(cfg))
    args = root.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
