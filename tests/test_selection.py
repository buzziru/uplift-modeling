import pandas as pd

from uplift.selection import choose_method

ORDER = ["s", "t", "x"]


def _scores(values):
    return pd.DataFrame(
        [
            {"method": m, "seed": s, "value": v}
            for m, vs in values.items()
            for s, v in zip([42, 154, 1592], vs, strict=True)
        ]
    )


def test_picks_simplest_method_within_threshold_of_leader():
    table, chosen = choose_method(
        _scores({"s": [0.180, 0.181, 0.179], "t": [0.181, 0.183, 0.182], "x": [0.15, 0.15, 0.15]}),
        ORDER,
        0.0038,
    )
    assert chosen == "s"
    assert table.loc[table["method"] == "x", "distinguishable"].item()


def test_floor_applies_when_pair_range_is_small():
    table, chosen = choose_method(
        _scores({"s": [0.170, 0.170, 0.170], "t": [0.175, 0.175, 0.175]}), ORDER, 0.0038
    )
    row = table.set_index("method").loc["s"]
    assert (row["seed_range"], row["threshold"], chosen) == (0, 0.0038, "t")


def test_pair_range_widens_threshold_beyond_floor():
    table, chosen = choose_method(
        _scores({"s": [0.170, 0.180, 0.172], "t": [0.180, 0.181, 0.180]}), ORDER, 0.0038
    )
    assert table.set_index("method").loc["s", "threshold"] > 0.0038
    assert chosen == "s"
