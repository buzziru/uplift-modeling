# EXP-001-comparison-policies

## 질문

- 바뀔 결정:
  - 모델 선택(OOF)과 시험 세트 판정에 쓸 정책 가치 추정량(IPW, Hájek, AIPW 중 하나). 승인 지점: 데이터 분할과 검증 전략.
  - U5 판정 규칙의 "가를 수 없는 차이"의 참고값(비교 정책 차이의 seed 간 범위).
  - U5 이후 후보가 넘어야 할 비교 정책의 OOF 정책 가치.
- 지킬 조건: 학습 세트만 쓴다(시험 세트는 쓰지 않는다). fold는 `folds` 테이블의 seed 42, 154, 1592와 5-fold(`scripts/splits.yaml`). 결과 변수는 `visit`.
- 못 정한 질문: `spend` 정책 가치의 추정량(`spend`를 AIPW로 잴 때). U6 금액 모델에서 정한다.

## 설계

- 질문 유형: 추정(비교 정책의 정책 가치와 잡음의 크기)과 결정(추정량 선택).
- 추정 대상:
  - 세 비교 정책(무작위 타겟팅, 전체 발송 정책, 반응 모델 정책)의 학습 세트 `visit` 정책 가치와 정책 차이.
  - 정책 차이마다 세 추정량의 95% 구간 폭.
  - 정책 차이의 seed 간 범위.
  - 보고용: 반응 모델 정책의 쌍별 Qini와 AUUC(`ranking.ranking_scores`, U5 후보와 비교할 기준), outcome model의 처치군 안 설명력.
- 식별: 고객을 세 처치에 1/3씩 무작위 배정했고 배정 점검을 통과했다(`artifacts/ANA-001/tables/srm.json`, `smd.csv`). 그래서 배정 확률 1/3로 IPW·Hájek·AIPW가 정책 가치를 식별한다.
- 추정:
  - 정책: 전체 발송은 `policy.all_mens`, 무작위 타겟팅은 `policy.uniform`(기대값으로 계산해 seed와 무관), 반응 모델 정책은 `policy.top_k`에 메일별 OOF 예측 방문 확률을 넣는다.
  - 반응 모델: 남성용 군, 여성용 군마다 LightGBM 분류기를 따로 학습해 메일별 방문 확률을 5-fold OOF로 예측한다. 특성은 `features.feature_matrix`.
  - 반응 모델 HPO: U5 1단계와 같은 예산이다. optuna TPE sampler(sampler seed 42)로 trial 50회를 돈다. trial 점수는 seed 42 fold로 만든 두 메일 군 모델의 OOF log loss 합이다(각 모델은 자기 군 고객에서 잰다). 탐색 범위는 `num_leaves` 7\~63(로그), `learning_rate` 0.01\~0.1(로그), `n_estimators` 100\~1,000, `min_child_samples` 20\~500(로그), `subsample` 0.5\~1(`subsample_freq` 1), `colsample_bytree` 0.5\~1이다. 고른 설정을 세 seed에 그대로 쓰고 `random_state`만 seed로 바꾼다.
  - 발송 수: 반응 모델 정책은 발송 비율 10%, 20%, ..., 100%에서 잰다. U3에는 같은 발송 수로 맞출 uplift 정책이 아직 없어, 같은 발송 수 비교는 U5에서 한다.
  - 추정량: `value.compare_methods`. AIPW의 μ̂는 처치군별 logistic regression의 OOF 예측(`oof.outcome_model_oof`)이고 같은 seed의 fold를 쓴다.
  - 구간: 고객 복원 추출 부트스트랩 1,000회, μ̂ 고정, 부트스트랩 seed는 실행 seed.
  - outcome model 설명력: 처치군마다 R² = 1 − (μ̂의 제곱오차) / (처치군 평균 OOF 예측의 제곱오차)를 logistic regression과 반응 모델 HPO 설정의 LightGBM으로 잰다. AIPW 폭 / Hájek 폭은 근사적으로 √(1 − R²)이므로, AIPW가 10% 좁아지려면 R²가 약 0.19여야 한다. 판정에는 쓰지 않고 판정 결과의 해석에 쓴다.
