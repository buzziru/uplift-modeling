# analyses 규약

- 탐색(EDA)과 결정에 쓰는 분석은 marimo 노트북(`.py`)으로 쓴다. 작성은 `.claude/skills/marimo-notebook` 스킬을 따른다. 이름은 `ANA-<번호>-<주제>.py`다.
- 집계, 모델 학습, 지표 계산은 `src/` 함수로 두고 pytest와 pyright가 검사한다. 노트북은 그 함수를 불러 표와 그림을 보이고 판단을 적는다. 노트북 안에만 있는 계산은 두지 않는다.
- 그림은 seaborn으로 그리고, 그리는 함수는 `src/uplift/plots.py`에 둔다. 스타일과 그림 유형은 https://anyplot.ai/plots?lib=seaborn 을 참고한다.
- 결정에 쓰는 노트북은 첫 마크다운 셀에 `experiments/TEMPLATE.md`의 질문 절과 "이미 본 것"을 둔다. 결과를 아직 보지 않았으면 판정 규칙도 둔다.
- 분석(ANA)은 `artifacts/<ID>/`에 `figures/`, `tables/`와 함께 `summary.md`를 둔다. 절 제목에 그 절의 결론을 쓰고, 수치마다 같은 폴더의 결과 파일을 가리킨다. `docs/`는 인용하지 않는다.
- marimo HTML export는 커밋하지 않는다.
