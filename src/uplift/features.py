from typing import Literal

import pandas as pd

from uplift.eda import product_segment

NUMERIC = ["recency", "history", "mens", "womens", "newbie"]
CATEGORICAL = ["zip_code", "channel"]


def feature_matrix(
    df: pd.DataFrame, product: Literal["flags", "segment"] = "flags"
) -> pd.DataFrame:
    dummies = pd.get_dummies(df[CATEGORICAL], drop_first=True, dtype=float)
    numeric = df[NUMERIC].astype(float)
    if product == "segment":
        segment = pd.get_dummies(
            product_segment(df), prefix="product", drop_first=True, dtype=float
        )
        numeric = pd.concat([numeric.drop(columns=["mens", "womens"]), segment], axis=1)
    return pd.concat([numeric, dummies], axis=1)
