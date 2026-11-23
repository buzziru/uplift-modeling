# ENGINEERING.md: 엔지니어링

담는 범위: 저장 형식, 폴더 구조, 테스트, 품질 도구, CI, 재현 허용 오차, 배포.

지금 유효한 결정만 둔다. 결정마다 아래 절을 하나씩 만든다. 바뀐 이력은 git 커밋에 남긴다.

<!--
## <결정 제목: 결정 내용을 한 문장으로>

- 결정:
- 근거: 수치와 결과 파일 경로
- 기각한 대안: 대안과 기각 이유
-->

## 탐색과 결정에 쓰는 분석은 marimo 노트북에서 하고, 계산은 `src/`에 둔다

- 결정:
  - 탐색(EDA)과 결정에 쓰는 분석에는 Jupyter 대신 marimo 노트북(`.py`)을 쓴다. 노트북 작성은 `.claude/skills/marimo-notebook` 스킬을 따른다.
  - 집계, 모델 학습, 지표 계산은 `src/` 함수로 두고 pytest와 pyright가 검사한다. marimo 노트북은 그 함수를 불러 표와 그림을 보이고 판단을 적는다. 노트북 안에만 있는 계산은 두지 않는다(SPEC.md 15절).
- 근거: 사용자 지시(2026-11-23).
- 기각한 대안: marimo 노트북 자체를 재현 대상으로 두고 계산도 노트북에 두는 안. 노트북 코드는 테스트와 타입 검사가 약하고 SPEC.md 15절의 기준을 바꿔야 해서 뺐다.
- 승인: 2026-11-23

## 시각화는 seaborn으로 하고 스타일과 그림 유형은 anyplot을 참고한다

- 결정: 분석 그림은 seaborn으로 그린다. 스타일과 그림 유형은 https://anyplot.ai/plots?lib=seaborn 을 참고한다. 그리는 함수는 `src/uplift/plots.py`에 둔다.
- 근거: 사용자 지시(2026-11-23).
- 기각한 대안: plotly 같은 대화형 그림 라이브러리. 대화형 화면은 대시보드(SPEC.md 7절)가 맡고, 분석 산출물은 `artifacts/`에 저장할 정적 그림이면 된다.
- 승인: 2026-11-23

## 분석 데이터와 실험 기록은 DuckDB 파일 하나에 두고 이것을 정본으로 한다

- 결정:
  - 원본은 Parquet로 받고(SPEC.md 3절), 분석 테이블과 실험 기록은 DuckDB 파일 하나에 둔다. DB 서버는 두지 않는다. 테이블 구성은 `docs/DATA.md` "분석 데이터는 데이터 구조와 분석 목적에 따라 테이블로 나눈다" 절에 둔다.
  - 실행 스크립트가 설정, 지표, 예측을 DuckDB 테이블에 쓴다. 이것이 실험 기록의 정본이다. `experiment_id`는 실험 폴더 ID(`EXP-001`)이고, 같은 실험을 설정을 바꿔 다시 돌리면 실행마다 `run_id`가 새로 붙는다.
  - DuckDB 파일은 데이터라서 커밋하지 않는다. 채택한 실행은 지표(기준값 파일)와 예측을 `tests/baseline/`에 내보내 커밋한다. CI 회귀 테스트는 이 두 파일만 읽어 지표를 다시 계산하고 기준값과 비교한다(SPEC.md 9절).
  - 문서와 사이트가 인용하는 수치는 실행 스크립트가 DuckDB에서 `artifacts/<ID>/`로 내보낸 파일(`metrics.json` 등)을 근거로 단다. 내보낸 파일은 한 방향 사본이라 손으로 고치지 않는다. 평가 에이전트는 DuckDB를 읽지 못하고 이 파일은 읽을 수 있다.
- 근거: 사용자 지시(2026-11-23). 데이터는 고객 약 64,000명의 정적 데이터라(SPEC.md 2절) 동시 쓰기나 트랜잭션이 필요 없다.
- 기각한 대안: 실행마다 `results/<run_id>/` JSON을 정본으로 두고 DuckDB는 읽어 들이기만 하는 안. 같은 값이 파일과 테이블 두 곳에 생긴다.
- 승인: 2026-11-23

## 계산 코드, 실험, 분석, 산출물을 폴더로 나누고 ID로 잇는다

- 결정:

  ```
  src/uplift/          계산 코드 전부(데이터, DB, 학습기, 지표, 정책, 그림)
  experiments/         모델 실험. 설정을 바꿔 다시 돌려 비교하는 일
    EXP-001-<주제>/
      experiment.md    질문, 가설, 결과 해석
      config.yaml      pydantic으로 검증
      run.py           src 호출, DuckDB 기록, artifacts 내보내기만 함
  analyses/            marimo 분석. 한 번 보고 판단하는 일(EDA, 결정에 쓰는 분석)
    ANA-001-<주제>.py
  artifacts/           산출물. 코드와 나누고 폴더 이름은 ID만 씀
    EXP-001/           metrics.json, summary.md, figures/ 커밋. 예측 파일 커밋 안 함
    ANA-001/           figures/, tables/ 커밋. marimo HTML export 커밋 안 함
    data/              데이터 명세 요약(profile.json). 커밋함
  data/                커밋 안 함. raw/*.parquet, uplift.duckdb
  scripts/             데이터 받기와 체크섬(fetch_data.py), DuckDB 적재(build_db.py)
  tests/
    baseline/          채택한 실행의 기준값 파일과 예측. 커밋함
  ```

  - 실험 폴더 이름은 ID와 짧은 주제(`EXP-001-meta-learner-compare`)이고, 산출물 폴더 이름은 ID(`EXP-001`)만 쓴다.
  - 나중에 참고할 분석 결과(그림, 표, 지표 요약)는 `artifacts/<ID>/`에 저장해 커밋한다. marimo는 실행 결과를 파일에 남기지 않기 때문이다. marimo HTML export와 예측 파일처럼 크고 다시 만들 수 있는 것은 커밋하지 않는다.
  - `experiment.md`는 실험 하나의 기록이다. 결정의 정본은 분야 문서이고, 결정 절의 근거가 실험 ID와 `artifacts/<ID>/` 파일을 가리킨다.
- 근거: 사용자 지시(2026-11-23). SPEC.md 9절이 폴더 구조를 이 문서에 둔다.
- 기각한 대안: 산출물을 실험 폴더 안(`experiments/EXP-001/results/`)에 두는 안. 코드와 산출물이 섞이고 무시 규칙을 폴더마다 둬야 한다.
- 승인: 2026-11-23
