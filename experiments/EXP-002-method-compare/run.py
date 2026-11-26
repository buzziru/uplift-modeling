import argparse
import json
from pathlib import Path
from typing import Literal

import duckdb
import optuna
import pandas as pd
import yaml
from pydantic import BaseModel, PositiveFloat

from uplift import learners, plots, policy, ranking, runs, value
from uplift.features import feature_matrix
from uplift.policy import MENS, WOMENS
from uplift.selection import choose_method
from uplift.train_data import TrainData, from_duckdb, from_parquet

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
DB = ROOT / "data" / "uplift.duckdb"
CODE = [str(ROOT / "src"), str(HERE)]
MAILS = (MENS, WOMENS)


class Smoke(BaseModel):
    sample_size: int
    n_trials: int
    n_boot: int


class Config(BaseModel):
    experiment_id: str
    outcome: str
    seeds: list[int]
    hpo_seed: int
    n_trials: int
    n_boot: int
    floor: PositiveFloat
    order: list[learners.Method]
    feature_part: str
    response_run: str
    run_on: Literal["local", "kaggle"]
    smoke: Smoke


def load_config() -> Config:
    return Config(**yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8")))


def parts(cfg: Config) -> list[str]:
    return [*cfg.order, cfg.feature_part]


def part_setup(cfg: Config, part: str) -> tuple[learners.Method, Literal["flags", "segment"]]:
    if part == cfg.feature_part:
        return "t_learner", "segment"
    return next(m for m in cfg.order if m == part), "flags"


def compute(cfg: Config, data: TrainData, rec: duckdb.DuckDBPyConnection, part: str) -> str:
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
        for name, pol, base in [
            ("chosen", chosen, None),
            ("chosen - all_mens", chosen, all_mens),
            ("all_mens", all_mens, None),
        ]:
            interval = value.value_interval(
                pol, t, y, "hajek", baseline=base, n_boot=cfg.n_boot, seed=s
            )
            values.append({**interval, "seed": s, "part": part, "policy": name, "sends": sends})
        ranks.append(ranking.ranking_scores(uplift, t, y).assign(seed=s, part=part))
        for j, arm in enumerate(MAILS):
            preds.append(
                pd.DataFrame(
                    {
                        "model_id": f"{part}_s{s}",
                        "customer_id": df["customer_id"],
                        "treatment_id": arm,
                        "fold": folds[s],
                        "score": uplift[:, j],
                    }
                )
            )

    run_id = runs.record_run(
        rec,
        cfg.experiment_id,
        cfg.model_dump() | {"part": part, "best_params": params, "n_customers": n},
    )
    values = pd.DataFrame(values)
    trial_cols = ["number", "value"] + [c for c in trials.columns if c.startswith("params_")]
    tables = {
        "policy_values": values,
        "ranking": pd.concat(ranks, ignore_index=True),
        "hpo_trials": trials[trial_cols].assign(part=part),
    }
    for name, table in tables.items():
        runs.record_table(rec, run_id, name, table)
    long = values.melt(["seed", "part", "policy"], ["estimate", "low", "high"])
    runs.record_metrics(
        rec,
        run_id,
        pd.DataFrame(
            {
                "model_id": long["part"] + "|" + long["policy"] + "_s" + long["seed"].astype(str),
                "metric": "hajek_" + long["variable"],
                "fold": pd.array([None] * len(long), dtype="Int64"),
                "value": long["value"],
            }
        ),
    )
    runs.record_predictions(rec, run_id, pd.concat(preds, ignore_index=True))
    return run_id


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


def export(
    rec: duckdb.DuckDBPyConnection,
    data_con: duckdb.DuckDBPyConnection,
    run_ids: list[str],
    out: Path,
) -> None:
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    cfg, by_part = runs.common_config(rec, run_ids, Config)
    tables = {
        name: pd.concat([runs.load_table(rec, r, name) for r in run_ids], ignore_index=True)
        for name in ["policy_values", "ranking", "hpo_trials"]
    }
    pv = tables["policy_values"]
    chosen_rows = pv[pv["policy"] == "chosen"]
    scores = (
        chosen_rows[chosen_rows["part"].isin(cfg.order)]
        .drop(columns="method")
        .rename(columns={"part": "method", "estimate": "value"})[["method", "seed", "value"]]
    )
    pair, choice = choose_method(scores, cfg.order, cfg.floor)
    all_mens = float(pv.loc[pv["policy"] == "all_mens", "estimate"].mean())
    wide = scores.pivot(index="method", columns="seed", values="value")
    tables["method_scores"] = wide.assign(mean=wide.mean(axis=1)).reset_index()
    tables["pair_thresholds"] = pair
    tables["method_choice"] = pd.DataFrame(
        [
            {
                "chosen": choice,
                "leader": pair.loc[0, "method"],
                "all_mens_value": all_mens,
                "any_beats_all_mens": bool(pair["mean"].max() > all_mens),
            }
        ]
    )
    feature = chosen_rows[chosen_rows["part"].isin(["t_learner", cfg.feature_part])]
    feature_wide = feature.pivot(index="seed", columns="part", values="estimate")
    tables["feature_compare"] = feature_wide.assign(
        diff=feature_wide[cfg.feature_part] - feature_wide["t_learner"]
    ).reset_index()
    tables["response_same_send"] = same_send(cfg, rec, data_con, by_part[choice], choice)
    for name, table in tables.items():
        table.to_csv(out / "tables" / f"{name}.csv", index=False)
    plots.method_score_plot(scores, cfg.order, all_mens).savefig(
        out / "figures" / "method_scores.png", dpi=150
    )
    metrics = {
        "run_ids": by_part,
        "chosen": choice,
        "leader": pair.loc[0, "method"],
        "any_beats_all_mens": bool(pair["mean"].max() > all_mens),
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    cfg = load_config()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    comp = sub.add_parser("compute")
    comp.add_argument("--part", required=True, choices=parts(cfg))
    comp.add_argument("--data", type=Path)
    comp.add_argument("--db", type=Path)
    comp.add_argument("--smoke", action="store_true")
    sub.add_parser("export").add_argument("run_ids", nargs="+")
    sub.add_parser("smoke").add_argument("out", type=Path)
    args = parser.parse_args()
    smoke = args.command == "smoke" or (args.command == "compute" and args.smoke)
    if smoke:
        cfg.n_trials, cfg.n_boot = cfg.smoke.n_trials, cfg.smoke.n_boot

    if args.command == "compute":
        if args.data is None and cfg.run_on == "kaggle":
            raise RuntimeError("이 실험은 Kaggle에서 compute한다: scripts/kaggle.py push")
        if args.smoke and args.db is None:
            raise RuntimeError("smoke 설정의 compute는 --db로 따로 기록한다")
        runs.require_clean(CODE)
        if args.data is None:
            with duckdb.connect(str(DB), read_only=True) as con:
                data = from_duckdb(con)
        else:
            data = from_parquet(args.data)
        if smoke:
            data = data.sample(cfg.smoke.sample_size)
        with duckdb.connect(str(args.db or DB)) as rec:
            print(compute(cfg, data, rec, args.part))
    elif args.command == "export":
        with duckdb.connect(str(DB), read_only=True) as con:
            export(con, con, args.run_ids, ROOT / "artifacts" / cfg.experiment_id)
    else:
        with duckdb.connect(str(DB), read_only=True) as data_con, duckdb.connect() as rec:
            data = from_duckdb(data_con).sample(cfg.smoke.sample_size)
            run_ids = [compute(cfg, data, rec, part) for part in parts(cfg)]
            export(rec, data_con, run_ids, args.out)


if __name__ == "__main__":
    main()
