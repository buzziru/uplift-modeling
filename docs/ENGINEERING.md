# ENGINEERING.md: 엔지니어링

담는 범위: 저장 형식, 폴더 구조, 실험 기록 양식, 실행 환경, 테스트, 품질 도구, CI, 재현 허용 오차, 배포.

결정 당시 기록이며 지금 규칙과 다를 수 있다. 결정한 날짜순으로 항목을 둔다.

## 2026-11-22 실험 추적 서버는 두지 않고 DuckDB를 실험 기록의 정본으로 한다

- 결정: 추적 서버(MLflow 등)는 두지 않는다. 정본은 DuckDB이고, 채택한 실행의 지표를 기준값 파일로 고정한다.
- 근거: SPEC 작성 당시 사용자 결정(2026-11-22).
- 기각한 대안: MLflow 같은 추적 서버를 두는 안.
- 정본: 아직 없음. DuckDB 실행 기록은 `src/uplift/runs.py`에 반영했고, 기준값 파일은 `tests/baseline/`에 반영한다.
- 승인: 2026-11-22

## 2026-11-23 탐색과 결정에 쓰는 분석은 marimo 노트북에서 하고, 계산은 `src/`에 둔다

- 결정:
  - 탐색(EDA)과 결정에 쓰는 분석에는 Jupyter 대신 marimo 노트북(`.py`)을 쓴다. 노트북 작성은 `.claude/skills/marimo-notebook` 스킬을 따른다.
  - 집계, 모델 학습, 지표 계산은 `src/` 함수로 두고 pytest와 pyright가 검사한다. marimo 노트북은 그 함수를 불러 표와 그림을 보이고 판단을 적는다. 노트북 안에만 있는 계산은 두지 않는다.
- 근거: 사용자 지시(2026-11-23).
- 기각한 대안: marimo 노트북 자체를 재현 대상으로 두고 계산도 노트북에 두는 안. 노트북 코드는 테스트와 타입 검사가 약하고 SPEC.md의 기준을 바꿔야 해서 뺐다.
- 정본: `analyses/CLAUDE.md`
- 승인: 2026-11-23

## 2026-11-23 시각화는 seaborn으로 하고 스타일과 그림 유형은 anyplot을 참고한다

- 결정: 분석 그림은 seaborn으로 그린다. 스타일과 그림 유형은 https://anyplot.ai/plots?lib=seaborn 을 참고한다. 그리는 함수는 `src/uplift/plots.py`에 둔다.
- 근거: 사용자 지시(2026-11-23).
- 기각한 대안: plotly 같은 대화형 그림 라이브러리. 대화형 화면은 대시보드가 맡고, 분석 산출물은 `artifacts/`에 저장할 정적 그림이면 된다.
- 정본: `src/uplift/plots.py`, `analyses/CLAUDE.md`
- 승인: 2026-11-23

## 2026-11-23 분석 데이터와 실험 기록은 DuckDB 파일 하나에 두고 이것을 정본으로 한다

- 결정:
  - 원본은 Parquet로 받고, 분석 테이블과 실험 기록은 DuckDB 파일 하나에 둔다. DB 서버는 두지 않는다. 테이블 구성은 `docs/DATA.md`에 둔다.
  - 실행 스크립트가 설정, 지표, 예측을 DuckDB 테이블에 쓴다. 이것이 실험 기록의 정본이다. `experiment_id`는 실험 폴더 ID(`EXP-001`)이고, 같은 실험을 설정을 바꿔 다시 돌리면 실행마다 `run_id`가 새로 붙는다.
  - DuckDB 파일은 데이터라서 커밋하지 않는다. 채택한 실행은 지표(기준값 파일)와 예측을 `tests/baseline/`에 내보내 커밋한다. CI 회귀 테스트는 이 두 파일만 읽어 지표를 다시 계산하고 기준값과 비교한다.
  - 문서와 사이트가 인용하는 수치는 실행 스크립트가 DuckDB에서 `artifacts/<ID>/`로 내보낸 파일(`metrics.json` 등)이나 적재 때 만든 `artifacts/data/` 파일을 근거로 단다. 내보낸 파일은 한 방향 사본이라 손으로 고치지 않는다. 평가 에이전트는 DuckDB를 읽지 못하고 이 파일은 읽을 수 있다.
