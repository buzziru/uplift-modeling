# M2 계획: 모델링

작업 분해는 2026-11-25 사용자 동의. 순서는 앞 단위가 끝나야 열리는 조건을 따른다. 시험 세트는 M2에서 쓰지 않는다. 단위가 끝나면 그 행에 PR 번호를 적는다.

## 작업 분해

| 단위 | 내용 | 앞에 필요한 것 | PR |
| --- | --- | --- | --- |
| U1 ANA-002, ANA-003 | ANA-002 분포 EDA(공변량·결과 분포와 변수별 해석, 상관, 군별 분포와 구매 고객 1명당 금액 구간). ANA-003 고객 세그먼트와 메일 반응(구매 상품·지역·채널 교차 구성, 대조군의 세그먼트별 행동, 세그먼트별 효과와 퍼널 분해 가정 확인, 담당자 질문). 2026-11-25 분리. 학습 세트만. 비교 정책 정의를 PROBLEM.md에 반영 | 없음 | PR-A |
| U2 평가 도구 | IPW·Hájek·AIPW 정책 가치(AIPW의 outcome model OOF 예측 포함)와 정책 차이, 부트스트랩 구간, 정책 생성, 처치 쌍별 Qini·AUUC, OOF 실행기(folds 테이블), DuckDB 실행 기록. BACKLOG docstring 삭제 행 | 없음 | PR-B |
| U3 EXP-001 비교 정책 | 무작위 타겟팅, 전체 발송 정책, 반응 모델의 OOF 정책 가치와 비교 정책 사이 차이의 seed 간 범위(U5 판정 규칙에 쓸 값). 세 추정량의 OOF 구간 폭 비교. 빈 `experiments/EXP-001/`을 `EXP-001-<주제>`로 바꿔 씀 | U2 | 실험 PR |
| U4 공통 학습기와 Kaggle 연결 | 학습기 인터페이스, causalml 설치 확인(로컬, Kaggle 이미지), dataset 업로드·출력 형식·DuckDB 기록 시험 실행 | U2 | U5 PR에 포함 |
| U5 EXP-002 1단계 | LightGBM 고정, S·T·X·DR-learner, uplift random forest, class transformation, transformed outcome. 설계 절 먼저 커밋 | U3, U4 | 실험 PR |
| 승인 | 1단계 방법론 | U5 | |
| U6 EXP-003 2단계 | base learner 비교, 결합 후보, 금액 모델 spend 잡음 문턱을 판정 규칙에 먼저 적음 | 1단계 승인 | 실험 PR |
| 승인 | 최종 모델 | U6 | |
| U7 M2 마감 | tests/baseline 회귀 기준값과 CI 회귀 테스트(형식은 이때 정함, 2026-11-26), NARRATIVE M2, 기록 문서 항목 | 최종 모델 승인 | 마감 PR |

- 병행: 쉬운 판 3\~9절(기초 개념은 문제에 걸린 것만, 2026-11-25 피드백). 하네스 BACKLOG 행은 다른 브랜치에 모아 M2를 닫을 때.

## 단위별 메모

### U1

- ANA-002, ANA-003 완료. 비교 정책 결정을 PROBLEM.md에 반영.

### U3: EXP-001 결과(2026-11-26)

- U2 점검에서 결과 파일 없이 낸 구간 폭 비교는 EXP-001에서 결과 파일로 다시 냈다(`artifacts/EXP-001/summary.md`). Hájek 편향 시뮬레이션 수치는 지웠다. 추정량은 구간 폭 규칙으로 정했고 편향은 판정에 쓰이지 않는다.
- U5로 넘길 것: seed 간 범위(`artifacts/EXP-001/tables/seed_range.csv`), 반응 모델 쌍별 Qini(`artifacts/EXP-001/tables/response_ranking.csv`), 반응 모델 HPO 예산(trial 50회, `experiments/EXP-001-comparison-policies/config.yaml`). `policy.top_k`는 반응 모델 정책 함수다. 고른 정책은 U5에서 메일별 uplift와 0 가운데 큰 쪽을 고르는 함수로 따로 만든다.

### U3, U5: 모델링에 가져갈 것(ANA-002, ANA-003)

- 변수: `history_segment`는 빼고 `history`만 쓴다(Spearman 0.97). 구매 상품 세그먼트를 한 변수로 넣는 안과 `mens`, `womens`를 그대로 넣는 안을 1단계에서 함께 본다.
- 모델 점검: 예측 uplift를 ANA-003 세그먼트별로 평균 내어 관측 효과(`artifacts/ANA-003/tables/segment_effects.csv`)와 비교한다. 첫 확인점은 남성 상품만 산 고객의 여성용 효과가 0에 가깝게 나오는지다.
- 판정 규칙의 기대치: 남성용이 거의 모든 세그먼트에서 `visit` 효과가 같거나 커서, 고른 정책과 전체 발송 정책의 `visit` 차이가 작게 나올 수 있다. 이 예상과 근거를 설계 절에 결과보다 먼저 적는다.
- 데이터 경계: 둘 다 산 고객과 Multichannel의 `history` 200 하한, `history` 500 이상은 모두 신규 고객. 모델이 이 경계를 효과처럼 쓰는지 본다.

### U6: 금액 모델

- 퍼널 분해의 가정(늘어난 방문 1회당 구매가 처치 안에서 세그먼트로 다르지 않음)은 반박되지 않았다(`artifacts/ANA-003/tables/funnel_by_product.csv`).
- 신규 고객은 `visit` 효과가 기존 고객과 비슷한데 `spend` 효과가 더 크다. 퍼널 분해가 이 차이를 잡는지 두 부분 모델과 비교할 때 이 세그먼트를 따로 본다.
