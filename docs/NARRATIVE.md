# NARRATIVE.md: 성과 정리

담는 범위: 사이트 항목 초안, 성과 문장, 한계, 배운 점.

기록 문서다(SPEC.md 10절). 결정한 날짜순으로 항목을 둔다.


## M0 기반: 원본 64,000행을 체크섬으로 고정하고 DuckDB 네 테이블로 나눠 처음부터 다시 만들 수 있게 했다

- 주장 문장: 원 출처 CSV를 해시로 고정하고 고객 특성, 처치, 배정, 결과 네 테이블로 나눠, 명령 두 줄(`scripts/fetch_data.py`, `scripts/build_db.py`)로 같은 분석 데이터를 다시 만들 수 있게 했다.
- 근거 수치: 원본 전체 64,000행, 처치 세 그룹 No E-Mail 21,306명, Mens E-Mail 21,307명, Womens E-Mail 21,387명, 고객 특성 결측 0. 결과 파일 `artifacts/data/profile.json`.
- 그림 값: 처치 그룹별 visit 비율 No E-Mail 0.1062, Mens E-Mail 0.1828, Womens E-Mail 0.1514(`artifacts/data/profile.json`의 `by_treatment`). 그룹 간 차이의 95% 구간은 M1 절.
- 사이트 문장 승인: M5(SPEC.md 11절).

## M1 실험 이해: 무작위 배정이 성립해 보정 없이 효과를 잴 수 있고, 메일로 늘어난 방문은 평소 방문보다 구매로 자주 이어진다

- 주장 문장: 세 군의 크기와 공변량·범주 18개의 균형을 세 비교로 확인해, 보정 없이 평균 차이로 효과를 잴 수 있음을 보였다. 남성용 메일은 방문을 7.7%p 늘렸고, 늘어난 방문은 평소 방문보다 1.6배 자주 구매로 이어졌다.
- 근거 수치: SRM p = 0.904(`artifacts/ANA-001/tables/srm.json`). SMD 54개의 |SMD| 최댓값 0.0164(`artifacts/ANA-001/tables/smd.csv`). 남성용 메일 `visit` 효과 0.0766(95% 구간 0.0700\~0.0832), 여성용 0.0452(0.0389\~0.0516)(`artifacts/ANA-001/tables/ate.csv`, 분할 전 전체 64,000행). 늘어난 방문 1회당 구매 0.0889(남성용), 대조군 방문 1회당 구매 0.0539(`artifacts/ANA-001/tables/funnel.csv`).
- 그림 값: 공변량별 |SMD|와 기준선 0.1(`artifacts/ANA-001/figures/smd.png`). 처치별 세 결과의 효과와 95% 구간(`ate.csv`의 `effect`, `ci_low`, `ci_high`).
- 사이트 문장 승인: M5(SPEC.md 11절).