- 근거: 사용자 지시(2026-11-23). 데이터는 고객 약 64,000명의 정적 데이터라 동시 쓰기나 트랜잭션이 필요 없다.
- 기각한 대안: 실행마다 `results/<run_id>/` JSON을 정본으로 두고 DuckDB는 읽어 들이기만 하는 안. 같은 값이 파일과 테이블 두 곳에 생긴다.
- 정본: `scripts/CLAUDE.md`, `experiments/CLAUDE.md`
- 승인: 2026-11-23
- 바뀐 이력: 2026-11-26, "회귀 기준값과 CI 회귀 테스트는 M2 최종 모델에서 기준값 형식과 함께 정하고, EXP-001은 기준값을 만들지 않는다"로 바뀜

## 2026-11-23 계산 코드, 실험, 분석, 산출물을 폴더로 나누고 ID로 잇는다

- 결정:

  ```
  src/uplift/          계산 코드 전부(데이터, DB, 학습기, 지표, 정책, 그림)
  experiments/         모델 실험. 설정을 바꿔 다시 돌려 비교하는 일
    TEMPLATE.md        experiment.md 양식과 쓰는 법
    EXP-001-<주제>/
      experiment.md    질문, 설계, 계획, 결과 해석
      config.yaml      pydantic으로 검증
      run.py           src 호출, DuckDB 기록, artifacts 내보내기만 함(Kaggle 실행은 kaggle-remote-runner 스킬의 예외)
  analyses/            marimo 분석. 한 번 보고 판단하는 일(EDA, 결정에 쓰는 분석)
    ANA-001-<주제>.py
  artifacts/           산출물. 코드와 나누고 폴더 이름은 실험·분석 ID만 씀(data/ 예외)
    EXP-001/           metrics.json, summary.md, figures/ 커밋. 예측 파일 커밋 안 함
    ANA-001/           figures/, tables/, summary.md 커밋. marimo HTML export 커밋 안 함
    data/              적재 때 만든 명세 요약(profile.json)과 테이블 미리보기(tables.md). 커밋함
  data/                커밋 안 함. raw/*.parquet, uplift.duckdb
  scripts/             데이터 받기와 체크섬(fetch_data.py), DuckDB 적재와 분할(build_db.py, splits.yaml)
  tests/
    baseline/          채택한 실행의 기준값 파일과 예측. 커밋함
  ```

  - 실험 폴더 이름은 ID와 짧은 주제(`EXP-001-meta-learner-compare`)이고, 산출물 폴더 이름은 ID(`EXP-001`)만 쓴다. 실험·분석이 아닌 데이터 적재의 산출물은 `artifacts/data/`에 둔다.
  - DuckDB 파일은 텍스트 편집기에서 열리지 않으므로 두 가지로 본다. 적재 때 만드는 `artifacts/data/tables.md`를 열거나, `uv run marimo edit analyses/ANA-000-data-browse.py`로 테이블을 둘러보고 SQL을 돌린다.
  - 나중에 참고할 분석 결과(그림, 표, 지표 요약)는 `artifacts/<ID>/`에 저장해 커밋한다. marimo는 실행 결과를 파일에 남기지 않기 때문이다. marimo HTML export와 예측 파일처럼 크고 다시 만들 수 있는 것은 커밋하지 않는다.
  - `experiment.md`는 실험 하나의 기록이다. 결정의 정본은 코드와 설정이고, 기록 문서 항목의 근거가 실험 ID와 `artifacts/<ID>/` 파일을 가리킨다.
