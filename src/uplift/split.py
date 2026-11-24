"""학습·시험 분할과 학습 세트의 seed별 CV fold. 결정은 docs/DATA.md 분할 절."""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel
from sklearn.model_selection import StratifiedKFold, train_test_split


class SplitConfig(BaseModel):
    test_size: float
    test_seed: int
    cv_seeds: list[int]
    n_folds: int


def load_config(path: Path) -> SplitConfig:
    return SplitConfig(**yaml.safe_load(path.read_text(encoding="utf-8")))


def funnel_strata(df: pd.DataFrame) -> pd.Series:
    """처치 x 깔때기 단계(0 방문 안 함, 1 방문만, 2 구매)를 층 하나로 묶는다."""
    return pd.Series(df["treatment_id"] * 3 + df["visit"] + df["conversion"])


def make_splits(
    customer_id: pd.Series, strata: pd.Series, cfg: SplitConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """시험 세트는 test_seed로 한 번 나누고, 학습 세트에만 cv_seeds마다 fold를 매긴다."""
    train_id, test_id = train_test_split(
        customer_id, test_size=cfg.test_size, random_state=cfg.test_seed, stratify=strata
    )
    splits = pd.concat(
        [
            pd.DataFrame({"customer_id": train_id, "split": "train"}),
            pd.DataFrame({"customer_id": test_id, "split": "test"}),
        ]
    ).sort_values("customer_id", ignore_index=True)

    train_strata = strata[customer_id.isin(train_id)]
    train_ids = np.asarray(customer_id[customer_id.isin(train_id)])
    folds = []
    for seed in cfg.cv_seeds:
        kf = StratifiedKFold(n_splits=cfg.n_folds, shuffle=True, random_state=seed)
        for fold, (_, idx) in enumerate(kf.split(train_ids, train_strata)):
            folds.append(pd.DataFrame({"customer_id": train_ids[idx], "seed": seed, "fold": fold}))
    return splits, pd.concat(folds).sort_values(["seed", "customer_id"], ignore_index=True)


def check_splits(splits: pd.DataFrame, folds: pd.DataFrame, customer_id: pd.Series) -> list[str]:
    """모든 고객이 학습·시험 중 하나에만 들고, 학습 고객만 seed마다 fold 하나에 드는지 본다."""
    errors = []
    if not splits["customer_id"].is_unique or set(splits["customer_id"]) != set(customer_id):
        errors.append("splits가 고객마다 한 행이 아님")
    train = set(splits.loc[splits["split"] == "train", "customer_id"])
    for seed, f in folds.groupby("seed"):
        if not f["customer_id"].is_unique or set(f["customer_id"]) != train:
            errors.append(f"seed {seed}의 fold가 학습 고객을 한 번씩 덮지 않음")
    return errors
