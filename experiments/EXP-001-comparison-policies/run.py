import argparse
from pathlib import Path

import duckdb
import optuna
import pandas as pd

from uplift import experiment, oof, plots, policy, ranking, response, runs, value
from uplift.experiment import Computed, ExperimentConfig
from uplift.features import feature_matrix
from uplift.train_data import TrainData, from_duckdb

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
DB = ROOT / "data" / "uplift.duckdb"
CODE = [str(ROOT / "src"), str(HERE)]


class Config(ExperimentConfig):
    send_ratios: list[float]
    aipw_margin: float
    differences: list[tuple[str, str]]
    seed_range_difference: tuple[str, str]


def interval_metrics(values: pd.DataFrame, diffs: pd.DataFrame) -> pd.DataFrame:
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
    return pd.DataFrame(
        {
            "model_id": long["model_id"],
            "metric": long["method"] + "_" + long["variable"],
            "fold": pd.array([None] * len(long), dtype="Int64"),
            "value": long["value"],
        }
    )


def compute(cfg: Config, data: TrainData) -> Computed:
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
                value.compare_estimators(pol, t, y, mu, n_boot=cfg.n_boot, seed=s).assign(
                    seed=s, policy=name
                )
            )
        for a, b in cfg.differences:
            diffs.append(
                value.compare_estimators(
                    policies[a], t, y, mu, baseline=policies[b], n_boot=cfg.n_boot, seed=s
                ).assign(seed=s, comparison=f"{a} - {b}")
            )
        lgbm_mu = response.arm_models_oof(x, t, y, f, params, s, arms=(0, 1, 2))
        for model, m in [("logistic", mu), ("lightgbm", lgbm_mu)]:
            r2.append(oof.within_arm_r2(m, t, y, f).assign(seed=s, outcome_model=model))
        qini.append(ranking.ranking_scores(scores, t, y).assign(seed=s))
        preds.append(experiment.predictions(f"response_lgbm_s{s}", df["customer_id"], f, scores))

    values = pd.concat(values, ignore_index=True)
    diffs = pd.concat(diffs, ignore_index=True)
    return Computed(
        config={"best_params": params, "n_customers": n},
        tables={
            "policy_values": values,
            "policy_differences": diffs,
            "outcome_r2": pd.concat(r2, ignore_index=True),
            "response_ranking": pd.concat(qini, ignore_index=True),
            "hpo_trials": experiment.trial_table(trials),
        },
        metrics=interval_metrics(values, diffs),
        predictions=pd.concat(preds, ignore_index=True),
    )


def estimator_tables(diffs: pd.DataFrame, cfg: Config) -> tuple[dict[str, pd.DataFrame], dict]:
    widths = diffs.pivot_table(index=["seed", "comparison"], columns="method", values="width")
    widths = widths.reset_index()
    choice = value.choose_estimator(widths, cfg.aipw_margin)
    a, b = cfg.seed_range_difference
    ranged = diffs.query("comparison == @a + ' - ' + @b and method == @choice['estimator']")
    seed_range = float(ranged["estimate"].max() - ranged["estimate"].min())
    mean_width = pd.Series(choice["mean_width"])
    tables = {
        "estimator_widths": widths,
        "estimator_choice": pd.DataFrame(
            {
                "method": mean_width.index,
                "mean_width": mean_width.to_numpy(),
                "ratio_to_ipw": (mean_width / mean_width["ipw"]).to_numpy(),
                "ratio_to_base": (mean_width / mean_width[choice["base"]]).to_numpy(),
                "selected": mean_width.index == choice["estimator"],
            }
        ),
        "seed_range": ranged[["seed", "comparison", "method", "estimate"]].assign(
            seed_range=seed_range
        ),
    }
    summary = {
        "estimator_choice": choice,
        "seed_range": {
            "comparison": f"{a} - {b}",
            "method": choice["estimator"],
            "range": seed_range,
        },
    }
    return tables, summary


def send_ratio_figure(values: pd.DataFrame, estimator: str):
    selected = values.query("method == @estimator")
    curve = selected[selected["policy"].str.startswith("response_")].assign(
        send_ratio=lambda d: d["policy"].str.removeprefix("response_").astype(int) / 100
    )
    refs = {
        p: float(selected.query("policy == @p")["estimate"].mean()) for p in ["all_mens", "uniform"]
    }
    return plots.send_ratio_plot(
        curve, refs, f"Response model OOF visit policy value ({estimator}, 95% CI)"
    )


def export(con: duckdb.DuckDBPyConnection, run_id: str, out: Path) -> None:
    run_cfg = runs.load_run_config(con, run_id)
    cfg = Config(**run_cfg)
    names = ["policy_values", "policy_differences", "outcome_r2", "response_ranking", "hpo_trials"]
    tables = {name: runs.load_table(con, run_id, name) for name in names}
    judged, summary = estimator_tables(tables["policy_differences"], cfg)
    figure = send_ratio_figure(tables["policy_values"], summary["estimator_choice"]["estimator"])
    metrics = {
        "run_id": run_id,
        "n_customers": run_cfg["n_customers"],
        "best_params": run_cfg["best_params"],
        "best_log_loss": float(tables["hpo_trials"]["value"].min()),
        **summary,
    }
    experiment.write_outputs(out, tables | judged, {"send_ratio": figure}, metrics)


def main() -> None:
    cfg = experiment.load_config(HERE, Config)

    def run_export(args: argparse.Namespace) -> None:
        with duckdb.connect(str(DB), read_only=True) as con:
            export(con, args.run_ids[0], ROOT / "artifacts" / cfg.experiment_id)

    def run_smoke(args: argparse.Namespace) -> None:
        smoke_cfg = experiment.with_smoke(cfg)
        with duckdb.connect(str(DB), read_only=True) as con:
            data = from_duckdb(con).sample(smoke_cfg.smoke.sample_size, smoke_cfg.smoke.seed)
        with duckdb.connect() as rec:
            export(rec, experiment.record(rec, smoke_cfg, compute(smoke_cfg, data)), args.out)

    root, _ = experiment.parser(
        lambda args: experiment.run_compute(cfg, args, DB, CODE, compute),
        run_export,
        run_smoke,
        export_nargs=1,
    )
    args = root.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
