# EXP-002 요약: 1단계 방법론 비교

실행 여덟 개(`metrics.json`의 `run_ids`, Kaggle CPU kernel). 데이터는 학습 세트 44,800명, 결과 변수는 `visit`, fold seed 42, 154, 1592의 5-fold OOF다. 방법마다 HPO trial 50회, 구간은 고객 복원 추출 부트스트랩 1,000회의 95% 구간이다. DR-learner는 처음 실행에서 교차 적합 분할에 seed가 들어가지 않아 같은 설정으로 재현되지 않았고, seed를 넘기도록 고친 코드로 그 part만 다시 돌린 실행이다.

## 일곱 방법 모두 1위 transformed outcome과 가를 수 없어, 판정 규칙대로 S-learner를 고른다

세 seed 평균 정책 가치는 transformed outcome 0.1830이 가장 크고 T-learner 0.1809가 가장 작다(`tables/method_scores.csv`). 1위와의 평균 차이는 0.0001\~0.0022이고, 쌍마다 문턱은 0.0038\~0.0052라 모든 쌍이 문턱 아래다(`tables/pair_thresholds.csv`). 그래서 단순한 순서의 첫 방법 S-learner(0.1817)를 고른다(`tables/method_choice.csv`).

## 어느 방법의 고른 정책도 전체 남성용 발송보다 낫다고 말할 수 없다

전체 남성용 발송(all_mens)의 정책 가치는 0.1828이다(`tables/method_choice.csv`). 1위 transformed outcome과 2위 DR-learner(0.1829)의 평균만 이보다 크고, S-learner를 비롯한 다섯 방법은 평균이 더 작다(`tables/method_scores.csv`). 그래서 "모든 방법이 전체 발송보다 낮으면 고르지 않는다"는 규칙에는 걸리지 않는다.

고른 정책 − all_mens 차이는 방법 일곱과 seed 셋의 21개 점추정이 −0.0032\~0.0019다. 21개 구간 가운데 20개가 0을 포함하고, class transformation seed 1592(−0.0060\~−0.0007) 하나는 0보다 아래에 있다. 0보다 위에 있는 구간은 없다(`tables/policy_values.csv`).

## 고른 정책은 거의 모든 고객에게 메일을 보내, 방법 사이 차이는 메일 종류에서만 난다

고른 정책의 발송 수는 seed와 방법에 따라 44,745\~44,800명이고, S-learner, transformed outcome, uplift random forest는 세 seed 모두 44,800명 전원에게 보낸다(`tables/policy_values.csv`). 고른 정책은 메일별 uplift 가운데 큰 값이 0보다 크면 보내므로, 어느 방법에서든 예측 uplift가 0보다 큰 고객이 거의 전부다.

## 같은 발송 수의 반응 모델 정책과도 가를 수 없다

S-learner 정책 − 같은 발송 수의 반응 모델 정책 차이는 seed마다 0.0021, −0.0010, 0.0023이고 세 구간 모두 0을 포함한다(`tables/response_same_send.csv`).

## 구매 상품 세그먼트 특성은 T-learner를 세 seed 모두 높였지만 차이가 문턱보다 작다

세그먼트 한 변수 특성 − `mens`·`womens` 특성 차이는 0.0008, 0.0007, 0.0014다(`tables/feature_compare.csv`). 방법 비교의 문턱 하한 0.0038보다 작다(`tables/pair_thresholds.csv`).

## 메일 대 미발송 순위는 여성용만 잡히고 남성용은 거의 잡히지 않는다

정규화 Qini는 여성용 대 미발송이 방법과 seed에 따라 0.0380\~0.0606, 남성용 대 여성용이 0.0270\~0.0495다. 남성용 대 미발송은 −0.0118\~0.0122로 0 근처다. 일곱 방법 가운데 세 seed 모두 양수인 방법은 class transformation, 모두 음수인 방법은 uplift random forest이고, 나머지 다섯 방법은 seed에 따라 부호가 바뀐다(`tables/ranking.csv`). 비용을 넣어 남성용 메일을 받을 고객을 줄이는 정책은 이 순위에 기대므로, 지금 모델로는 그 정책의 이득이 작을 수 있다.
