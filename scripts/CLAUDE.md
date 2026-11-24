# scripts 규약

- `fetch_data.py`가 원본을 받고 SHA-256, 행 수, 열 이름을 확인한다. 체크섬은 받을 때만 확인하고, PR마다 도는 검사에는 넣지 않는다.
- 분석 테이블과 실험 기록은 DuckDB 파일 `data/uplift.duckdb` 하나에 두고 이것을 정본으로 한다. DB 서버는 두지 않는다. DuckDB 파일은 커밋하지 않는다.
- 실행 스크립트가 설정, 지표, 예측을 DuckDB 테이블에 쓴다. `experiment_id`는 실험 폴더 ID(`EXP-001`)이고, 실행마다 `run_id`가 새로 붙는다.
- 채택한 실행은 지표(기준값 파일)와 예측을 `tests/baseline/`에 내보내 커밋한다. CI 회귀 테스트는 이 두 파일만 읽어 지표를 다시 계산하고 기준값과 비교한다.
- 문서와 사이트가 인용하는 수치는 DuckDB에서 `artifacts/<ID>/`로 내보낸 파일이나 `build_db.py`가 만든 `artifacts/data/` 파일을 근거로 단다. 내보낸 파일은 손으로 고치지 않는다.
- 분할 설정은 `splits.yaml`이다.
