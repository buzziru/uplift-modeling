<!-- solo-harness:start -->
## 하네스

- 메인이 직접 일한다. 기획·작성·수정을 에이전트로 나누지 않는다.
- 에이전트는 조사, 병렬, 분리된 검증, 권한 분리에만 쓴다.
- 위임하는 동안 결과에 기대지 않는 일을 하고, 결과는 단위별로 오는 대로 처리한다.
- 나눌 일이 worker보다 많으면 고정으로 나누지 않고, 끝난 worker가 다음 일을 가져간다.
- 같은 지시를 두 번 받으면 스킬이나 규칙 후보로 기록한다.
- 사용자가 고쳐 준 것은 그 자리에서 세션 맥락에 안내된 `record.mjs observe --source conversation`으로 남긴다.
- 새 종류의 산출물은 앞부분을 먼저 보이고 피드백을 받은 뒤 나머지를 만든다.
- 평가 대상 파일(`run-evaluation` 스킬에 정의)을 바꾼 작업은 평가를, 모든 작업은 PR 전 검토(`pr-reviewer`)를 `run-evaluation` 스킬대로 받는다.
- 작은 수정과 결정은 작업 트리나 진행 중인 브랜치에 모으고, 브랜치를 새로 만들거나 PR을 열기 전에 묶을 범위를 사용자와 정한다. 하네스 파일(범위는 아래 변경 이력 줄) 수정은 작업 변경과 다른 브랜치에 모은다. `experiments/`의 실험 폴더 하나는 묻지 않고 PR 하나로 한다.
- 되돌리기 어려운 대상은 명령을 막는 대신 대상 쪽(보호 설정, 복구 수단, 보관 위치)에서 지킨다. main은 GitHub branch protection, 프로덕션 배포는 Vercel Git 연동(main 병합 때만), 원본 데이터는 받는 스크립트와 체크섬, 비밀 값(API 키)은 저장소 밖 Doppler에 두고 실행할 때 주입한다.
- 거부 규칙은 흔한 명령 꼴만 막는 첫 방어선이다. 같은 동작의 다른 명령 꼴을 찾아 규칙을 더하지 않는다.
- 정본(SPEC.md 10절)과 SPEC.md의 내용을 하네스 파일에 옮겨 적지 않고 위치로 가리킨다.
- 규칙을 새로 쓰거나 바꾸기 전에 같은 대상을 정하는 정본과 하네스 파일(범위는 아래 변경 이력 줄)을 먼저 읽는다. 용어나 규칙 표현을 바꾸면 바뀌기 전 표현을 저장소에서 검색해 남은 곳을 같은 커밋에서 고친다.
- 이미 정의된 용어를 새 문장에 쓰면 정의를 가리킨다. 괄호로 다시 나열하거나 다른 말로 바꾸지 않는다.
- 하네스 파일(이 절, `.claude/skills/`, `.claude/rules/`, `.claude/agents/`, `.claude/rubrics/`, 거부 규칙, `.claude/harness/config.json`)을 바꾸면 `.claude/harness/CHANGELOG.md`에 행을 더한다. 같은 브랜치에서 이미 행을 더했으면 solo-harness `docs/formats.md` 4절을 따른다.

### 승인 지점

- 사용자에게 묻는다: SPEC.md 11절의 승인 지점, 시험 세트 사용, 공개 배포, 저장소 공개 설정 변경, 해석이 갈리는 지시. 승인 요청에는 선택지별 개념 설명, 근거 수치, 추천안을 붙인다.
- 메인이 정하고 보고에 한 줄로 적는다: SPEC.md 11절 끝 문단의 항목, 폴더 구조, 앞 결정의 의도가 덮는 새 사례, 저장소를 읽으면 닫히는 질문. 정한 것은 정본에 반영하고 해당 기록 문서에 항목을 남긴다.

<!-- solo-harness:end -->

## 프로젝트

- 명세는 `SPEC.md`, 용어는 `docs/glossary.md`다. 결정의 정본과 기록 문서의 구분은 SPEC.md 10절이다.
- 정했지만 코드로 옮기지 못한 결정은 `PENDING-DECISIONS.md`에 둔다.
- `docs/` 문서에서 바뀐 이력 줄이 문서 전체 줄의 20%를 넘으면, 그 문서의 바뀐 이력을 `docs/history/<문서 이름>.md`로 옮기고 각 항목에는 옮긴 곳을 한 줄로 남긴다. `check_docs.py`가 비율을 재어 넘으면 알린다.
- 폴더 규약은 `analyses/CLAUDE.md`, `experiments/CLAUDE.md`, `scripts/CLAUDE.md`, 실험 양식은 `experiments/TEMPLATE.md`, Kaggle 실행은 `.claude/skills/kaggle-remote-runner/SKILL.md`다.

### 폴더 구조

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

- 실험 폴더 이름은 ID와 짧은 주제(`EXP-001-meta-learner-compare`)이고, 산출물 폴더 이름은 ID(`EXP-001`)만 쓴다.
- DuckDB 파일은 `artifacts/data/tables.md`를 열거나 `uv run marimo edit analyses/ANA-000-data-browse.py`로 본다.
- 나중에 참고할 결과(그림, 표, 요약)는 `artifacts/<ID>/`에 저장해 커밋한다. marimo는 실행 결과를 파일에 남기지 않기 때문이다. 크고 다시 만들 수 있는 파일(marimo HTML export, 예측)은 커밋하지 않는다.
