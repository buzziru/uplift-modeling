import numpy as np
import pandas as pd

from uplift.randomization import Z80, Z95, ate_diff

QUANTILES = {"p50": 0.5, "p90": 0.9, "p99": 0.99}


def numeric_summary(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in cols:
        x = df[col]
        mode = x.mode().iloc[0]
        rows.append(
            {
                "column": col,
                "mean": x.mean(),
                "std": x.std(),
                "min": x.min(),
                **{name: x.quantile(q) for name, q in QUANTILES.items()},
                "max": x.max(),
                "mode": mode,
                "mode_share": (x == mode).mean(),
            }
        )
    return pd.DataFrame(rows)


def category_shares(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = pd.concat(
        [
            df[col]
            .value_counts()
            .sort_index()
            .rename_axis("level")
            .reset_index(name="n")
            .assign(column=col, share=lambda d: d["n"] / d["n"].sum())
            for col in cols
        ],
        ignore_index=True,
    )
    return pd.DataFrame(out, columns=["column", "level", "n", "share"])


def outcome_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(by):
        buyers = g.loc[g["spend"] > 0, "spend"]
        rows.append(
            {
                by: key,
                "n": len(g),
                "visit_rate": g["visit"].mean(),
                "conversion_rate": g["conversion"].mean(),
                "buyers": len(buyers),
                "spend_mean": g["spend"].mean(),
                "buyer_spend_mean": buyers.mean(),
                **{f"buyer_{name}": buyers.quantile(q) for name, q in QUANTILES.items()},
                "buyer_max": buyers.max(),
                "buyers_at_max": int((buyers == buyers.max()).sum()),
            }
        )
    return pd.DataFrame(rows)


def cramers_v(x: pd.Series, y: pd.Series) -> float:
    table = pd.crosstab(x, y).to_numpy()
    n = table.sum()
    expected = table.sum(axis=1, keepdims=True) * table.sum(axis=0, keepdims=True) / n
    chi2 = ((table - expected) ** 2 / expected).sum()
    return float(np.sqrt(chi2 / n / (min(table.shape) - 1)))


def cramers_v_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [[cramers_v(pd.Series(df[a]), pd.Series(df[b])) for b in cols] for a in cols],
        index=cols,
        columns=cols,
    )


def bootstrap_mean_ci(
    groups: dict[str, np.ndarray], n_boot: int = 5000, seed: int = 0
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    draws = {
        name: x[rng.integers(0, len(x), (n_boot, len(x)))].mean(axis=1)
        for name, x in groups.items()
    }
    rows = [
        {"group": name, "n": len(x), "mean": x.mean(), **_interval(draws[name])}
        for name, x in groups.items()
    ]
    names = list(groups)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            diff = draws[a] - draws[b]
            rows.append(
                {
                    "group": f"{a} - {b}",
                    "n": np.nan,
                    "mean": groups[a].mean() - groups[b].mean(),
                    **_interval(diff),
                }
            )
    return pd.DataFrame(rows)


def _interval(draws: np.ndarray) -> dict[str, float]:
    low, high = np.quantile(draws, [0.025, 0.975])
    return {"ci_low": float(low), "ci_high": float(high)}


PRODUCT_LABELS = {(1, 0): "mens_only", (0, 1): "womens_only", (1, 1): "both"}


def product_segment(df: pd.DataFrame) -> pd.Series:
    return pd.Series(
        [PRODUCT_LABELS[(m, w)] for m, w in zip(df["mens"], df["womens"], strict=True)],
        index=df.index,
        name="product",
    )


def segment_profile(df: pd.DataFrame, by: str) -> pd.DataFrame:
    return (
        df.groupby(by)
        .agg(
            n=("history", "size"),
            history_median=("history", "median"),
            history_mean=("history", "mean"),
            recency_mean=("recency", "mean"),
            newbie_share=("newbie", "mean"),
            multichannel_share=("channel", lambda s: (s == "Multichannel").mean()),
        )
        .reset_index()
    )


COMPARISONS = {0: {1: "Mens - None", 2: "Womens - None"}, 2: {1: "Mens - Womens"}}


def group_means(df: pd.DataFrame, by: str, outcomes: list[str]) -> pd.DataFrame:
    rows = []
    for level, g in df.groupby(by):
        for outcome in outcomes:
            y = g[outcome]
            se = y.std() / np.sqrt(len(y))
            rows.append(
                {
                    by: level,
                    "outcome": outcome,
                    "n": len(y),
                    "mean": y.mean(),
                    "ci_low": y.mean() - Z95 * se,
                    "ci_high": y.mean() + Z95 * se,
                }
            )
    return pd.DataFrame(rows)


def segment_effects(df: pd.DataFrame, by: str, outcome: str) -> pd.DataFrame:
    rows = []
    for level, g in df.groupby(by):
        for control, labels in COMPARISONS.items():
            result = ate_diff(pd.Series(g[outcome]), pd.Series(g["treatment_id"]), control)
            columns = ["treatment", "effect", "ci_low", "ci_high"]
            for t, effect, low, high in result[columns].itertuples(index=False):
                if t in labels:
                    rows.append(
                        {
                            by: level,
                            "comparison": labels[t],
                            "n": len(g),
                            "effect": effect,
                            "ci_low": low,
                            "ci_high": high,
                        }
                    )
    return pd.DataFrame(rows)


def incremental_composition(effects: pd.DataFrame, by: str) -> pd.DataFrame:
    out = pd.DataFrame(effects[effects["comparison"].str.endswith("- None")])
    out["increment"] = out["effect"] * out["n"]
    out["share"] = out["increment"] / out.groupby("comparison")["increment"].transform("sum")
    return pd.DataFrame(out[["comparison", by, "n", "effect", "increment", "share"]])


def funnel_ratio_ci(
    df: pd.DataFrame, by: str, treatment: int, n_boot: int = 2000, seed: int = 0
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for level, g in df.groupby(by):
        arms = {
            t: g.loc[g["treatment_id"] == t, ["visit", "conversion"]].to_numpy()
            for t in (treatment, 0)
        }
        boot = {
            t: x[rng.integers(0, len(x), (n_boot, len(x)))].mean(axis=1) for t, x in arms.items()
        }
        diff = boot[treatment] - boot[0]
        ratio = diff[:, 1] / diff[:, 0]
        point = arms[treatment].mean(axis=0) - arms[0].mean(axis=0)
        rows.append(
            {
                by: level,
                "treatment": treatment,
                "visit_effect": point[0],
                "conversion_effect": point[1],
                "conversion_per_visit": point[1] / point[0],
                **_interval(ratio),
            }
        )
    return pd.DataFrame(rows)


def threshold_effects(df: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    return pd.concat(
        [
            ate_diff(pd.Series(df["spend"] > t, dtype=int), pd.Series(df["treatment_id"])).assign(
                threshold=t
            )
            for t in thresholds
        ],
        ignore_index=True,
    )


def n_per_arm(sd: float, mde: float) -> int:
    return int(np.ceil(2 * ((Z95 + Z80) * sd / mde) ** 2))
