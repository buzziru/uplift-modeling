"""data/raw/hillstrom.parquet를 DuckDB에 적재하고 분할을 만들고 명세용 요약을 내보낸다.

실행: uv run python scripts/build_db.py (먼저 scripts/fetch_data.py)
"""

import json
from pathlib import Path

import pandas as pd

from uplift.db import build_tables, profile, tables_markdown, write_db
from uplift.split import check_splits, funnel_strata, load_config, make_splits

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hillstrom.parquet"
DB = ROOT / "data" / "uplift.duckdb"
SPLIT_CONFIG = ROOT / "scripts" / "splits.yaml"
PROFILE = ROOT / "artifacts" / "data" / "profile.json"
PREVIEW = ROOT / "artifacts" / "data" / "tables.md"


def main() -> None:
    tables = build_tables(pd.read_parquet(RAW))
    frame = tables["assignments"].merge(tables["outcomes"], on="customer_id")
    ids = pd.Series(frame["customer_id"])
    splits, folds = make_splits(ids, funnel_strata(frame), load_config(SPLIT_CONFIG))
    errors = check_splits(splits, folds, ids)
    if errors:
        raise ValueError("분할 규칙 위반: " + "; ".join(errors))
    tables |= {"splits": splits, "folds": folds}

    write_db(tables, DB)
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(
        json.dumps(profile(tables), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    PREVIEW.write_text(tables_markdown(tables), encoding="utf-8")
    print(f"{DB} 적재, 요약 -> {PROFILE}, 미리보기 -> {PREVIEW}")


if __name__ == "__main__":
    main()
