import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from uplift.policy import CONTROL, MENS, WOMENS, all_mens, best_action, top_k, uniform


def test_all_mens_sends_mens_to_everyone():
    assert all_mens(4).argmax(axis=1).tolist() == [MENS] * 4


def test_uniform_gives_each_arm_one_third():
    assert np.allclose(uniform(4), 1 / 3)


def test_top_k_picks_best_mail_for_highest_scores():
    scores = np.array([[0.1, 0.5], [0.9, 0.2], [0.3, 0.1], [0.0, 0.05]])
    choice = top_k(scores, k=2).argmax(axis=1)
    assert choice.tolist() == [WOMENS, MENS, CONTROL, CONTROL]


def test_top_k_breaks_score_ties_by_row_order():
    sent = top_k(np.full((4, 2), 0.5), k=2).argmax(axis=1) != CONTROL
    assert sent.tolist() == [True, True, False, False]


GRID = st.sampled_from([i / 4 for i in range(5)])


@st.composite
def scores_and_k(draw):
    n = draw(st.integers(min_value=1, max_value=50))
    scores = draw(arrays(np.float64, (n, 2), elements=GRID))
    return scores, draw(st.integers(min_value=0, max_value=n))


@settings(max_examples=50, deadline=None)
@given(scores_and_k())
def test_top_k_rows_are_one_hot(case):
    policy = top_k(*case)
    assert np.array_equal(np.sort(policy, axis=1), np.tile([0.0, 0.0, 1.0], (len(policy), 1)))


@settings(max_examples=50, deadline=None)
@given(scores_and_k())
def test_top_k_sends_exactly_k(case):
    scores, k = case
    assert int((top_k(scores, k).argmax(axis=1) != CONTROL).sum()) == k


@settings(max_examples=50, deadline=None)
@given(scores_and_k())
def test_top_k_sends_the_better_scored_mail(case):
    scores, k = case
    choice = top_k(scores, k).argmax(axis=1)
    sent = choice != CONTROL
    assert np.array_equal(scores[sent, choice[sent] - 1], scores[sent].max(axis=1))


@settings(max_examples=50, deadline=None)
@given(scores_and_k())
def test_top_k_sends_no_lower_scores_than_it_skips(case):
    scores, k = case
    sent = top_k(scores, k).argmax(axis=1) != CONTROL
    best = scores.max(axis=1)
    assert best[sent].min(initial=np.inf) >= best[~sent].max(initial=-np.inf)


@pytest.mark.parametrize(
    ("uplift", "arm"),
    [([0.1, 0.3], WOMENS), ([0.2, -0.1], MENS), ([-0.1, -0.2], CONTROL), ([0.0, 0.0], CONTROL)],
    ids=["womens", "mens", "all_negative", "all_zero"],
)
def test_best_action_picks_arm(uplift, arm):
    assert best_action(np.array([uplift])).argmax(axis=1).tolist() == [arm]


UPLIFTS = arrays(
    np.float64,
    st.tuples(st.integers(min_value=1, max_value=30), st.just(2)),
    elements=st.sampled_from([-1.0, -0.5, 0.0, 0.5, 1.0]),
)


@settings(max_examples=50, deadline=None)
@given(UPLIFTS)
def test_best_action_takes_arm_with_largest_effect(uplift):
    effects = np.column_stack([np.zeros(len(uplift)), uplift])
    chosen = effects[np.arange(len(uplift)), best_action(uplift).argmax(axis=1)]
    assert np.array_equal(chosen, effects.max(axis=1))


@settings(max_examples=50, deadline=None)
@given(UPLIFTS)
def test_best_action_mails_nobody_without_positive_uplift(uplift):
    no_gain = uplift.max(axis=1) <= 0
    assert (best_action(uplift).argmax(axis=1)[no_gain] == CONTROL).all()
