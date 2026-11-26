import numpy as np

CONTROL, MENS, WOMENS = 0, 1, 2
N_ARMS = 3


def fixed(choice: np.ndarray) -> np.ndarray:
    return np.eye(N_ARMS)[np.asarray(choice)]


def all_mens(n: int) -> np.ndarray:
    return fixed(np.full(n, MENS))


def uniform(n: int) -> np.ndarray:
    return np.full((n, N_ARMS), 1 / N_ARMS)


def best_action(uplift: np.ndarray) -> np.ndarray:
    effects = np.column_stack([np.zeros(len(uplift)), uplift])
    return fixed(effects.argmax(axis=1))


def top_k(mail_scores: np.ndarray, k: int) -> np.ndarray:
    best_mail = mail_scores.argmax(axis=1) + 1
    order = np.argsort(-mail_scores.max(axis=1), kind="stable")
    choice = np.full(len(mail_scores), CONTROL)
    choice[order[:k]] = best_mail[order[:k]]
    return fixed(choice)
