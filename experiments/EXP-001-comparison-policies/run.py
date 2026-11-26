import json
from pathlib import Path

import duckdb
import optuna
import pandas as pd
import yaml
from pydantic import BaseModel

from uplift import oof, plots, policy, ranking, response, runs, value
from uplift.db import load_frame
from uplift.features import feature_matrix

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


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


def main() -> None:
    cfg = Config(**yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8")))
    out = ROOT / "artifacts" / cfg.experiment_id
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    con = duckdb.connect(str(ROOT / "data" / "uplift.duckdb"))
    df = load_frame(con, "train")
    features = feature_matrix(df)
    x = features.to_numpy()
    t = df["treatment_id"].to_numpy()
    y = df[cfg.outcome].to_numpy()
    n = len(df)
    folds = {s: oof.load_folds(con, s).loc[df["customer_id"]].to_numpy() for s in cfg.seeds}

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
        for j, arm in enumerate(response.MAIL_ARMS):
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
    r2 = pd.concat(r2, ignore_index=True)
    qini = pd.concat(qini, ignore_index=True)
    widths = diffs.pivot_table(index=["seed", "comparison"], columns="method", values="width")
    choice = value.choose_estimator(widths.reset_index(), cfg.aipw_margin)
    a, b = cfg.seed_range_difference
    ranged = diffs.query("comparison == @a + ' - ' + @b and method == @choice['chosen']")
    seed_range = {
        "comparison": f"{a} - {b}",
        "method": choice["chosen"],
        "estimates": dict(zip(ranged["seed"].astype(str), ranged["estimate"], strict=True)),
        "range": float(ranged["estimate"].max() - ranged["estimate"].min()),
    }

    run_id = runs.record_run(con, cfg.experiment_id, cfg.model_dump() | {"best_params": params})
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
        con,
        run_id,
        long.assign(
            metric=long["method"] + "_" + long["variable"],
            fold=pd.array([None] * len(long), dtype="Int64"),
        )[["model_id", "metric", "fold", "value"]],
    )
    runs.record_predictions(con, run_id, pd.concat(preds, ignore_index=True))
    con.close()

    values.to_csv(out / "tables" / "policy_values.csv", index=False)
    diffs.to_csv(out / "tables" / "policy_differences.csv", index=False)
    widths.reset_index().to_csv(out / "tables" / "estimator_widths.csv", index=False)
    r2.to_csv(out / "tables" / "outcome_r2.csv", index=False)
    qini.to_csv(out / "tables" / "response_ranking.csv", index=False)
    trial_cols = ["number", "value"] + [c for c in trials.columns if c.startswith("params_")]
    trials[trial_cols].to_csv(out / "tables" / "hpo_trials.csv", index=False)

    chosen = values.query("method == @choice['chosen']")
    curve = chosen[chosen["policy"].str.startswith("response_")].assign(
        send_ratio=lambda d: d["policy"].str.removeprefix("response_").astype(int) / 100
    )
    refs = {
        p: float(chosen.query("policy == @p")["estimate"].mean()) for p in ["all_mens", "uniform"]
    }
    fig = plots.send_ratio_plot(
        curve, refs, f"Response model OOF visit policy value ({choice['chosen']}, 95% CI)"
    )
    fig.savefig(out / "figures" / "send_ratio.png", dpi=150)

    metrics = {
        "run_id": run_id,
        "n_customers": n,
        "best_params": params,
        "best_log_loss": float(trials["value"].min()),
        "estimator": choice,
        "seed_range": seed_range,
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
