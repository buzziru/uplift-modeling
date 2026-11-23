# DuckDB 테이블 미리보기

`scripts/build_db.py`가 적재할 때 만든다. 손으로 고치지 않는다.

## customers (64,000행)

| customer_id (int64) | recency (int64) | history_segment (str) | history (float64) | mens (int64) | womens (int64) | zip_code (str) | newbie (int64) | channel (str) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10 | 2) $100 - $200 | 142.44 | 1 | 0 | Surburban | 0 | Phone |
| 1 | 6 | 3) $200 - $350 | 329.08 | 1 | 1 | Rural | 1 | Web |
| 2 | 7 | 2) $100 - $200 | 180.65 | 0 | 1 | Surburban | 1 | Web |
| 3 | 9 | 5) $500 - $750 | 675.83 | 1 | 0 | Rural | 1 | Web |
| 4 | 2 | 1) $0 - $100 | 45.34 | 1 | 0 | Urban | 0 | Web |

## treatments (3행)

| treatment_id (int64) | name (str) |
| --- | --- |
| 0 | No E-Mail |
| 1 | Mens E-Mail |
| 2 | Womens E-Mail |

## assignments (64,000행)

| customer_id (int64) | treatment_id (int64) |
| --- | --- |
| 0 | 2 |
| 1 | 0 |
| 2 | 2 |
| 3 | 1 |
| 4 | 2 |

## outcomes (64,000행)

| customer_id (int64) | visit (int64) | conversion (int64) | spend (float64) |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0.0 |
| 1 | 0 | 0 | 0.0 |
| 2 | 0 | 0 | 0.0 |
| 3 | 0 | 0 | 0.0 |
| 4 | 0 | 0 | 0.0 |
