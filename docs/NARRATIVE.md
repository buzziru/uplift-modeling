# NARRATIVE.md: 성과 정리

담는 범위: 사이트 항목 초안, 성과 문장, 한계, 배운 점.

지금 유효한 결정만 둔다. 결정마다 아래 절을 하나씩 만든다. 바뀐 이력은 git 커밋에 남긴다.

<!--
## <결정 제목: 결정 내용을 한 문장으로>

- 결정:
- 근거: 수치와 결과 파일 경로
- 기각한 대안: 대안과 기각 이유
-->

## M0 기반: 원본 64,000행을 체크섬으로 고정하고 DuckDB 네 테이블로 나눠 처음부터 다시 만들 수 있게 했다

- 주장 문장: 원 출처 CSV를 해시로 고정하고 고객 특성, 처치, 배정, 결과 네 테이블로 나눠, 명령 두 줄(`scripts/fetch_data.py`, `scripts/build_db.py`)로 같은 분석 데이터를 다시 만들 수 있게 했다.
- 근거 수치: 원본 전체 64,000행, 처치 세 그룹 No E-Mail 21,306명, Mens E-Mail 21,307명, Womens E-Mail 21,387명, 고객 특성 결측 0. 결과 파일 `artifacts/data/profile.json`.
- 그림 값: 처치 그룹별 visit 비율 No E-Mail 0.1062, Mens E-Mail 0.1828, Womens E-Mail 0.1514(`artifacts/data/profile.json`의 `by_treatment`). 그룹 간 차이의 95% 구간은 M1에서 더한다.
- 사이트 문장 승인: M5(SPEC.md 11절).
