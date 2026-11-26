import argparse
import json
from pathlib import Path
from typing import Literal

import duckdb
import optuna
import pandas as pd
import yaml
from pydantic import BaseModel

from uplift import oof, plots, policy, ranking, response, runs, value
from uplift.features import feature_matrix
from uplift.train_data import TrainData, from_duckdb, from_parquet

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
DB = ROOT / "data" / "uplift.duckdb"
CODE = [str(ROOT / "src"), str(HERE)]


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
    send_ratios: list[float]
    n_boot: int
    aipw_margin: float
    differences: list[tuple[str, str]]
    seed_range_difference: tuple[str, str]
    run_on: Literal["local", "kaggle"]
    smoke: Smoke


def load_config() -> Config:
    return Config(**yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8")))


def compute(cfg: Config, data: TrainData, rec: duckdb.DuckDBPyConnection) -> str:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    df = data.frame
    folds = {s: data.fold_array(s) for s in cfg.seeds}
    features = feature_matrix(df)
    x = features.to_numpy()
    t = df["treatment_id"].to_numpy()
    y = df[cfg.outcome].to_numpy()
    n = len(df)

    params, trials = response.tune(x, t, y, folds[cfg.hpo_seed], cfg.n_trials, cfg.hpo_seed)

    values, diffs, r2, qini, preds = [], [], [], [], []
    for s in cfg.seeds:
        f = folds[s]
        mu = oof.outcome_model_oof(features, t, y, f)
        scores = response.arm_models_oof(x, t, y, f, params, s)
        policies = {"uniform": policy.uniform(n), "all_mens": policy.all_mens(n)}
        for r in cfg.send_ratios:
            policies[f"response_{round(r * 100)}"] = policy.top_k(scores, round(r * n))
        for name, pol in policies.items():
            values.append(
                value.compare_methods(pol, t, y, mu, n_boot=cfg.n_boot, seed=s).assign(
                    seed=s, policy=name
                )
            )
        for a, b in cfg.differences:
            diffs.append(
                value.compare_methods(
                    policies[a], t, y, mu, baseline=policies[b], n_boot=cfg.n_boot, seed=s
                ).assign(seed=s, comparison=f"{a} - {b}")
            )
        lgbm_mu = response.arm_models_oof(x, t, y, f, params, s, arms=(0, 1, 2))
        for model, m in [("logistic", mu), ("lightgbm", lgbm_mu)]:
            r2.append(oof.within_arm_r2(m, t, y, f).assign(seed=s, outcome_model=model))
        qini.append(ranking.ranking_scores(scores, t, y).assign(seed=s))
        for j, arm in enumerate(policy.MAILS):
            preds.append(
                pd.DataFrame(
                    {
                        "model_id": f"response_lgbm_s{s}",
                        "customer_id": df["customer_id"],
                        "treatment_id": arm,
                        "fold": f,
                        "score": scores[:, j],
                    }
                )
            )

    values = pd.concat(values, ignore_index=True)
    diffs = pd.concat(diffs, ignore_index=True)
    trial_cols = ["number", "value"] + [c for c in trials.columns if c.startswith("params_")]
    tables = {
        "policy_values": values,
        "policy_differences": diffs,
        "outcome_r2": pd.concat(r2, ignore_index=True),
        "response_ranking": pd.concat(qini, ignore_index=True),
        "hpo_trials": trials[trial_cols],
    }

    run_id = runs.record_run(
        rec, cfg.experiment_id, cfg.model_dump() | {"best_params": params, "n_customers": n}
    )
    for name, table in tables.items():
        runs.record_table(rec, run_id, name, table)
    long = pd.concat(
        [
            values.melt(["seed", "policy", "method"], ["estimate", "low", "high"]).assign(
                model_id=lambda d: d["policy"] + "_s" + d["seed"].astype(str)
            ),
            diffs.melt(["seed", "comparison", "method"], ["estimate", "low", "high"]).assign(
                model_id=lambda d: d["comparison"] + "_s" + d["seed"].astype(str)
            ),
        ]
    )
    runs.record_metrics(
        rec,
        run_id,
        long.assign(
            metric=long["method"] + "_" + long["variable"],
            fold=pd.array([None] * len(long), dtype="Int64"),
        )[["model_id", "metric", "fold", "value"]],
    )
    runs.record_predictions(rec, run_id, pd.concat(preds, ignore_index=True))
    return run_id


def export(con: duckdb.DuckDBPyConnection, run_id: str, out: Path) -> None:
    run_cfg = runs.load_run_config(con, run_id)
    cfg = Config(**run_cfg)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    names = ["policy_values", "policy_differences", "outcome_r2", "response_ranking", "hpo_trials"]
    tables = {name: runs.load_table(con, run_id, name) for name in names}
    values, diffs = tables["policy_values"], tables["policy_differences"]

    widths = diffs.pivot_table(index=["seed", "comparison"], columns="method", values="width")
    widths = widths.reset_index()
    choice = value.choose_estimator(widths, cfg.aipw_margin)
    a, b = cfg.seed_range_difference
    ranged = diffs.query("comparison == @a + ' - ' + @b and method == @choice['estimator']")
    seed_range = float(ranged["estimate"].max() - ranged["estimate"].min())
    mean_width = pd.Series(choice["mean_width"])
    tables["estimator_widths"] = widths
    tables["estimator_choice"] = pd.DataFrame(
        {
            "method": mean_width.index,
            "mean_width": mean_width.to_numpy(),
            "ratio_to_ipw": (mean_width / mean_width["ipw"]).to_numpy(),
            "ratio_to_base": (mean_width / mean_width[choice["base"]]).to_numpy(),
            "selected": mean_width.index == choice["estimator"],
        }
    )
    tables["seed_range"] = ranged[["seed", "comparison", "method", "estimate"]].assign(
        seed_range=seed_range
    )
    for name, table in tables.items():
        table.to_csv(out / "tables" / f"{name}.csv", index=False)

    chosen = values.query("method == @choice['estimator']")
    curve = chosen[chosen["policy"].str.startswith("response_")].assign(
        send_ratio=lambda d: d["policy"].str.removeprefix("response_").astype(int) / 100
    )
    refs = {
        p: float(chosen.query("policy == @p")["estimate"].mean()) for p in ["all_mens", "uniform"]
    }
    fig = plots.send_ratio_plot(
        curve, refs, f"Response model OOF visit policy value ({choice['estimator']}, 95% CI)"
    )
    fig.savefig(out / "figures" / "send_ratio.png", dpi=150)

    metrics = {
        "run_id": run_id,
        "n_customers": run_cfg["n_customers"],
        "best_params": run_cfg["best_params"],
        "best_log_loss": float(tables["hpo_trials"]["value"].min()),
        "estimator": choice,
        "seed_range": {"comparison": f"{a} - {b}", "method": choice["estimator"], "range": seed_range},
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    comp = sub.add_parser("compute")
    comp.add_argument("--data", type=Path)
    comp.add_argument("--db", type=Path)
    comp.add_argument("--smoke", action="store_true")
    sub.add_parser("export").add_argument("run_id")
    sub.add_parser("smoke").add_argument("out", type=Path)
    args = parser.parse_args()
    cfg = load_config()
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
            print(compute(cfg, data, rec))
    elif args.command == "export":
        with duckdb.connect(str(DB), read_only=True) as con:
            export(con, args.run_id, ROOT / "artifacts" / cfg.experiment_id)
    else:
        with duckdb.connect(str(DB), read_only=True) as con:
            data = from_duckdb(con).sample(cfg.smoke.sample_size)
        with duckdb.connect() as rec:
            export(rec, compute(cfg, data, rec), args.out)


if __name__ == "__main__":
    main()
