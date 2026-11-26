---
name: run-analysis
description: 분석(ANA) 노트북을 시작하고, 분석 단위를 더하고, summary.md를 쓰고, 마무리하는 순서. analyses/에 새 노트북을 만들 때, 노트북에 분석 셀을 더할 때, artifacts/<ID>/summary.md를 쓰거나 고칠 때 쓴다. marimo 문법은 marimo-notebook 스킬이 맡는다.
---

# 분석(ANA) 절차

1. 시작: ID, 첫 셀, 머리 셀, 결과를 보기 전 커밋
2. 분석 단위: src 함수와 테스트, 노트북 호출, 내보내기, mo.md
3. summary.md: tables/ 파일을 보며 쓰기, 절 제목, 수치마다 경로
4. 마무리: 처음부터 다시 실행, 수치 검사

노트북 셀을 쓰기 전에 marimo-notebook 스킬을 불러 온다.

## 1. 시작

1. ID를 정한다. `analyses/`와 `artifacts/`의 가장 큰 ANA 번호에 1을 더한다. 노트북 이름은 `analyses/CLAUDE.md`를 따르고, 산출물 폴더는 `artifacts/<ID>/`다.
2. 첫 셀에서 import, `uplift.db.load_frame`으로 분할 읽기, `out = root / "artifacts" / "<ID>"`와 `out / "tables"`, `out / "figures"` 만들기를 한다. 다른 셀은 `out`만 받아 쓴다.
3. 결정에 쓰는 노트북은 머리 셀(첫 마크다운 셀)에 질문을 `experiments/TEMPLATE.md` 질문 절의 꼴로 쓰고, 이미 본 것을 둔다. 결과를 아직 보지 않았으면 판정 규칙도 둔다.
4. 결과를 보기 전에 첫 셀과 머리 셀을 커밋한다.

## 2. 분석 단위

분석 단위는 표나 그림 하나와 그 결론이다. 단위마다 아래 순서를 지킨다.

1. 집계, 통계, 지표는 `src/uplift/` 함수로 쓰고 `tests/`에 테스트를 더한다.
2. 노트북 셀은 그 함수를 부르기만 한다. 셀 안에서 행 수 세기, 최댓값 고르기, 비율 나누기 같은 새 계산을 하지 않는다. 필요하면 1로 돌아가 함수에 넣는다.
3. 산출물을 만드는 값은 위젯 입력에 기대지 않는다. 위젯은 탐색용으로만 쓰고, 산출물에 쓸 값은 셀에 상수로 둔다. marimo-notebook 스킬은 스크립트 모드에서 위젯 대신 기본값이나 예시 데이터를 쓰게 하는데, 4단계는 스크립트 모드로 산출물을 다시 만들기 때문이다.
4. 결과를 `out / "tables" / "<이름>.csv"`(또는 `.json`)와 `out / "figures" / "<이름>.png"`로 내보낸다.
5. 셀의 `mo.md`는 내보낸 표에 있는 값만 쓰고, 제목에 그 단위의 결론을 결론 문장 규칙대로 쓴다.

## 3. summary.md

`artifacts/<ID>/summary.md`는 노트북 화면이 아니라 `tables/` 파일을 열어 보며 쓴다. 화면의 표는 반올림과 필터가 내보낸 파일과 다를 수 있다.

1. 머리에 노트북 경로와 데이터 범위(분할, 행 수)를 적는다.
2. 절마다 결론 하나를 두고, 절 제목에 그 결론을 쓴다.
3. 수치마다 같은 폴더의 결과 파일 경로(`tables/<이름>.csv`, `figures/<이름>.png`)를 붙인다. 표에 없는 값(배수, 차이, 합)이 필요하면 2단계로 돌아가 함수와 표에 넣는다.
4. `docs/`는 인용하지 않는다.

### 결론 문장 규칙

노트북의 `mo.md`와 summary.md에 함께 쓴다.

- 결론 문장과 절 제목에는 그 결론이 걸린 결과 변수(`visit`, `spend` 등)를 적는다.
- 한 결과 변수에서 나온 결론을 다른 결과 변수나 다른 세그먼트까지 넓혀 쓰지 않는다.
- "~에게만 듣는다"처럼 범위를 닫는 말은 다른 세그먼트의 구간이 0을 포함할 때만 쓴다.

## 4. 마무리

1. 커밋 전에 노트북을 처음부터 다시 실행해(`uv run python analyses/<ID>-<주제>.py`) `tables/`와 `figures/`를 다시 만든다. 편집 중에는 `pyproject.toml`의 `auto_reload = "lazy"`가 바뀐 `src/` 모듈을 쓰는 셀을 stale로 표시만 하고 다시 실행하지 않아, 편집기 화면과 내보낸 파일이 옛 결과로 남을 수 있다. 커밋하는 산출물은 처음부터 실행한 결과를 기준으로 한다. `git diff`로 내보낸 파일이 바뀌었으면 summary.md의 수치를 다시 맞춘다.
2. 다시 실행이 오래 걸리면 무거운 계산을 EXP(`experiments/`의 `run.py`)로 옮기는 것을 먼저 검토한다. ANA에 남겨야 하면 그 계산만 `mo.persistent_cache`로 캐시한다. 몇 분부터 오래 걸린다고 볼지는 병목인 분석이 처음 생길 때 정한다. 캐시에는 아래 외부 제약이 있다(marimo 문서 https://docs.marimo.io/api/caching/ Limitations).
   - 캐시 키에 import한 모듈의 소스 코드가 들어가지 않는다. 캐시 블록이 쓰는 `src/` 함수를 고치면 캐시 이름을 바꿔 무효화한다.
   - 캐시가 맞으면(cache hit) 블록 안의 부수 효과(파일 쓰기 등)가 실행되지 않는다. `tables/`·`figures/` 내보내기는 캐시 블록 밖에 둔다.
3. `uv run python .claude/harness/check_docs.py --summary artifacts/<ID>/summary.md`를 돌린다. 오류에 나온 수치는 표에 넣거나 경로를 고친다. 소수점이 없는 수(문턱, 설정값, 행 수, 개수)는 대조하지 않는다.
