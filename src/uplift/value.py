from collections.abc import Callable
from typing import Literal, TypedDict

import numpy as np
import pandas as pd

PROPENSITY = 1 / 3
Estimator = Literal["ipw", "hajek", "aipw"]
Terms = tuple[np.ndarray, np.ndarray]


class Interval(TypedDict):
    method: Estimator
    estimate: float
    low: float
    high: float
    se: float


class EstimatorChoice(TypedDict):
    mean_width: dict[Estimator, float]
    base: Estimator
    aipw_ratio: float
    estimator: Estimator
    hajek_vs_ipw_disagree: int
    aipw_vs_base_disagree: int


def _ipw(policy, treatment, outcome, weight, mu) -> Terms:
    return weight * outcome, np.ones_like(weight)


def _hajek(policy, treatment, outcome, weight, mu) -> Terms:
    return weight * outcome, weight


def _aipw(policy, treatment, outcome, weight, mu) -> Terms:
    if mu is None:
        raise ValueError("aipw에는 mu가 필요하다")
    direct = (policy * mu).sum(axis=1)
    observed = mu[np.arange(len(treatment)), treatment]
    return direct + weight * (outcome - observed), np.ones_like(weight)


ESTIMATORS: dict[
    Estimator,
    Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None], Terms],
] = {"ipw": _ipw, "hajek": _hajek, "aipw": _aipw}
METHODS: tuple[Estimator, ...] = tuple(ESTIMATORS)


def components(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: Estimator,
    mu: np.ndarray | None = None,
) -> Terms:
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome, dtype=float)
    weight = policy[np.arange(len(treatment)), treatment] / PROPENSITY
    return ESTIMATORS[method](policy, treatment, outcome, weight, mu)


def policy_value(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: Estimator = "ipw",
    mu: np.ndarray | None = None,
) -> float:
    num, den = components(policy, treatment, outcome, method, mu)
    return float(num.sum() / den.sum())


def value_interval(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: Estimator = "ipw",
    mu: np.ndarray | None = None,
    baseline: np.ndarray | None = None,
    n_boot: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> Interval:
    parts = [components(policy, treatment, outcome, method, mu)]
    if baseline is not None:
        parts.append(components(baseline, treatment, outcome, method, mu))

    def estimate(idx: np.ndarray | slice) -> float:
        values = [num[idx].sum() / den[idx].sum() for num, den in parts]
        return float(values[0] - values[1]) if baseline is not None else float(values[0])

    rng = np.random.default_rng(seed)
    n = len(parts[0][0])
    boot = np.array([estimate(rng.integers(0, n, n)) for _ in range(n_boot)])
    alpha = (1 - level) / 2
    return {
        "method": method,
        "estimate": estimate(slice(None)),
        "low": float(np.quantile(boot, alpha)),
        "high": float(np.quantile(boot, 1 - alpha)),
        "se": float(boot.std(ddof=1)),
    }


def choose_estimator(widths: pd.DataFrame, aipw_margin: float) -> EstimatorChoice:
    w: dict[Estimator, np.ndarray] = {m: widths[m].to_numpy(dtype=float) for m in METHODS}
    mean: dict[Estimator, float] = {m: float(w[m].mean()) for m in METHODS}
    base: Estimator = "hajek" if mean["hajek"] < mean["ipw"] else "ipw"
    use_aipw = mean["aipw"] <= (1 - aipw_margin) * mean[base]
    aipw_smaller = mean["aipw"] < mean[base]
    return {
        "mean_width": mean,
        "base": base,
        "aipw_ratio": mean["aipw"] / mean[base],
        "estimator": "aipw" if use_aipw else base,
        "hajek_vs_ipw_disagree": int(((w["hajek"] < w["ipw"]) != (base == "hajek")).sum()),
        "aipw_vs_base_disagree": int(((w["aipw"] < w[base]) != aipw_smaller).sum()),
    }


def compare_methods(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    mu: np.ndarray,
    baseline: np.ndarray | None = None,
    n_boot: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    return pd.DataFrame(
        [value_interval(policy, treatment, outcome, m, mu, baseline, n_boot, seed) for m in METHODS]
    ).assign(width=lambda d: d["high"] - d["low"])
