import pandas as pd

NUMERIC = ["recency", "history", "mens", "womens", "newbie"]
CATEGORICAL = ["zip_code", "channel"]


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    dummies = pd.get_dummies(df[CATEGORICAL], drop_first=True, dtype=float)
    return pd.concat([df[NUMERIC].astype(float), dummies], axis=1)
