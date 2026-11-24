# experiments 규약

- 실험 기록은 `experiments/TEMPLATE.md` 양식으로 쓴다.
- `run.py`는 `src/`를 부르고, 설정, 지표, 예측을 DuckDB(`scripts/CLAUDE.md`)에 쓰고, `artifacts/<ID>/`로 내보내기만 한다. `experiment_id`는 실험 폴더 ID(`EXP-001`)이고, 실행마다 `run_id`가 새로 붙는다. Kaggle에서 돌 때는 kaggle-remote-runner 스킬대로 출력 폴더에 쓴다.
- 문서와 사이트가 인용하는 수치는 `artifacts/<ID>/`로 내보낸 파일을 근거로 단다. 내보낸 파일은 손으로 고치지 않는다.
- 채택한 실행은 지표(기준값 파일)와 예측을 `tests/baseline/`에 내보내 커밋한다. CI 회귀 테스트는 이 두 파일만 읽어 지표를 다시 계산하고 기준값과 비교한다.
