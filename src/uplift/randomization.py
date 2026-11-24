"""무작위 배정 점검(SRM, SMD)과 처치별 평균 차이(ATE).

판정 기준은 docs/DATA.md "무작위 배정은 SRM과 SMD로 점검하고 불균형이면 공변량 보정 회귀로 ATE를 구한다" 절.
"""

import numpy as np
import pandas as pd
from scipy import stats

SRM_ALPHA = 0.001
SMD_THRESHOLD = 0.1
Z95 = stats.norm.ppf(0.975)
Z80 = stats.norm.ppf(0.8)


def srm_test(counts: pd.Series, expected_ratio: pd.Series) -> dict:
    """그룹 크기를 설계 비율과 카이제곱 적합도 검정으로 비교한다."""
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
    """처치군마다 대조군과의 SMD를 공변량별로 구한다. 범주형은 범주마다 비율의 SMD를 구한다."""
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
    """처치군마다 대조군과의 평균 차이, 표준오차, 95% 신뢰구간을 구한다."""
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
    """시험 세트 크기에서 처치군 대 대조군 차이의 표준오차, 95% 구간 반폭, 검정력 80% 최소 효과."""
    var = pd.Series(outcome.groupby(treatment).var())
    rows = []
    for t in sorted(set(treatment) - {control}):
        se = np.sqrt(var[t] / test_counts[t] + var[control] / test_counts[control])
        rows.append(
            {"treatment": t, "se_test": se, "ci_half_width": Z95 * se, "mde_80": (Z95 + Z80) * se}
        )
    return pd.DataFrame(rows)


def funnel_ratios(effect: pd.DataFrame, control: pd.DataFrame) -> pd.DataFrame:
    """효과의 비(구매 증가 / 방문 증가, 매출 증가 / 구매 증가)와 대조군의 같은 비율.

    effect는 비교마다 visit, conversion, spend 효과를 열로 둔 표, control은 대조군 고객의 결과다.
    """
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
