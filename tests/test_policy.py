import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.policy import CONTROL, MENS, WOMENS, all_mens, best_action, top_k, uniform


def test_fixed_policies():
    assert (all_mens(4).argmax(axis=1) == MENS).all()
    assert np.allclose(uniform(4), 1 / 3)


def test_top_k_picks_best_mail_for_highest_scores():
    scores = np.array([[0.1, 0.5], [0.9, 0.2], [0.3, 0.1], [0.0, 0.05]])
    choice = top_k(scores, k=2).argmax(axis=1)
    assert choice.tolist() == [WOMENS, MENS, CONTROL, CONTROL]


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=50), st.data())
def test_top_k_sends_exactly_k(n, data):
    k = data.draw(st.integers(min_value=0, max_value=n))
    scores = np.random.default_rng(n).random((n, 2))
    policy = top_k(scores, k)
    assert np.allclose(policy.sum(axis=1), 1)
    assert int((policy.argmax(axis=1) != CONTROL).sum()) == k


@pytest.mark.parametrize(
    ("uplift", "arm"),
    [([0.1, 0.3], WOMENS), ([0.2, -0.1], MENS), ([-0.1, -0.2], CONTROL), ([0.0, 0.0], CONTROL)],
    ids=["womens", "mens", "all_negative", "all_zero"],
)
def test_best_action_picks_arm(uplift, arm):
    assert best_action(np.array([uplift])).argmax(axis=1).tolist() == [arm]
