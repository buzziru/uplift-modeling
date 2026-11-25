import numpy as np
import pandas as pd

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
