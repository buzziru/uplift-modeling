import numpy as np
import pandas as pd

PROPENSITY = 1 / 3
METHODS = ("ipw", "hajek", "aipw")


def components(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: str,
    mu: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    treatment = np.asarray(treatment)
    outcome = np.asarray(outcome, dtype=float)
    rows = np.arange(len(treatment))
    weight = policy[rows, treatment] / PROPENSITY
    if method == "ipw":
        return weight * outcome, np.ones_like(weight)
    if method == "hajek":
        return weight * outcome, weight
    if method == "aipw":
        if mu is None:
            raise ValueError("aipw에는 mu가 필요하다")
        direct = (policy * mu).sum(axis=1)
        return direct + weight * (outcome - mu[rows, treatment]), np.ones_like(weight)
    raise ValueError(f"알 수 없는 method: {method}")


def policy_value(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: str = "ipw",
    mu: np.ndarray | None = None,
) -> float:
    num, den = components(policy, treatment, outcome, method, mu)
    return float(num.sum() / den.sum())


def value_interval(
    policy: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    method: str = "ipw",
    mu: np.ndarray | None = None,
    baseline: np.ndarray | None = None,
    n_boot: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> dict:
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


def choose_estimator(widths: pd.DataFrame, aipw_margin: float) -> dict:
    w = {m: widths[m].to_numpy(dtype=float) for m in METHODS}
    mean = {m: float(w[m].mean()) for m in METHODS}
    base = "hajek" if mean["hajek"] < mean["ipw"] else "ipw"
    use_aipw = mean["aipw"] <= (1 - aipw_margin) * mean[base]
    row_aipw = w["aipw"] <= (1 - aipw_margin) * w[base]
    return {
        "mean_width": mean,
        "base": base,
        "aipw_ratio": mean["aipw"] / mean[base],
        "chosen": "aipw" if use_aipw else base,
        "hajek_vs_ipw_disagree": int(((w["hajek"] < w["ipw"]) != (base == "hajek")).sum()),
        "aipw_vs_base_disagree": int((row_aipw != use_aipw).sum()),
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
