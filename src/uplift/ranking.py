import numpy as np
import pandas as pd
from sklift.metrics import qini_auc_score, qini_curve, uplift_auc_score

from uplift.policy import CONTROL, MENS, WOMENS

MAILS = {MENS: "Mens vs None", WOMENS: "Womens vs None"}


def _pair(uplift: np.ndarray, treatment: np.ndarray, outcome: np.ndarray, mail: int):
    treatment = np.asarray(treatment)
    mask = np.isin(treatment, [CONTROL, mail])
    return np.asarray(outcome)[mask], uplift[mask, mail - 1], (treatment[mask] == mail).astype(int)


def ranking_scores(uplift: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> pd.DataFrame:
    rows = []
    for mail, name in MAILS.items():
        y, score, treated = _pair(uplift, treatment, outcome, mail)
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
    for mail, name in MAILS.items():
        y, score, treated = _pair(uplift, treatment, outcome, mail)
        x, q = qini_curve(y, score, treated)
        frames.append(pd.DataFrame({"comparison": name, "n_targeted": x, "qini": q}))
    return pd.concat(frames, ignore_index=True)
