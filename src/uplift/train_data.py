from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from uplift.db import load_frame

TRAIN_FILE = "train.parquet"
FOLDS_FILE = "folds.parquet"


@dataclass
class TrainData:
    frame: pd.DataFrame
    folds: pd.DataFrame

    def fold_array(self, seed: int) -> np.ndarray:
        rows = self.folds[self.folds["seed"] == seed].set_index("customer_id")["fold"]
        return rows.loc[self.frame["customer_id"]].to_numpy()

    def sample(self, n: int, seed: int = 0) -> "TrainData":
        keep = np.sort(np.random.default_rng(seed).choice(len(self.frame), n, replace=False))
        frame = self.frame.iloc[keep].reset_index(drop=True)
        folds = self.folds.loc[self.folds["customer_id"].isin(frame["customer_id"])]
        return TrainData(frame, pd.DataFrame(folds).reset_index(drop=True))


def from_duckdb(con: duckdb.DuckDBPyConnection) -> TrainData:
    frame = load_frame(con, "train")
    folds = con.execute(
        "SELECT f.* FROM folds AS f INNER JOIN splits AS s"
        " ON f.customer_id = s.customer_id AND s.split = 'train'"
        " ORDER BY f.seed, f.customer_id"
    ).df()
    return TrainData(frame, folds)


def from_parquet(folder: Path) -> TrainData:
    return TrainData(pd.read_parquet(folder / TRAIN_FILE), pd.read_parquet(folder / FOLDS_FILE))


def to_parquet(data: TrainData, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    data.frame.to_parquet(folder / TRAIN_FILE, index=False)
    data.folds.to_parquet(folder / FOLDS_FILE, index=False)
