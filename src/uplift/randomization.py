from collections.abc import Hashable
from typing import TypedDict

import numpy as np
import pandas as pd
from scipy import stats

SRM_ALPHA = 0.001
SMD_THRESHOLD = 0.1
Z95 = stats.norm.ppf(0.975)
Z80 = stats.norm.ppf(0.8)


class SrmResult(TypedDict):
    counts: dict[Hashable, int]
    expected: dict[Hashable, float]
    chi2: float
    p_value: float
    mismatch: bool


def srm_test(counts: pd.Series, expected_ratio: pd.Series) -> SrmResult:
    expected = expected_ratio / expected_ratio.sum() * counts.sum()
    chi2, p = stats.chisquare(counts, expected.loc[counts.index])
    return {
        "counts": counts.to_dict(),
        "expected": expected.round(1).to_dict(),
        "chi2": float(chi2),
        "p_value": float(p),
        "mismatch": bool(p < SRM_ALPHA),
    }


def _smd(x1: pd.Series, x0: pd.Series) -> float:
    return float((x1.mean() - x0.mean()) / np.sqrt((x1.var() + x0.var()) / 2))


def smd_table(covariates: pd.DataFrame, treatment: pd.Series, control: int = 0) -> pd.DataFrame:
    rows = []
    x0_all = covariates[treatment == control]
    for t in sorted(set(treatment) - {control}):
        x1_all = covariates[treatment == t]
        for col in covariates.columns:
            if pd.api.types.is_numeric_dtype(covariates[col]):
                levels = [(None, pd.Series(x1_all[col]), pd.Series(x0_all[col]))]
            else:
                levels = [
                    (
                        v,
                        pd.Series(x1_all[col] == v, dtype=float),
                        pd.Series(x0_all[col] == v, dtype=float),
                    )
                    for v in sorted(covariates[col].unique())
                ]
            for level, x1, x0 in levels:
                rows.append({"treatment": t, "covariate": col, "level": level, "smd": _smd(x1, x0)})
    out = pd.DataFrame(rows)
    out["balanced"] = out["smd"].abs() < SMD_THRESHOLD
    return out


def ate_diff(outcome: pd.Series, treatment: pd.Series, control: int = 0) -> pd.DataFrame:
    y0 = outcome[treatment == control]
    rows = []
    for t in sorted(set(treatment) - {control}):
        y1 = outcome[treatment == t]
        effect = y1.mean() - y0.mean()
        se = np.sqrt(y1.var() / len(y1) + y0.var() / len(y0))
        rows.append(
            {
                "treatment": t,
                "mean_treated": y1.mean(),
                "mean_control": y0.mean(),
                "effect": effect,
                "se": se,
                "ci_low": effect - Z95 * se,
                "ci_high": effect + Z95 * se,
                "n_treated": len(y1),
                "n_control": len(y0),
            }
        )
    return pd.DataFrame(rows)


def precision_at_test_size(
    outcome: pd.Series, treatment: pd.Series, test_counts: pd.Series, control: int = 0
) -> pd.DataFrame:
    var = pd.Series(outcome.groupby(treatment).var())
    rows = []
    for t in sorted(set(treatment) - {control}):
        se = np.sqrt(var[t] / test_counts[t] + var[control] / test_counts[control])
        rows.append(
            {
                "treatment": t,
                "n_treatment": test_counts[t],
                "n_control": test_counts[control],
                "se_test": se,
                "ci_half_width": Z95 * se,
                "mde_80": (Z95 + Z80) * se,
            }
        )
    return pd.DataFrame(rows)


def funnel_ratios(effect: pd.DataFrame, control: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "conversion_per_visit": effect["conversion"] / effect["visit"],
            "spend_per_conversion": effect["spend"] / effect["conversion"],
        }
    )
    out.loc["Control baseline"] = [
        control["conversion"].sum() / control["visit"].sum(),
        control["spend"].sum() / control["conversion"].sum(),
    ]
    return out
