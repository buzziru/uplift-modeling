# experiments 규약

- 실험 기록은 `experiments/TEMPLATE.md` 양식으로 쓴다.
- `run.py`는 `src/`를 불러 DuckDB(`scripts/CLAUDE.md`)에 기록하고, 기록을 `artifacts/<ID>/`로 내보내기만 한다. 하위 명령은 셋이다.
  - `compute`: 계산해 설정, 지표, 예측, 결과 표를 DuckDB에 쓰고 `run_id`를 출력한다. 시작 전에 `runs.require_clean`으로 `src/`와 실험 폴더에 커밋하지 않은 변경이 있으면 멈춘다. DuckDB에 적히는 커밋 해시가 실행한 코드와 맞게 하기 위해서다.
  - `export <run_id>`: 그 실행의 기록을 DuckDB에서 읽어 `artifacts/<ID>/`의 `tables/`, `figures/`, `metrics.json`을 만든다. 다시 계산하지 않으므로 표나 그림을 더할 때는 `export`만 다시 돈다.
  - `smoke <폴더>`: `config.yaml`의 smoke 절 값으로 학습 세트 표본에서 계산해 메모리 DuckDB에 쓰고 지정한 폴더로 내보낸다. 폴더는 저장소 밖 임시 폴더를 쓰고, DuckDB 파일과 `artifacts/`에는 쓰지 않는다.
- 정식 `compute` 전에 `smoke`로 파이프라인과 내보낼 파일을 확인한다.
- `experiment_id`는 실험 폴더 ID(`EXP-001`)이고, 실행마다 `run_id`가 새로 붙는다. Kaggle에서 돌 때는 kaggle-remote-runner 스킬대로 출력 폴더에 쓴다.
- `artifacts/<ID>/`에서 `summary.md` 말고는 `export`로만 만들고 손으로 고치지 않는다. 문서와 사이트가 인용하는 수치는 이 파일을 근거로 단다. `summary.md`가 인용할 수치는 `tables/`에 낸다. `.claude/harness/check_docs.py --summary`는 `tables/`만 대조한다.
- `tests/baseline/`의 기준값 파일은 `tests/CLAUDE.md` 테스트 도입 순서의 regression test 시점에 만든다. 그 전의 실험 실행은 기준값을 만들지 않는다.
