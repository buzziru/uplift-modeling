"""분석 그림(seaborn)."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure
from matplotlib.ticker import NullFormatter, ScalarFormatter


def smd_plot(smd: pd.DataFrame, threshold: float) -> Figure:
    """공변량(범주형은 범주)별 |SMD|를 처치 정의마다 점으로 찍고 기준선을 긋는다."""
    df = smd.assign(
        label=(
            smd["covariate"] + smd["level"].map(lambda v: "" if pd.isna(v) else f" = {v}")
        ).str.replace("$", r"\$"),
        abs_smd=smd["smd"].abs(),
    )
    fig, ax = plt.subplots(figsize=(7, 0.28 * df["label"].nunique() + 1.5))
    sns.stripplot(data=df, x="abs_smd", y="label", hue="comparison", ax=ax, jitter=False, size=6)
    ax.axvline(threshold, color="gray", linestyle="--", linewidth=1)
    ax.set(xlabel="|SMD|", ylabel="")
    ax.legend(title="", loc="lower right")
    fig.tight_layout()
    return fig


def numeric_distribution_plot(df: pd.DataFrame) -> Figure:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    history = df["history"].to_numpy()
    sns.histplot(x=history, bins=60, ax=axes[0])
    axes[0].set(title="history", xlabel="USD", ylabel="customers")
    sns.histplot(x=history, bins=60, log_scale=True, ax=axes[1])
    axes[1].set(title="history (log scale)", xlabel="USD", ylabel="")
    sns.countplot(x=df["recency"].to_numpy(), color="C0", ax=axes[2])
    axes[2].set(title="recency", xlabel="months since last purchase", ylabel="")
    fig.tight_layout()
    return fig


def category_share_plot(shares: pd.DataFrame) -> Figure:
    cols = list(dict.fromkeys(shares["column"]))
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.5))
    for ax, col in zip(axes.flat, cols, strict=True):
        part = pd.DataFrame(shares.loc[shares["column"] == col])
        labels = part["level"].astype(str).str.replace("$", r"\$")
        sns.barplot(x=part["share"].to_numpy(), y=labels.to_numpy(), color="C0", ax=ax)
        ax.set(title=col, xlabel="share", ylabel="", xlim=(0, 1))
    fig.tight_layout()
    return fig


def buyer_spend_plot(spend: pd.Series) -> Figure:
    values = spend.to_numpy()
    buyers = values[values > 0]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    sns.histplot(x=buyers, bins=50, ax=axes[0])
    axes[0].set(title="spend of buyers", xlabel="USD", ylabel="customers")
    sns.histplot(x=buyers, bins=40, log_scale=True, ax=axes[1])
    axes[1].set(title="spend of buyers (log scale)", xlabel="USD", ylabel="")
    axes[1].set_xticks([30, 50, 100, 200, 500])
    axes[1].xaxis.set_major_formatter(ScalarFormatter())
    axes[1].xaxis.set_minor_formatter(NullFormatter())
    for q, style in [(0.5, "-"), (0.9, "--"), (0.99, ":")]:
        value = float(np.quantile(buyers, q))
        for ax in axes:
            ax.axvline(value, color="gray", linestyle=style, linewidth=1, label=f"p{int(q * 100)}")
    axes[1].legend(loc="upper right")
    fig.tight_layout()
    return fig


def association_heatmaps(spearman: pd.DataFrame, cramers: pd.DataFrame) -> Figure:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    sns.heatmap(spearman, vmin=-1, vmax=1, cmap="vlag", annot=True, fmt=".2f", ax=axes[0])
    axes[0].set(title="Spearman")
    sns.heatmap(cramers, vmin=0, vmax=1, cmap="mako_r", annot=True, fmt=".2f", ax=axes[1])
    axes[1].set(title="Cramer's V")
    fig.tight_layout()
    return fig


def ecdf_by_group(df: pd.DataFrame, value: str, group: str, title: str) -> Figure:
    data = pd.DataFrame(df[[group, value]])
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.ecdfplot(data=data, x=value, hue=group, log_scale=True, ax=ax)
    ax.set_xticks([30, 50, 100, 200, 500, 1000, 3000])
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set(title=title, xlabel=f"{value} (USD, log scale)", ylabel="share")
    fig.tight_layout()
    return fig


def buyer_spend_ecdf(df: pd.DataFrame, group: str) -> Figure:
    buyers = pd.DataFrame(df.loc[df["spend"] > 0])
    fig = ecdf_by_group(buyers, "spend", group, "spend of buyers by treatment")
    fig.axes[0].set_xlim(25, 600)
    return fig


def share_heatmap(table: pd.DataFrame, title: str) -> Figure:
    fig, ax = plt.subplots(figsize=(1.3 * table.shape[1] + 2, 0.5 * table.shape[0] + 1.5))
    sns.heatmap(table, vmin=0, vmax=1, cmap="mako_r", annot=True, fmt=".2f", cbar=False, ax=ax)
    ax.set(title=title)
    ax.tick_params(axis="y", rotation=0)
    fig.tight_layout()
    return fig
