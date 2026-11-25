# M2 계획: 모델링

작업 분해는 2026-11-25 사용자 동의. 순서는 앞 단위가 끝나야 열리는 조건을 따른다. 시험 세트는 M2에서 쓰지 않는다. 단위가 끝나면 그 행에 PR 번호를 적는다.

## 작업 분해

| 단위 | 내용 | 앞에 필요한 것 | PR |
| --- | --- | --- | --- |
| U1 ANA-002, ANA-003 | ANA-002 분포 EDA(공변량·결과 분포와 변수별 해석, 상관, 군별 분포와 구매 고객 1명당 금액 구간). ANA-003 고객 세그먼트와 메일 반응(구매 상품·지역·채널 교차 구성, 대조군의 세그먼트별 행동, 세그먼트별 효과와 퍼널 분해 가정 확인, 담당자 질문). 2026-11-25 분리. 학습 세트만. 기준선 정책 정의를 PROBLEM.md와 PENDING에 반영 | 없음 | PR-A |
| U2 평가 도구 | IPW 정책 가치와 정책 차이, 부트스트랩 구간, 정책 생성, 처치 쌍별 Qini·AUUC, OOF 실행기(folds 테이블), DuckDB 실행 기록. BACKLOG "다음 작업 PR" 두 행 | 없음 | PR-B |
| U3 EXP-001 기준선 | 무작위 타겟팅, 전체 발송 정책, 반응 모델의 OOF 정책 가치와 기준선 사이 차이의 seed 간 범위(U5 판정 규칙에 쓸 값). 빈 `experiments/EXP-001/`을 `EXP-001-<주제>`로 바꿔 씀 | U2 | 실험 PR |
| U4 공통 학습기와 Kaggle 연결 | 학습기 인터페이스, causalml 설치 확인(로컬, Kaggle 이미지), dataset 업로드·출력 형식·DuckDB 기록 시험 실행 | U2 | U5 PR에 포함 |
| U5 EXP-002 1단계 | LightGBM 고정, S·T·X·DR-learner, uplift random forest, class transformation, transformed outcome. 설계 절 먼저 커밋 | U3, U4, SPEC 14절 승인(U3 무렵 요청). 늦으면 이진 전용 둘을 나눔 | 실험 PR |
| 승인 | 1단계 방법론 | U5 | |
| U6 EXP-003 2단계 | base learner 비교, 결합 후보, 금액 모델 spend 잡음 문턱을 판정 규칙에 먼저 적음 | 1단계 승인 | 실험 PR |
| 승인 | 최종 모델 | U6 | |
| U7 M2 마감 | tests/baseline 회귀 기준값과 CI 회귀 테스트(SPEC 9절 84줄 시점은 U3 결과 보고 정함), NARRATIVE M2, 기록 문서 항목 | 최종 모델 승인 | 마감 PR |

- 메인 결정(구현 때 정본에 반영하고 기록 문서에 항목): 1단계는 방법마다 같은 예산의 가벼운 HPO(trial은 seed 42), 2단계는 넓게. S·T·X·DR·uplift RF는 causalml, class transformation·transformed outcome은 직접 구현. IPW 배정 확률은 설계값 1/3.- 병행: 쉬운 판 3\~9절(기초 개념은 문제에 걸린 것만, 2026-11-25 피드백). 하네스 BACKLOG 행은 다른 브랜치에 모아 M2를 닫을 때.

## 단위별 메모

### U1

- ANA-002, ANA-003 완료. 기준선 정책(전체 발송 정책, 무작위 타겟팅, 반응 모델) 결정을 PROBLEM.md와 PENDING에 반영.

### U3, U5: 모델링에 가져갈 것(ANA-002, ANA-003)

- 변수: `history_segment`는 빼고 `history`만 쓴다(Spearman 0.97). 구매 상품 세그먼트를 한 변수로 넣는 안과 `mens`, `womens`를 그대로 넣는 안을 1단계에서 함께 본다.
- 모델 점검: 예측 uplift를 ANA-003 세그먼트별로 평균 내어 관측 효과(`artifacts/ANA-003/tables/segment_effects.csv`)와 비교한다. 첫 확인점은 남성 상품만 산 고객의 여성용 효과가 0에 가깝게 나오는지다.
- 판정 규칙의 기대치: 남성용이 거의 모든 세그먼트에서 `visit` 효과가 같거나 커서, 고른 정책과 전체 발송 정책의 `visit` 차이가 작게 나올 수 있다. 이 예상과 근거를 설계 절에 결과보다 먼저 적는다.
- 데이터 경계: 둘 다 산 고객과 Multichannel의 `history` 200 하한, `history` 500 이상은 모두 신규 고객. 모델이 이 경계를 효과처럼 쓰는지 본다.

### U6: 금액 모델

- 퍼널 분해의 가정(늘어난 방문 1회당 구매가 처치 안에서 세그먼트로 다르지 않음)은 반박되지 않았다(`artifacts/ANA-003/tables/funnel_by_product.csv`).
- 신규 고객은 `visit` 효과가 기존 고객과 비슷한데 `spend` 효과가 더 크다. 퍼널 분해가 이 차이를 잡는지 두 부분 모델과 비교할 때 이 세그먼트를 따로 본다.
