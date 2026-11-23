# DATA.md: 데이터

담는 범위: 데이터 출처와 받는 법, 무작위 배정 점검, 전처리, 분할.

지금 유효한 결정만 둔다. 결정마다 아래 절을 하나씩 만든다. 바뀐 이력은 git 커밋에 남긴다.

<!--
## <결정 제목: 결정 내용을 한 문장으로>

- 결정:
- 근거: 수치와 결과 파일 경로
- 기각한 대안: 대안과 기각 이유
-->

## 분석 데이터는 데이터 구조와 분석 목적에 따라 테이블로 나눈다

- 결정: 고객 특성, 처치 배정, 결과, 분할, 실험과 실행, 모델 예측, 지표를 각각 테이블로 나누고, 고객은 `customer_id`, 실험은 `experiment_id`, 실행은 `run_id`, 모델은 `model_id`로 잇는다. 저장 위치는 `docs/ENGINEERING.md` DuckDB 절이다. 아래는 초안이고, 열은 데이터를 받는 작업에서 확정한다.

  | 테이블 | 열(초안) | 담는 것 |
  | --- | --- | --- |
  | `customers` | customer_id, recency, history_segment, history, mens, womens, zip_code, newbie, channel | 고객 특성. `channel`은 지난 1년 구매 채널로 고객 특성이다 |
  | `treatments` | treatment_id, name | 처치 세 종류(Mens E-Mail, Womens E-Mail, No E-Mail) |
  | `assignments` | customer_id, treatment_id | 실험 배정 |
  | `outcomes` | customer_id, visit, conversion, spend | 발송 뒤 2주 결과 |
  | `splits` | customer_id, split, fold | 학습·시험 분할과 CV fold |
  | `experiments` | experiment_id, title | 실험 폴더 하나(`EXP-001`) |
  | `runs` | run_id, experiment_id, created_at, config, git_commit | 실행 하나의 설정 |
  | `models` | model_id, run_id, method, base_learner, treatment_definition | 실행 안의 모델 |
  | `predictions` | model_id, customer_id, treatment_id, fold, uplift_score | 고객별 처치별 예측 |
  | `metrics` | run_id, model_id, metric, fold, value | 지표 |

- 근거: 사용자 지시(2026-11-23). 변수 정의는 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.
- 기각한 대안: 원본 한 테이블에 예측과 지표 열을 덧붙이는 안. 실행이 늘 때마다 열이 늘고 실행 간 비교 쿼리가 어려워진다.
- 승인: 2026-11-23