- 근거: 사용자 지시(2026-11-23).
- 기각한 대안: 산출물을 실험 폴더 안(`experiments/EXP-001/results/`)에 두는 안. 코드와 산출물이 섞이고 무시 규칙을 폴더마다 둬야 한다.
- 정본: `CLAUDE.md` 프로젝트 절
- 승인: 2026-11-23
- 바뀐 이력:
  - 2026-11-24: 결정의 정본을 분야 문서에서 코드와 설정으로 옮겼다(아래 2026-11-24 기록 문서 항목). 분석 산출물에 `summary.md`를 더했다.
  - 2026-11-26, "실험 run.py는 compute와 export 하위 명령으로 나누고, artifacts/<ID>/는 export로만 만든다"로 바뀜
  - 2026-11-26, "회귀 기준값과 CI 회귀 테스트는 M2 최종 모델에서 기준값 형식과 함께 정하고, EXP-001은 기준값을 만들지 않는다"로 바뀜

## 2026-11-24 결정에 쓰는 실험과 분석은 판정 규칙을 결과보다 먼저 적는 양식을 따른다

- 결정:
  - `experiment.md`는 `experiments/TEMPLATE.md` 양식(질문, 설계, 계획, 결과 해석)으로 쓰고, 질문과 설계 절을 결과보다 먼저 커밋한다.
  - 결정에 쓰는 ANA 노트북은 첫 마크다운 셀에 그 양식의 질문 절과 "이미 본 것"을 둔다. 결과를 아직 보지 않았으면 판정 규칙도 둔다.
- 근거: 사용자 지시(2026-11-24). 결과를 본 뒤 지표나 판정 기준을 고르면 우연한 차이를 효과로 보고하게 된다. 판정 규칙을 먼저 커밋하면 그 순서를 git 이력으로 확인할 수 있다.
- 기각한 대안: 작업마다 별도 폴더에 intent, spec, plan 문서를 두는 안. 채택한 결정이 그 문서와 분야 문서 두 곳에 남는다. ANA 노트북에도 네 절을 모두 두는 안. 한 번 보고 판단하는 분석에는 쓰는 곳이 없는 절이 많다.
- 정본: `experiments/TEMPLATE.md`, `analyses/CLAUDE.md`
- 승인: 2026-11-24

## 2026-11-24 본학습, HPO, GPU 실행은 Kaggle kernel에서 하고 나머지는 로컬에서 한다

- 결정:
  - 로컬: 작은 실험과 디버깅, EDA, 데이터 검증, feature engineering, 모델 평가와 분석. 시험 세트 평가도 로컬에서 한다.
  - Kaggle: 모델의 본학습과 HPO는 모두 Kaggle kernel에서 돌린다. 기본은 CPU kernel이고, LightGBM이 여기에 든다. XGBoost, CatBoost처럼 GPU로 학습 시간이 줄어드는 모델만 GPU kernel을 쓴다. 절차는 `.claude/skills/kaggle-remote-runner/SKILL.md`.
  - Kaggle에는 학습 세트와 `folds`만 비공개 dataset으로 올리고 시험 세트는 올리지 않는다. 원격 HPO가 시험 세트를 읽을 수 없게 하기 위해서다.
  - kernel은 GitHub에 푸시한 커밋을 받아 `uv.lock`대로 환경을 만들어 돈다. Kaggle에는 DuckDB 파일이 없으므로 `run.py`가 DuckDB 대신 출력 폴더에 쓰고, 받아 온 출력을 로컬 스크립트가 DuckDB에 실행으로 적는다. 출력 형식과 그 스크립트는 첫 Kaggle 실험(M2)에서 정해 kaggle-remote-runner 스킬과 `experiments/CLAUDE.md`에 적는다.
