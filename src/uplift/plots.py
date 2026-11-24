"""분석 그림(seaborn)."""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure


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
