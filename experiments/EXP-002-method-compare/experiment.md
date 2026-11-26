# EXP-002-method-compare

## 질문

- 바뀔 결정: M2 1단계 방법론. LightGBM을 base learner로 고정했을 때 S·T·X·DR-learner, uplift random forest, class transformation, transformed outcome 가운데 어느 방법으로 2단계(base learner 비교)를 할지. 승인 지점: 모델 선택.
- 지킬 조건: 학습 세트만 쓴다. fold는 `folds` 테이블의 seed 42, 154, 1592와 5-fold(`scripts/splits.yaml`). 결과 변수는 `visit`. 학습과 HPO는 Kaggle CPU kernel에서 돈다(`config.yaml`의 `run_on`).
- 못 정한 질문: 구매 상품 특성의 형태(세그먼트 한 변수 대 `mens`, `womens` 그대로)는 이 실험에서 T-learner 하나로 비교해 보고만 하고, 방법론을 정한 뒤 2단계에서 정한다.

## 설계

- 질문 유형: 결정(방법론 선택).
- 추정 대상: 방법마다 고른 정책(`policy.best_action`)의 학습 세트 OOF `visit` 정책 가치와, 1위 방법과의 차이.
- 식별: 고객을 세 처치에 1/3씩 무작위 배정했고 배정 점검을 통과했다(`artifacts/ANA-001/tables/srm.json`, `smd.csv`). 배정 확률 1/3로 Hájek 추정량이 정책 가치를 식별한다.
- 추정:
  - 학습기: `learners.METHODS`의 일곱 방법. class transformation과 transformed outcome은 메일마다 따로(남성용 대 미발송, 여성용 대 미발송) 학습한다. 특성은 `features.feature_matrix`.
  - HPO: 방법마다 optuna TPE sampler(sampler seed 42)로 trial 50회. trial 점수는 seed 42 fold OOF로 만든 고른 정책의 Hájek 정책 가치다. LightGBM을 쓰는 여섯 방법은 EXP-001 반응 모델과 같은 탐색 범위(`response.search_space`), uplift random forest는 `learners.urf_space`. 고른 설정을 세 seed에 그대로 쓰고 `random_state`만 seed로 바꾼다.
  - 점수: 방법마다 세 seed의 OOF Hájek 정책 가치 평균.
  - 구간(보고용): 고객 복원 추출 부트스트랩 1,000회, 부트스트랩 seed는 실행 seed.
  - 특성 비교(보고용): T-learner를 구매 상품 세그먼트 한 변수 특성으로 같은 방식으로 한 번 더 돌린다.
- 판정 규칙:
  - 1위: 점수가 가장 큰 방법.
  - 가를 수 없는 차이: 1위 방법 A와 다른 방법 B마다 seed별 차이 $d_s = V_A(s) - V_B(s)$를 구한다. 평균 차이 $\bar d$가 문턱 $\max(R, 0.0038)$보다 작으면 A와 B를 가를 수 없다고 본다. $R$은 세 $d_s$의 최댓값 − 최솟값이고, 0.0038은 EXP-001의 seed 간 범위(`artifacts/EXP-001/tables/seed_range.csv`)다.
  - 선택: 1위와 가를 수 없는 방법(1위 포함) 가운데 가장 단순한 방법을 고른다. 단순한 순서는 S-learner, T-learner, class transformation, transformed outcome, X-learner, DR-learner, uplift random forest다(학습 한 번에 맞추는 모델 수와 단계가 적은 순, uplift random forest는 base learner가 없는 별도 알고리즘이고 학습이 가장 느려 맨 뒤).
  - 모든 방법의 점수가 같은 seed의 전체 발송 정책보다 낮으면, 고르지 않고 그 결과와 이유를 보고한다.
  - 판정은 방법론 승인을 요청하는 근거이고, 승인 전에 2단계로 넘어가지 않는다.
