from typing import Literal, TypedDict

from pydantic import ConfigDict, with_config

Method = Literal[
    "s_learner",
    "t_learner",
    "x_learner",
    "dr_learner",
    "uplift_rf",
    "class_transformation",
    "transformed_outcome",
]


@with_config(ConfigDict(extra="forbid"))
class LgbmParams(TypedDict, total=False):
    num_leaves: int
    learning_rate: float
    n_estimators: int
    min_child_samples: int
    subsample: float
    subsample_freq: int
    colsample_bytree: float


@with_config(ConfigDict(extra="forbid"))
class UrfParams(TypedDict, total=False):
    n_estimators: int
    max_depth: int
    min_samples_leaf: int
    max_features: int


Params = LgbmParams | UrfParams
