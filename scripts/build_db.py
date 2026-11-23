"""data/raw/hillstrom.parquet를 DuckDB에 적재하고 명세용 요약을 내보낸다.

실행: uv run python scripts/build_db.py (먼저 scripts/fetch_data.py)
"""

import json
from pathlib import Path

import pandas as pd

from uplift.db import build_tables, profile, tables_markdown, write_db

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hillstrom.parquet"
DB = ROOT / "data" / "uplift.duckdb"
PROFILE = ROOT / "artifacts" / "data" / "profile.json"
PREVIEW = ROOT / "artifacts" / "data" / "tables.md"


def main() -> None:
    tables = build_tables(pd.read_parquet(RAW))
    write_db(tables, DB)
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(
        json.dumps(profile(tables), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    PREVIEW.write_text(tables_markdown(tables), encoding="utf-8")
    print(f"{DB} 적재, 요약 -> {PROFILE}, 미리보기 -> {PREVIEW}")


if __name__ == "__main__":
    main()