- 이미 본 것: EXP-001에서 반응 모델 100% 발송과 전체 발송의 차이는 세 seed 모두 구간이 0을 포함했다(`artifacts/EXP-001/tables/policy_differences.csv`). U4에서 일곱 방법이 효과를 심은 합성 데이터에서 남성용 효과를 되찾는 것을 확인했다(`tests/test_learners.py`). 학습 세트로 방법끼리 비교한 결과는 아직 없다.
- 예상: ANA-003에서 남성용 메일의 `visit` 효과가 거의 모든 세그먼트에서 여성용과 같거나 컸다(`artifacts/ANA-003/tables/segment_effects.csv`). 그래서 고른 정책은 대부분의 고객에게 남성용을 보내고, 방법 사이 차이와 고른 정책과 전체 발송 정책의 차이가 작게 나올 수 있다.
- 걸리는 점:
  - seed 셋으로 구한 $R$은 그 자체가 크게 흔들린다(세 값의 범위는 표준편차의 평균 1.69배, 그 표준편차는 0.89배). 0.0038 하한은 범위가 우연히 작게 나오는 경우를 막는다.
  - 기준은 학습 운만 다루고 학습 세트 고객 표본의 흔들림은 다루지 않는다. 표본 흔들림은 시험 세트 판정에서 다룬다.
- 논의한 선택지:
  - 문턱을 그 쌍의 $R$만으로 두는 안. 네 번에 한 번쯤 범위가 실제 흔들림보다 작게 나와 학습 운을 방법 차이로 판정한다.
  - 문턱을 0.0038로 고정하는 안. 한쪽만 학습하는 비교에서 잰 값이라 두 방법이 모두 학습하는 비교의 흔들림보다 작을 가능성이 크다.
  - 가를 수 없을 때 seed를 늘려 다시 재는 안. 방법마다 Kaggle 실행이 늘고, 1단계는 방법론만 고르고 2단계에서 다시 넓게 탐색한다.
  - 특성 두 안을 일곱 방법 모두에서 비교하는 안(kernel 14개). 1단계의 질문은 방법이고, 특성 비교는 방법 하나를 고정해 따로 보면 질문이 섞이지 않는다.

## 계획

- 실행 위치: Kaggle CPU kernel. 방법마다 kernel 하나(`scripts/kaggle.py push --part <방법>`)와 특성 비교 kernel 하나, 모두 여덟 개. batch CPU kernel은 동시에 다섯 개까지라 나머지는 대기열에 둔다.
- 바꿀 파일: 이 폴더의 `config.yaml`, `run.py`, `src/uplift/features.py`(구매 상품 세그먼트 특성), `src/uplift/selection.py`(판정 규칙), 테스트. 학습기와 Kaggle 실행 코드(`src/uplift/learners.py`, `kaggle_jobs.py`, `train_data.py`, `runs.py`, `scripts/kaggle.py`)와 EXP-001 `run.py`의 `--data`·`--db` 대응은 U4에서 같은 브랜치에 더했다.
- 산출물: `export <run_id>...`가 방법별 실행을 모아 낸다. `tables/`의 `method_scores.csv`(방법별 seed 점수와 평균), `pair_thresholds.csv`(1위와의 $\bar d$, $R$, 문턱, 가를 수 있는지), `method_choice.csv`(선택), `policy_values.csv`(구간), `response_same_send.csv`(같은 발송 수의 반응 모델과의 차이), `ranking.csv`(쌍별 Qini), `feature_compare.csv`, `hpo_trials.csv`, `metrics.json`, `figures/`.
- smoke: 여덟 part가 모두 표본에서 돌고, export가 위 표를 모두 내는지.
- 구현 검증: unit test(판정 규칙의 경우별 결과, 특성 함수, part 선택). 효과를 심은 합성 데이터 test는 `tests/test_learners.py`.

## 결과 해석

- 판정: 일곱 방법 모두 1위 transformed outcome과 가를 수 없어, 단순한 순서의 첫 방법 S-learner를 고른다(`artifacts/EXP-002/tables/pair_thresholds.csv`, `method_choice.csv`). 1위의 평균 점수가 전체 발송 정책보다 커서 "고르지 않는다" 규칙에는 걸리지 않는다. 고른 S-learner의 평균은 전체 발송 정책보다 작고, 차이 구간은 세 seed 모두 0을 포함한다(`policy_values.csv`).
- 설계와 달라진 점: 없다.
- 반영한 결정: 1단계 방법론을 S-learner로 정했다(사용자 승인 2026-11-26). 2단계 전에 예산 제약에서 반응 모델과 비교한다(ANA-004).