- 근거: 사용자 지시(2026-11-24). 로컬의 메모리와 CPU가 학습과 HPO를 감당하기에 부족하다. LightGBM은 GPU로 얻는 시간 이득이 작다.
- 기각한 대안: Colab. 실행을 명령줄에서 올리고 상태와 출력을 받는 공식 CLI를 확인하지 못해, 로컬 스크립트로 실행을 묶기 어렵다. Kaggle CLI는 kernel push, status, logs, output을 제공한다. 로컬 실행 시간(30분)으로 로컬과 Kaggle을 가르는 안. 로컬 자원이 부족해 짧은 학습도 다른 작업을 막는다.
- 정본: `.claude/skills/kaggle-remote-runner/SKILL.md`
- 승인: 2026-11-24
- 바뀐 이력: 2026-11-26, "Kaggle 실행은 scripts/kaggle.py가 맡고, kernel의 compute 기록을 로컬 DuckDB에 합친다"로 바뀜

## 2026-11-24 결정의 정본은 코드, 설정, 폴더 규약에 두고, docs/의 분야 문서는 기여 기록으로 쓴다

- 결정:
  - 결정은 그것이 반영된 코드, 설정, 테스트가 정본이다. 작업 규약은 폴더의 `CLAUDE.md`와 스킬이 정본이다. 코드가 아직 없는 결정만 임시 결정 파일에 두고, 반영하면 행을 지운다.
  - 분야 문서는 기록 문서로 바꿨다. 결정한 시점의 결정, 근거, 기각한 대안, 정본 위치를 날짜와 함께 남긴다. 틀린 내용은 제자리에서 고치고, 결정이 바뀌면 바뀐 이력에 한 줄을 더한다.
  - `docs/` 밖의 파일은 기록 문서의 절을 인용하지 않는다. `.claude/harness/check_docs.py`가 막는다.
