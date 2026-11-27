import numpy as np
import pytest
from sklift.metrics import qini_curve, uplift_curve

from uplift.ranking import PAIRS, qini_curves, ranking_scores


def _theory_example():
    y = np.r_[np.ones(12), np.zeros(48), np.ones(4), np.zeros(36), np.zeros(50)]
    treated = np.r_[np.ones(60), np.zeros(40), np.tile([1, 0], 25)]
    score = np.r_[np.linspace(2, 1.01, 100), np.linspace(1, 0, 50)]
    return y, score, treated


def test_qini_curve_theory_example():
    x, q = qini_curve(*_theory_example())
    assert q[x == 100][0] == 6


def test_uplift_curve_theory_example():
    x, f = uplift_curve(*_theory_example())
    assert f[x == 100][0] == 10


@pytest.fixture(scope="module")
def planted_pairs():
    rng = np.random.default_rng(0)
    n = 3000
    t = rng.integers(0, 3, n)
    effect = rng.random((n, 2))
    base = 0.1
    p = base + 0.3 * np.where(t == 1, effect[:, 0], 0) + 0.3 * np.where(t == 2, effect[:, 1], 0)
    y = (rng.random(n) < p).astype(int)
    return effect, t, y


def test_ranking_scores_cover_every_pair(planted_pairs):
    scores = ranking_scores(*planted_pairs)
    assert set(scores["comparison"]) == set(PAIRS)


def test_ranking_scores_find_planted_effects(planted_pairs):
    scores = ranking_scores(*planted_pairs)
    assert bool((scores["qini_auc"].to_numpy() > 0).all())


@pytest.mark.parametrize(("name", "pair"), PAIRS.items())
def test_qini_curve_targets_only_the_two_groups_of_the_pair(planted_pairs, name, pair):
    effect, t, y = planted_pairs
    curves = qini_curves(effect, t, y)
    n_targeted = curves.loc[curves["comparison"] == name, "n_targeted"].to_numpy().max()
    assert n_targeted == np.isin(t, pair).sum()


def test_mail_pair_ranks_by_uplift_difference():
    n = 600
    t = np.tile([0, 1, 2], n // 3)
    u_mens = np.r_[np.full(n // 2, 0.5), np.zeros(n // 2)]
    uplift = np.column_stack([u_mens, np.full(n, 0.2)])
    y = (((t == 1) & (u_mens > 0)) | ((t != 1) & (np.arange(n) % 6 < 3))).astype(int)
    shifted = uplift + 1.0
    a = ranking_scores(uplift, t, y).set_index("comparison")
    b = ranking_scores(shifted, t, y).set_index("comparison")
    assert a.loc["Mens vs Womens", "qini_auc"] > 0
    assert a.loc["Mens vs Womens", "qini_auc"] == b.loc["Mens vs Womens", "qini_auc"]
