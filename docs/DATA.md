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

- 결정: 고객 특성, 처치 배정, 결과, 분할, 실험과 실행, 모델 예측, 지표를 각각 테이블로 나누고, 고객은 `customer_id`, 실험은 `experiment_id`, 실행은 `run_id`, 모델은 `model_id`로 잇는다. 저장 위치는 `docs/ENGINEERING.md` DuckDB 절이다. `customers`, `treatments`, `assignments`, `outcomes`, `splits`, `folds`는 `scripts/build_db.py`가 만들고 열이 확정됐다. 나머지는 초안이고, 실험 기록 테이블은 첫 실험에서 만들며 열을 확정한다.

  | 테이블 | 열 | 담는 것 |
  | --- | --- | --- |
  | `customers` | customer_id, recency, history_segment, history, mens, womens, zip_code, newbie, channel | 고객 특성. `channel`은 지난 1년 구매 채널로 고객 특성이다 |
  | `treatments` | treatment_id, name | 처치 세 종류. 0 No E-Mail, 1 Mens E-Mail, 2 Womens E-Mail |
  | `assignments` | customer_id, treatment_id | 실험 배정 |
  | `outcomes` | customer_id, visit, conversion, spend | 발송 뒤 2주 결과 |
  | `splits` | customer_id, split | 학습·시험 분할. 고객마다 한 행 |
  | `folds` | customer_id, seed, fold | 학습 세트의 CV fold. seed마다 학습 고객 한 행씩 |
  | `experiments` | experiment_id, title | 실험 폴더 하나(`EXP-001`) |
  | `runs` | run_id, experiment_id, created_at, config, git_commit | 실행 하나의 설정 |
  | `models` | model_id, run_id, method, base_learner, treatment_definition | 실행 안의 모델 |
  | `predictions` | model_id, customer_id, treatment_id, fold, uplift_score | 고객별 처치별 예측 |
  | `metrics` | run_id, model_id, metric, fold, value | 지표 |

- 근거: 사용자 지시(2026-11-23). 변수 정의는 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.
- 기각한 대안: 원본 한 테이블에 예측과 지표 열을 덧붙이는 안. 실행이 늘 때마다 열이 늘고 실행 간 비교 쿼리가 어려워진다.
- 승인: 2026-11-23

## 원본은 MineThatData 원 출처 CSV를 받고 받을 때만 SHA-256으로 확인한다

- 결정:
  - `scripts/fetch_data.py`가 MineThatData의 원 출처 CSV(2008-03-20판)를 받는다. SHA-256과 행 수(64,000), 열 이름을 확인한 뒤 `data/raw/hillstrom.parquet`로 저장한다. 해시는 스크립트의 `SHA256` 상수에 있고, 해시가 다르면 받은 파일을 지우고 멈춘다.
  - 체크섬은 받을 때만 확인한다. PR마다 도는 검사(CI와 `.claude/harness/config.json`의 `check`)에는 넣지 않는다.
- 근거: 사용자 결정(2026-11-23). 받기는 환경마다 한 번이고, CI에는 데이터가 없다. 해시는 2026-11-23에 처음 받은 파일의 값이다. 출처 설명은 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.
- 기각한 대안:
  - `scikit-uplift`의 `fetch_hillstrom`. 다른 미러의 gz 파일을 받아, 원 출처 파일과 같은지 그 해시로 확인할 수 없다.
  - 체크섬 확인을 PR마다 도는 검사에 넣는 안. CI에는 원본이 없고, 받은 뒤에는 원본이 바뀌지 않는다.
- 승인: 2026-11-23

## 고객 ID는 원본 CSV의 행 순서로 매긴다

- 결정: 원본에는 고객 ID가 없어서, 원본 CSV의 행 순서(0부터)를 `customer_id`로 쓴다. `scripts/build_db.py`가 Parquet를 `data/uplift.duckdb`에 적재할 때 매긴다.
- 근거: 같은 원본에서 늘 같은 ID가 나오므로 다시 적재해도 예측과 분할이 같은 고객을 가리킨다. 원본 해시를 고정했으므로(위 절) 행 순서도 고정된다.
- 기각한 대안: 고객 특성 열을 합쳐 해시로 ID를 만드는 안. 특성이 같은 고객이 여러 명이면 ID가 겹친다.
- 승인: 2026-11-23


## 적재 때 키, 허용값과 범위, 깔때기, 분할 규칙을 확인하고 어긋나면 적재를 멈춘다