- 판정 규칙:
  - 추정량: 비교 대상은 정책 차이 셋(전체 발송 − 무작위 타겟팅, 반응 모델 100% − 전체 발송, 반응 모델 50% − 전체 발송)과 seed 셋의 아홉 구간 폭이다. 먼저 Hájek의 평균 폭이 IPW보다 작으면 Hájek, 아니면 IPW를 기본으로 둔다. 그다음 AIPW의 평균 폭이 기본보다 10% 이상 작을 때만 AIPW를 고른다. outcome model을 따로 학습하고 관리하는 비용이 있어서다.
  - seed 간 범위: 반응 모델 100% − 전체 발송 차이의, 고른 추정량 점추정값의 세 seed 최댓값 − 최솟값이다. U5 판정 규칙에 참고값으로 넘긴다. 전체 발송과 무작위 타겟팅은 학습이 없어 seed와 무관하다.
  - 아홉 폭에서 두 추정량의 대소가 엇갈리면 평균으로 판정하고, 엇갈린 개수를 함께 보고한다.
- 이미 본 것: U2 점검(2026-11-26, seed 42)에서 모두 남성용 정책과 처치군별 logistic regression 예측으로 만든 정책의 세 추정량 폭을 봤다. Hájek과 AIPW가 IPW보다 7\~9% 좁았고 둘 사이 차이는 거의 없었다. 반응 모델 정책은 아직 보지 않았다. 같은 날 점검 스크립트(seed 42)로 처치군 안 R²를 쟀다. logistic regression 0.023\~0.029, LightGBM 기본값은 −0.003\~−0.001(과적합), 보수적으로 손으로 고른 LightGBM 0.019\~0.020이었다. 이 값들은 이 실험의 결과 파일로 다시 낸다.
- 걸리는 점:
  - seed 셋으로 구한 범위는 그 자체가 크게 흔들린다. 학습 운이 후보 차이보다 확연히 큰 경우를 잡는 참고값으로만 쓴다.
- 논의한 선택지:
  - 반응 모델 학습기로 logistic regression을 쓰는 안. U5 1단계 방법론이 LightGBM을 base learner로 고정하므로, 비교 정책도 같은 학습기를 써야 차이가 학습기가 아니라 방법(반응 확률 대 uplift)에서 온다.
  - 처치를 입력으로 넣은 모델 하나로 두 메일의 확률을 내는 안. 메일 군별 모델이 AIPW outcome model과 같은 구조이고, 메일마다 다른 반응 구조를 상호작용 설계 없이 담는다.
  - 반응 모델을 기본값으로 두는 안. 기본값 LightGBM은 처치군 안 R²가 음수라 과적합하고, 1단계에서 HPO를 받는 uplift 방법보다 불리하다.
  - HPO trial을 OOF 정책 가치로 평가하는 안. 정책 가치의 구간 폭(약 0.012)이 trial 사이 차이보다 커서 운 좋은 trial을 고르기 쉽고, 어느 추정량으로 잴지는 이 실험이 정한다. 반응 모델은 방문 확률을 맞히는 모델이라 log loss가 그 목적이다.
  - 예산을 시간으로 맞추는 안. 빠른 방법이 trial을 더 받아 같은 예산이 되지 않는다.
  - AIPW outcome model에 반응 모델과 같은 HPO나 특성 공학을 하는 안. outcome model이 나빠도 AIPW는 편향되지 않고 폭만 달라지는데, 위 점검의 R²(0.03 안팎)로 보면 10% 문턱에 필요한 0.19에 닿기 어렵다. 그래서 logistic regression을 유지하고 설명력을 결과로 보고한다.

## 계획

- 실행 위치: 로컬. trial 하나가 수 초이고 실행 전체가 수 분이다.
- 바꿀 파일: `src/uplift/response.py`(반응 모델 OOF와 HPO), `src/uplift/oof.py`(처치군 안 설명력), `src/uplift/value.py`(추정량 판정), `src/uplift/runs.py`(예측 기록), `src/uplift/plots.py`(발송 비율 그림), 이 폴더의 `config.yaml`, `run.py`, 테스트.
- 산출물: `artifacts/EXP-001/`의 `metrics.json`(판정), `tables/`(정책 가치와 차이, 추정량 폭, seed 간 범위, outcome model 설명력, HPO trial, 쌍별 Qini), `figures/`, `summary.md`.
- 구현 검증: unit test(반응 모델 OOF가 학습 fold만 쓰는지, HPO가 탐색 범위 안의 설정을 내는지, 설명력, 추정량 판정 규칙의 경우별 결과).
