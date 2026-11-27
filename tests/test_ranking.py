import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.policy import CONTROL, MENS, WOMENS
from uplift.ranking import PAIRS, qini_curves, ranking_scores


def _theory_example():
    y = np.r_[np.ones(12), np.zeros(48), np.ones(4), np.zeros(36), np.zeros(50)]
    treated = np.r_[np.ones(60), np.zeros(40), np.tile([1, 0], 25)]
    score = np.r_[np.linspace(2, 1.01, 100), np.linspace(1, 0, 50)]
    return y, score, treated


# docs/THEORY.md Qini 예제: 상위 100명에 처치 60명(응답 12), 대조 40명(응답 4)이면 q = 6
def test_qini_curve_theory_example():
    y, score, treated = _theory_example()
    t = np.r_[np.where(treated == 1, MENS, CONTROL), [WOMENS, WOMENS]]
    uplift = np.column_stack([np.r_[score, [0, 0]], np.zeros(len(t))])
    curves = qini_curves(uplift, t, np.r_[y, [1, 0]])
    mens = curves[curves["comparison"] == "Mens vs None"]
    assert mens.loc[mens["n_targeted"] == 100, "qini"].tolist() == [6]


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
    scores = ranking_scores(uplift, t, y).set_index("comparison")
    assert scores.loc["Mens vs Womens", "qini_auc"] > 0


SHIFT_T = np.tile([0, 1, 2], 10)
SHIFT_Y = np.tile([1, 1, 0, 0, 0, 1], 5)


@settings(max_examples=15, deadline=None)
@given(
    arrays(np.float64, (len(SHIFT_T), 2), elements=st.sampled_from([k / 8 for k in range(9)])),
    st.integers(min_value=-3, max_value=3),
)
def test_ranking_scores_ignore_common_shift_of_uplift(uplift, shift):
    before = ranking_scores(uplift, SHIFT_T, SHIFT_Y)["qini_auc"].tolist()
    after = ranking_scores(uplift + shift, SHIFT_T, SHIFT_Y)["qini_auc"].tolist()
    assert after == pytest.approx(before)