- 결정: `build_tables`(`uplift.db.check_tables`)와 `scripts/build_db.py`(`uplift.split.check_splits`)가 아래 규칙을 확인한다. 규칙은 뒤의 계산이 기대는 사실만 둔다.

  | 묶음 | 규칙 | 기대는 계산 |
  | --- | --- | --- |
  | 키 | `customer_id` 고유, `customers`, `assignments`, `outcomes`가 같은 고객 집합 | 모든 조인 |
  | 허용값과 범위 | `treatment_id` ∈ {0, 1, 2}, `history_segment`, `zip_code`, `channel`은 정해진 값 집합, 이진 열과 `visit`, `conversion`은 0/1, `recency` 1\~12, `history`, `spend` 0 이상 | 범주별 SMD, 모델 입력. 값 집합을 고정해 새 오타가 들어오면 멈춘다 |
  | 깔때기 | `conversion = 1`이면 `visit = 1`, `spend > 0`과 `conversion = 1`이 같다 | 깔때기 층화, 방문과 매출의 관계 |
  | 분할 | 고객마다 `splits` 한 행, seed마다 학습 고객이 `folds`에 한 번씩 | 시험 세트 단일 사용, OOF 예측 |

- 근거: 사용자 지시(2026-11-24). 지금 데이터는 모든 규칙을 통과한다(`scripts/build_db.py` 실행). 규칙 위반을 잡는지는 `tests/test_db.py`, `tests/test_split.py`가 본다.
- 기각한 대안: dbt-duckdb로 품질 테스트를 두는 안. 적재가 한 번뿐인 정적 데이터에 프로젝트 폴더와 실행 단계가 따로 생기고, 데이터 파일이 CI에 없어 CI에서 돌지 못한다. sqlglot으로 위험한 SQL을 막는 안. DB는 원본에서 다시 만들 수 있고 분석 노트북은 읽기 전용으로 연결해 대상 쪽에서 지켜진다. `history_segment`와 `history`의 구간 일치 규칙. 모델에 둘 중 하나만 넣으면 기대는 계산이 없다.
- 승인: 2026-11-24

## 범주 오타는 적재 코드의 대응표로 고친다

- 결정: `uplift.db.CATEGORY_FIXES`에 원본 값과 고친 값을 두고 `build_tables`가 적재 때 바꾼다. 지금은 `zip_code`의 `Surburban`을 `Suburban`으로 바꾼다. 바꾼 뒤 허용값 규칙이 값 집합을 확인한다.
- 근거: 사용자 지시(2026-11-24). 원본의 `zip_code` 세 값 가운데 `Surburban`이 28,776행이다(고친 뒤 `profile.json`의 `categories`). 이름만 바뀌므로 SMD, 층화, 모델 성능은 같다. 이름은 산출물 표, 문서 인용, 모델의 원핫 열 이름, 대시보드에 남아서, 첫 산출물(ANA-001)이 나오기 전에 고쳤다.
- 기각한 대안: 원본 CSV나 DuckDB 파일을 손으로 고치는 안. 원본은 체크섬으로 지키는 정본이고 DB는 원본에서 다시 만드는 산출물이라 고친 내용이 다시 만들 때 사라진다. 분석 단계에서 고치는 안. 분석마다 같은 수정을 되풀이한다.
- 승인: 2026-11-24

## 무작위 배정은 SRM과 SMD로 점검하고 불균형이면 공변량 보정 회귀로 ATE를 구한다

- 결정:
  - SRM: 세 군의 크기를 설계 비율(1/3씩)과 카이제곱 적합도 검정으로 비교한다. p < 0.001이면 분석을 멈추고 배정과 기록을 조사한다.
  - 공변량 균형: 원본 공변량(범주형은 범주별 비율)의 표준화 평균 차이(SMD)를 세 군 정의(남성용, 여성용 각각 대 미발송)와 이진 정의(메일 전체 대 미발송)로 구한다. 모두 |SMD| < 0.1이면 평균 차이를 ATE로 쓴다. 하나라도 0.1 이상이면 Y = α + τ·T + βX 회귀의 τ를 ATE로 쓴다.
  - 결과: SRM과 균형 모두 통과해 평균 차이를 ATE로 쓴다.
- 근거: `analyses/ANA-001-randomization-and-ate.py`. SRM은 χ² = 0.203, p = 0.904(`artifacts/ANA-001/tables/srm.json`). SMD는 세 비교 x 공변량·범주 54개의 |SMD| 최댓값이 0.0164(Mens vs None, `history_segment = 2) $100 - $200`)다(`artifacts/ANA-001/tables/smd.csv`, 그림 `artifacts/ANA-001/figures/smd.png`). 0.1은 실무에서 통용되는 경험칙이다(Austin, 2009).
- 기각한 대안: 공변량마다 t검정 p값으로 균형을 보는 안. 군마다 2만 명이면 아주 작은 차이도 유의하게 나와, 차이가 결론을 흔들 만큼 큰지를 답하지 못한다.
- 승인: 2026-11-24

