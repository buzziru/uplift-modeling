# scripts 규약

- `fetch_data.py`가 원본을 받고 SHA-256, 행 수, 열 이름을 확인한다. 체크섬은 받을 때만 확인하고, PR마다 도는 검사에는 넣지 않는다.
- 분석 테이블과 실험 기록은 DuckDB 파일 `data/uplift.duckdb` 하나에 두고 이것을 정본으로 한다. DB 서버는 두지 않는다. DuckDB 파일은 커밋하지 않는다.
- 적재 산출물(`artifacts/data/`)은 `build_db.py`가 만든다. 손으로 고치지 않는다. 문서가 인용하는 데이터 수치는 이 파일들을 근거로 단다.
- 분할 설정은 `splits.yaml`이다.
