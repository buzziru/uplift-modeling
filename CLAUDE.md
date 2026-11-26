## 프로젝트

- `SPEC.md`는 시작 명세라 고치지 않는다. 지금 계획은 `docs/plans/`에 있다.
- 되돌리기 어려운 대상은 명령을 막는 대신 대상 쪽에서 지킨다. main은 GitHub branch protection, 프로덕션 배포는 Vercel Git 연동(main 병합 때만), 원본 데이터는 `scripts/fetch_data.py`의 체크섬으로 지킨다. 비밀 값(API 키)은 저장소 밖 Doppler에 두고 `doppler run -p uplift-modeling -c dev -- <명령>`으로 주입한다.

## 명령

- PR 전 검사: `.claude/harness/config.json`의 `check` 목록. 테스트 하나는 `uv run pytest tests/test_policy.py -k <이름>`.
- 데이터 준비: `uv run python scripts/fetch_data.py` 다음 `uv run python scripts/build_db.py`. build_db는 데이터·분할 테이블만 다시 만들고 실험 기록 테이블은 둔다.
- 실험: `run.py smoke <저장소 밖 임시 폴더>`로 확인한 뒤 `compute`, 출력된 run_id로 `export <run_id>`.
- 분석: `uv run marimo edit analyses/<파일>.py`. DuckDB는 ANA-000 노트북이나 `artifacts/data/tables.md`로 본다.

## 커밋하는 산출물

- 나중에 참고할 결과(그림, 표, `metrics.json`, `summary.md`)는 `artifacts/<ID>/`에 저장해 커밋한다. 폴더 이름은 ID만 쓴다. marimo는 실행 결과를 파일에 남기지 않기 때문이다.
- `data/`, 예측 파일, marimo HTML export는 커밋하지 않는다.