## 처치 x 깔때기 단계로 층화해 학습 70%, 시험 30%로 한 번 나누고, 학습 세트에 seed 세 개로 5-fold를 매긴다

- 결정:
  - 시험 세트: 처치(3) x 깔때기 단계(방문 안 함, 방문만, 구매)의 9개 층으로 층화해 30%를 seed 42로 한 번 나눈다. 시험 세트는 고정하고 마지막 판정에 한 번만 쓴다.
  - CV: 학습 세트에 같은 층으로 층화한 5-fold를 seed 42, 154, 1592로 세 번 매긴다. 학습 과정의 seed(fold 배정, 모델 `random_state`)를 바꿔 결과의 흔들림을 잰다.
  - 설정은 `scripts/splits.yaml`, 결과는 `splits`, `folds` 테이블이다.
- 근거: 사용자 지시(2026-11-24). 구매는 시험 세트에서 처치별 36\~80명이다(`profile.json`의 `splits`). 구매가 드물어 분할 운에 따라 `spend` 결과가 크게 흔들리므로, 깔때기 단계로 층화해 구매 고객을 학습과 시험에 7:3으로 나눈다. 시험 세트 크기에서 `spend` 차이의 95% 구간 반폭은 0.47\~0.52다(`artifacts/ANA-001/tables/precision.csv`).
- 기각한 대안: 처치 x `visit`으로 층화하는 안(SPEC.md 3절의 처음 안). 구매 고객 수가 분할마다 달라진다. 80/20 분할. 학습이 1.14배 커지는 대신 시험 세트의 구간이 약 1.22배 넓어진다. 시험 세트도 seed마다 다시 나누는 안. 시험 세트를 한 번만 쓰는 원칙이 깨진다.
- 승인: 2026-11-24

## 데이터 명세

수치와 타입은 전부 `artifacts/data/profile.json`에서 온다(`scripts/build_db.py`가 만듦). 조건은 원본 전체 64,000행이고, 분할 전이다. 테이블별 앞 5행은 `artifacts/data/tables.md`에 있다.

고객 특성(`customers`)에는 결측이 없다.

| 열 | 타입 | 값 |
| --- | --- | --- |
| `recency` | int64 | 1\~12(마지막 구매 뒤 개월 수) |
| `history_segment` | str | 7구간: `1) $0 - $100`, `2) $100 - $200`, `3) $200 - $350`, `4) $350 - $500`, `5) $500 - $750`, `6) $750 - $1,000`, `7) $1,000 +` |
| `history` | float64 | 29.99\~3,345.93(지난 1년 구매 금액, 달러) |
| `mens` | int64(0/1) | 1의 비율 0.551 |
| `womens` | int64(0/1) | 1의 비율 0.5497 |
| `zip_code` | str | `Rural`, `Suburban`, `Urban`. 원본의 `Surburban`을 적재 때 고친다("범주 오타는 적재 코드의 대응표로 고친다" 절) |
| `newbie` | int64(0/1) | 1의 비율 0.5022 |
| `channel` | str | `Multichannel`, `Phone`, `Web` |

결과(`outcomes`)는 `visit`(int64, 0/1), `conversion`(int64, 0/1), `spend`(float64, 달러)다. 열 정의는 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.

처치 그룹별 행 수와 결과 평균:

| 처치 | 행 수 | visit 비율 | conversion 비율 | spend 평균 |
| --- | --- | --- | --- | --- |
| No E-Mail | 21,306 | 0.1062 | 0.0057 | 0.6528 |
| Mens E-Mail | 21,307 | 0.1828 | 0.0125 | 1.4226 |
| Womens E-Mail | 21,387 | 0.1514 | 0.0088 | 1.0772 |

그룹 간 차이의 신뢰구간과 공변량 균형은 "무작위 배정은 SRM과 SMD로 점검하고 불균형이면 공변량 보정 회귀로 ATE를 구한다" 절.

경계값에 몰린 행이 있다(`profile.json`의 `boundary_counts`). 고칠 대상이 아니라 데이터가 만들어진 방식으로 보고, 해석에서 고려한다.

- `history` 최솟값 29.99에 7,947행이 몰려 있다. 지난 1년 구매 금액의 하한으로 보인다.
- `spend`는 구매 고객의 최솟값 29.99가 136행, 최댓값 499.0이 12행이다. 499.0은 위쪽을 자른 값으로 보이고, 그렇다면 큰 구매의 금액이 낮게 기록돼 `spend` 효과를 약간 낮게 본다. 원 출처 설명에서 확인하지 못해 추정으로 둔다.
