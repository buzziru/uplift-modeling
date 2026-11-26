# EXP-001 요약: 비교 정책과 정책 가치 추정량

실행 `cfb0d1dade18`(`experiments/EXP-001-comparison-policies/run.py compute`). 데이터는 학습 세트 44,800명, 결과 변수는 `visit`, fold seed 42, 154, 1592의 5-fold OOF다. 구간은 고객 복원 추출 부트스트랩 1,000회의 95% 구간이다.

## 추정량은 Hájek이다. AIPW 폭은 Hájek의 0.984배라 문턱에 닿지 않는다

정책 차이 셋과 seed 셋의 아홉 구간 폭 평균은 IPW 0.0107, Hájek 0.0097, AIPW 0.0095다. Hájek은 IPW의 0.907배, AIPW는 Hájek의 0.984배다(`tables/estimator_choice.csv`). 아홉 폭 모두에서 대소가 평균과 같았다(`tables/estimator_widths.csv`).

## outcome model은 처치군 안에서 visit을 거의 설명하지 못한다

처치군 안 R²는 logistic regression 0.023\~0.029, 반응 모델 HPO 설정의 LightGBM 0.023\~0.025다(`tables/outcome_r2.csv`). LightGBM으로 바꿔도 같은 수준이라, AIPW가 Hájek보다 좁아지는 몫이 작다.

## 반응 모델 정책은 모두 발송해도 전체 발송 정책보다 높지 않다

Hájek 정책 가치는 전체 발송 정책 0.1828, 무작위 타겟팅 0.1468, 반응 모델 100% 발송 0.1789\~0.1827이다(`tables/policy_values.csv`, `figures/send_ratio.png`). 반응 모델 100% − 전체 발송 차이는 seed마다 −0.0026, −0.0001, −0.0039이고 세 구간 모두 0을 포함한다(`tables/policy_differences.csv`). 반응 모델 50% − 전체 발송 차이는 −0.0373\~−0.0336이다.

## 반응 모델 차이의 seed 간 범위는 0.0038이다

반응 모델 100% − 전체 발송 차이의 Hájek 점추정은 세 seed에서 −0.0039\~−0.0001이고 범위는 0.0038이다(`tables/seed_range.csv`). 같은 차이의 구간 폭(0.0076\~0.0081)의 절반 정도다(`tables/estimator_widths.csv`).

## 반응 모델의 쌍별 Qini는 U5 후보와 비교할 기준값이다

정규화 Qini는 남성용 대 미발송 0.021\~0.022, 여성용 대 미발송 0.026\~0.029, 남성용 대 여성용 0.039\~0.044다(`tables/response_ranking.csv`). 반응 모델 HPO의 최선 trial log loss는 0.8766이다(`tables/hpo_trials.csv`).
