import numpy as np
import pandas as pd
from sklift.metrics import qini_auc_score, qini_curve, uplift_auc_score

from uplift.policy import CONTROL, MENS, WOMENS

PAIRS = {
    "Mens vs None": (MENS, CONTROL),
    "Womens vs None": (WOMENS, CONTROL),
    "Mens vs Womens": (MENS, WOMENS),
}


def _pair(
    uplift: np.ndarray, treatment: np.ndarray, outcome: np.ndarray, treated: int, reference: int
):
    treatment = np.asarray(treatment)
    effects = np.column_stack([np.zeros(len(uplift)), uplift])
    score = effects[:, treated] - effects[:, reference]
    mask = np.isin(treatment, [reference, treated])
    return np.asarray(outcome)[mask], score[mask], (treatment[mask] == treated).astype(int)


def ranking_scores(uplift: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> pd.DataFrame:
    rows = []
    for name, pair in PAIRS.items():
        y, score, treated = _pair(uplift, treatment, outcome, *pair)
        rows.append(
            {
                "comparison": name,
                "qini_auc": qini_auc_score(y, score, treated),
                "uplift_auc": uplift_auc_score(y, score, treated),
            }
        )
    return pd.DataFrame(rows)


def qini_curves(uplift: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> pd.DataFrame:
    frames = []
    for name, pair in PAIRS.items():
        y, score, treated = _pair(uplift, treatment, outcome, *pair)
        x, q = qini_curve(y, score, treated)
        frames.append(pd.DataFrame({"comparison": name, "n_targeted": x, "qini": q}))
    return pd.concat(frames, ignore_index=True)
