import numpy as np
from sklift.metrics import qini_curve, uplift_curve

from uplift.ranking import qini_curves, ranking_scores


def test_qini_and_uplift_curve_match_theory_example():
    top_t = np.r_[np.ones(12), np.zeros(48)]
    top_c = np.r_[np.ones(4), np.zeros(36)]
    y = np.r_[top_t, top_c, np.zeros(50)]
    treated = np.r_[np.ones(60), np.zeros(40), np.tile([1, 0], 25)]
    score = np.r_[np.linspace(2, 1.01, 100), np.linspace(1, 0, 50)]
    x, q = qini_curve(y, score, treated)
    assert q[x == 100][0] == 6
    x, f = uplift_curve(y, score, treated)
    assert f[x == 100][0] == 10


def test_pair_scores_use_only_that_mail_and_control():
    rng = np.random.default_rng(0)
    n = 3000
    t = rng.integers(0, 3, n)
    effect = rng.random((n, 2))
    base = 0.1
    p = base + 0.3 * np.where(t == 1, effect[:, 0], 0) + 0.3 * np.where(t == 2, effect[:, 1], 0)
    y = (rng.random(n) < p).astype(int)
    scores = ranking_scores(effect, t, y)
    assert set(scores["comparison"]) == {"Mens vs None", "Womens vs None"}
    assert (scores["qini_auc"] > 0).all()
    curves = qini_curves(effect, t, y)
    assert curves.groupby("comparison")["n_targeted"].max().tolist() == [
        int(np.isin(t, [0, 1]).sum()),
        int(np.isin(t, [0, 2]).sum()),
    ]
