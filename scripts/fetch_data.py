"""Hillstrom 원본 CSV를 받아 체크섬을 확인하고 Parquet로 저장한다.

실행: uv run python scripts/fetch_data.py
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

import pandas as pd

URL = (
    "http://www.minethatdata.com/"
    "Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
)
SHA256 = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
EXPECTED_ROWS = 64_000
EXPECTED_COLUMNS = [
    "recency",
    "history_segment",
    "history",
    "mens",
    "womens",
    "zip_code",
    "newbie",
    "channel",
    "segment",
    "visit",
    "conversion",
    "spend",
]

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
CSV_PATH = RAW_DIR / "hillstrom.csv"
PARQUET_PATH = RAW_DIR / "hillstrom.parquet"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        urllib.request.urlretrieve(URL, CSV_PATH)

    digest = sha256(CSV_PATH)
    if digest != SHA256:
        sys.exit(f"체크섬 불일치: {digest} != {SHA256}")

    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    if len(df) != EXPECTED_ROWS or list(df.columns) != EXPECTED_COLUMNS:
        sys.exit(f"구조 불일치: rows={len(df)}, columns={list(df.columns)}")

    df.to_parquet(PARQUET_PATH, index=False)
    print(f"sha256={digest} rows={len(df)} -> {PARQUET_PATH}")


if __name__ == "__main__":
    main()