- 근거: 사용자 지시(2026-11-24). M1 브랜치(PR #9)에서 평가 지적 16건 중 9건이 문서 간 정합(루브릭 R8)이었다(`_workspace/findings/feat/m1-experiment-understanding/`). 분야 문서를 `SPEC.md`, `src/` docstring, 분석, 스킬 등 파일 11곳이 절 제목으로 인용해, 결정이 바뀔 때마다 인용한 곳이 어긋났다. 이전에 `docs/decisions/`를 폐기한 이유와 같은 일이 분야 문서에서 되풀이됐다.
- 기각한 대안: 결정 절마다 고정 ID를 두고 ID로 인용하는 안. 제목이 바뀌어도 참조는 깨지지 않지만, 인용한 절의 내용이 바뀌면 인용한 쪽의 뜻이 여전히 어긋난다. 기록에서 옛 항목을 고치지 않고 덧쓰기만 하는 안. 인용을 막으면 제자리 수정이 다른 곳을 어긋나게 하지 않으므로 필요 없고, 문서만 길어진다.
- 정본: `SPEC.md` 문서 체계 절, `.claude/harness/check_docs.py`, `docs/CLAUDE.md`
- 바뀐 이력: 2026-11-25, "문서는 층마다 한 가지만 담고, 정본이 아직 없는 결정은 기록 문서 정본 칸의 "아직 없음"으로 둔다" 항목으로 바뀜

## 2026-11-25 문서는 층마다 한 가지만 담고, 정본이 아직 없는 결정은 기록 문서 정본 칸의 "아직 없음"으로 둔다

- 결정: SPEC.md 문서 체계 절의 표대로 정본, 명세, 기록 문서, 이론, 용어집, 단계 계획이 담는 것을 나누고, `PENDING-DECISIONS.md`를 없앤다. 정본이 아직 없는 결정은 기록 문서 항목의 정본 칸에 "아직 없음"과 반영할 곳을 적는다.
- 근거: 사용자 승인(2026-11-25). 평가 지적 96건 가운데 약 40%가 가리킨 곳 불일치, 사본, 같은 대상을 다르게 적기였다. 같은 결정이 SPEC, PENDING, 기록 문서, 용어집, 단계 계획에 겹쳐 결정이 바뀔 때마다 여러 곳을 고쳤고, 장치를 더할 때마다 사본이 검사 밖의 새 층으로 옮겨 갔다.
- 기각한 대안: PENDING을 두고 기록 문서 항목을 가리키게 하는 안. 기록 문서 인용이 늘고, 행과 항목이 다시 어긋날 수 있다. PENDING을 두고 기록 문서와의 동기화를 검사하는 안. 같은 결정 두 벌이 그대로 남아 검사와 수정 부담이 계속된다.
- 정본: `docs/CLAUDE.md` 문서 체계 절, `.claude/harness/check_docs.py`(--pending, 사본·인용 검사)
- 승인: 2026-11-25
- 바뀐 이력: 2026-11-25, "SPEC은 시작 명세로 고정하고, 지금 계획은 docs/plans/로 옮긴다" 항목으로 바뀜

## 2026-11-25 SPEC은 시작 명세로 고정하고, 지금 계획은 docs/plans/로 옮긴다

- 결정: `SPEC.md`는 프로젝트를 시작할 때 정한 요구 사항과 계획으로 고정하고 고치지 않는다. 지금의 마일스톤, 단계별 범위, 완료 기준, 미결 사항은 `docs/plans/ROADMAP.md`에 두고, 문서 체계 표는 `docs/CLAUDE.md`로 옮긴다. 다른 파일은 SPEC과 맞추지 않는다.
- 근거: 사용자 지시(2026-11-25). "SPEC은 grill-me로 시작 시 작성한 기초 문서이고 분석 과정에서 변할 수 있다. 처음 계획에서 무엇이 달라졌는지 비교하는 자료로 가치가 있다. 그런데 지금 spec은 앞으로의 계획까지 포함한 프로젝트 전체 기준 문서가 되었고 모든 곳에서 spec과의 정합을 맞추려고 하고 있다." 바꾸는 앞 항목: "문서는 층마다 한 가지만 담고, 정본이 아직 없는 결정은 기록 문서 정본 칸의 "아직 없음"으로 둔다".
- 기각한 대안: SPEC을 목적, 범위, 승인 지점, 마일스톤, 완료 기준 문서로 줄여 계속 고치는 안(같은 날 앞서 승인했던 안). 계획이 바뀔 때마다 SPEC과 다른 문서를 맞추는 일이 남는다.
- 정본: `SPEC.md` 머리말, `docs/CLAUDE.md` 문서 체계 절
- 승인: 2026-11-25

## 2026-11-25 기록 문서 사이의 충돌은 PR 검토에서 보지 않고 단계의 구현 계획을 세울 때 본다

- 결정: 기록 문서 항목끼리의 충돌은 PR 검토에서 보지 않는다. 단계의 구현 계획을 세울 때 그 단계에서 반영할 기록 항목을 모으고, 같은 곳에 반영할 항목끼리 충돌하면 각 결정이 쓰인 맥락, 선택지의 장단, 효과와 비용을 검토해 정한다. 사용자 승인 지점이면 묻는다.
- 근거: 사용자 지시(2026-11-25). "결정은 실제 구현이 될 때 의미가 생긴다. 마일스톤의 계획들은 앞단계 진행과정에서 수차례 변경될 수 있다. 구현 계획 단계에서 충돌을 발견했을 땐 각 결정이 어떤 맥락에서 쓰였는지, 선택지의 장단, 효과와 비용이 무엇인지를 검토해서 정한다."
- 기각한 대안: 기록 항목을 더하거나 고치는 PR마다 검토가 같은 대상의 다른 항목과 비교하는 안. 기록을 고칠 때마다 다른 기록과 맞추는 연쇄가 되살아나고, 지적을 피하려 옛 항목을 고치는 행동이 생길 수 있다. 아무도 보지 않는 안. 충돌한 채 구현될 수 있다.
- 정본: `docs/CLAUDE.md` 단계 계획 절, `.claude/harness/check_docs.py`의 --pending, PR 검토 지시문(`.claude/agents/pr-reviewer.md`)
- 승인: 2026-11-25

## 2026-11-26 실험 run.py는 compute와 export 하위 명령으로 나누고, artifacts/<ID>/는 export로만 만든다

- 결정: `run.py`는 `compute`와 `export <run_id>`를 둔다. `compute`는 계산 결과(설정, 지표, 예측, 결과 표)를 DuckDB에 쓰고, `export`는 DuckDB에서 읽어 `artifacts/<ID>/`의 `tables/`, `figures/`, `metrics.json`을 만든다. `artifacts/<ID>/`에서 `summary.md` 말고는 `export`로만 만든다.
- 근거: 사용자 지적(2026-11-26). EXP-001은 채택한 실행 말고도 같은 설정으로 전체 실행을 세 번 더 돌렸고, 모두 같은 판정을 냈다(`experiments/EXP-001-comparison-policies/experiment.md` 결과 해석 절의 설계와 달라진 점). 그중 한 번은 판정 수치를 표로 내려고 다시 돌린 것인데, 계산과 내보내기가 한 실행에 묶여 표 하나를 더하는 데도 전체를 다시 계산했다. 바꾸는 앞 항목: "계산 코드, 실험, 분석, 산출물을 폴더로 나누고 ID로 잇는다".
- 기각한 대안: `run.py` 한 실행이 계산과 `artifacts/` 내보내기를 함께 하는 앞 구조. 표나 그림 하나를 더하려 해도 전체 계산을 다시 돌려야 한다.
- 정본: `experiments/EXP-001-comparison-policies/run.py`, `src/uplift/runs.py`(`record_table`, `load_table`), `experiments/CLAUDE.md`, `CLAUDE.md` 폴더 구조

## 2026-11-26 compute는 src/와 실험 폴더에 커밋하지 않은 변경이 있으면 멈춘다

- 결정: `compute`는 시작 전에 `src/`와 실험 폴더에 커밋하지 않은 변경이 있으면 멈춘다.
- 근거: 사용자 지적(2026-11-26). EXP-001의 다시 돌린 실행 가운데 첫 번째는 커밋 전 코드로 돌아(`experiments/EXP-001-comparison-policies/experiment.md` 결과 해석 절의 설계와 달라진 점), DuckDB에 적힌 커밋 해시가 실행한 코드와 맞지 않았다.
- 기각한 대안: 커밋 해시만 기록하고 실행은 막지 않는 앞 방식. 커밋하지 않은 변경으로 돈 실행도 그 해시로 기록되어, 기록만 보고는 실행한 코드를 되살릴 수 없다.
- 정본: `src/uplift/runs.py`(`require_clean`), `experiments/CLAUDE.md`

## 2026-11-26 정식 compute 전에 smoke로 학습 세트 표본에서 파이프라인을 확인한다

- 결정: 정식 `compute` 전에 `smoke <폴더>`로 학습 세트 표본에서 파이프라인과 내보낼 파일을 확인한다. smoke 결과는 저장소 밖 임시 폴더에 쓰고 DuckDB 파일에는 쓰지 않는다.
- 근거: 사용자 지적(2026-11-26). EXP-001에는 작은 표본으로 파이프라인을 확인할 수단이 없어 첫 확인 실행이 그대로 정식 기록이 되었다.
- 기각한 대안: 정식 실행으로 바로 확인하는 앞 방식. 확인 중에 고칠 것이 나오면 정식 기록이 될 전체 실행을 다시 돌려야 한다.
- 정본: `experiments/EXP-001-comparison-policies/run.py`, `experiments/CLAUDE.md`, `experiments/TEMPLATE.md`

## 2026-11-26 summary.md가 인용할 수치는 tables/에 낸다

- 결정: `summary.md`가 인용할 수치는 `export`가 `tables/`에 낸다. 실험 계획 절의 산출물 줄에 그 수치가 든 표를 모두 적는다.
- 근거: 사용자 지적(2026-11-26). EXP-001에서 `summary.md` 수치 검사가 `tables/`만 대조한다는 것을 실행 뒤에 알아, 판정 수치를 표로 내려고 전체 실행을 다시 돌렸다(`experiments/EXP-001-comparison-policies/experiment.md` 결과 해석 절의 설계와 달라진 점).
- 기각한 대안: 판정 수치를 `metrics.json`에만 두는 안. `summary.md` 수치 검사가 `metrics.json`을 대조하지 않아 그 수치는 근거 파일과 맞는지 확인되지 않는다.
- 정본: `experiments/CLAUDE.md`, `experiments/TEMPLATE.md`

## 2026-11-26 회귀 기준값과 CI 회귀 테스트는 M2 최종 모델에서 기준값 형식과 함께 정하고, EXP-001은 기준값을 만들지 않는다

- 결정: EXP-001은 `tests/baseline/` 기준값을 만들지 않는다. 기준값과 CI 회귀 테스트는 M2 최종 모델을 채택할 때, 기준값 파일의 형식(고객별 처치와 결과를 어떻게 다룰지)과 함께 정한다.
- 근거: 사용자 결정(2026-11-26). CI가 정책 가치를 다시 계산하려면 예측 말고 고객별 처치와 `visit`이 필요해, 커밋하지 않기로 한 원본 데이터의 일부를 커밋하게 된다. 바꾸는 앞 항목: "분석 데이터와 실험 기록은 DuckDB 파일 하나에 두고 이것을 정본으로 한다", "계산 코드, 실험, 분석, 산출물을 폴더로 나누고 ID로 잇는다".
- 기각한 대안: 앞 규약대로 EXP-001 실행을 채택해 지표와 예측을 `tests/baseline/`에 커밋하는 안. 예측만으로는 CI가 정책 가치를 다시 계산할 수 없고, 계산하게 하려면 고객별 처치와 `visit`을 함께 커밋해야 한다.
- 정본: `tests/CLAUDE.md` 테스트 도입 순서, `experiments/CLAUDE.md`
- 승인: 2026-11-26

## 2026-11-26 Kaggle 실행은 scripts/kaggle.py가 맡고, kernel의 compute 기록을 로컬 DuckDB에 합친다

- 결정:
  - `scripts/kaggle.py`가 학습 세트 dataset 올리기, kernel 만들기와 push, 상태 보기, 출력 받기를 맡는다. dataset에는 데이터 파일 해시(manifest)를 넣고 kernel이 시작할 때 대조한다.
  - kernel은 로컬과 같은 `run.py compute`를 `--data`(dataset)와 `--db`(kernel 출력 폴더의 DuckDB 파일)로 돈다. `pull`이 받은 DuckDB 파일의 실행 기록을 메인 DuckDB에 합친다. smoke 실행은 합치지 않는다.
  - 실험 `config.yaml`의 `run_on`이 `kaggle`이면 로컬 compute를 멈춘다.
- 근거: 메인 결정(2026-11-26). 2026-11-24 Kaggle 항목이 첫 Kaggle 실험(M2)으로 미룬 출력 형식과 합치는 스크립트를 정한다. Kaggle에서도 DuckDB 파일에 쓰면 로컬과 같은 기록 코드를 쓰고, 합칠 때 표를 그대로 옮긴다. EXP-002의 kernel 여덟 개를 이렇게 돌려 합쳤다.
- 기각한 대안: `run.py`가 Kaggle에서 출력 폴더에 따로 쓰고 로컬 스크립트가 DuckDB에 다시 적는 안(2026-11-24 항목의 계획). 기록 형식이 두 벌이 된다.
- 정본: `scripts/kaggle.py`, `src/uplift/kaggle_jobs.py`, `src/uplift/runs.py`(`merge_records`), `experiments/CLAUDE.md`
- 승인: 메인 결정이라 승인 대상이 아니다.
