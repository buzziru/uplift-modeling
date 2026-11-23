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

- 결정: 고객 특성, 처치 배정, 결과, 분할, 실험과 실행, 모델 예측, 지표를 각각 테이블로 나누고, 고객은 `customer_id`, 실험은 `experiment_id`, 실행은 `run_id`, 모델은 `model_id`로 잇는다. 저장 위치는 `docs/ENGINEERING.md` DuckDB 절이다. `customers`, `treatments`, `assignments`, `outcomes`는 `scripts/build_db.py`가 만들고 열이 확정됐다. 나머지는 초안이고, 만드는 작업에서 열을 확정한다. `splits`는 분할 전략(SPEC.md 11절 승인 지점)이 정해진 뒤, 실험 기록 테이블은 첫 실험에서 만든다.

  | 테이블 | 열 | 담는 것 |
  | --- | --- | --- |
  | `customers` | customer_id, recency, history_segment, history, mens, womens, zip_code, newbie, channel | 고객 특성. `channel`은 지난 1년 구매 채널로 고객 특성이다 |
  | `treatments` | treatment_id, name | 처치 세 종류. 0 No E-Mail, 1 Mens E-Mail, 2 Womens E-Mail |
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

## 원본은 MineThatData 원 출처 CSV를 받고 SHA-256으로 확인한다

- 결정:
  - `scripts/fetch_data.py`가 MineThatData의 원 출처 CSV(2008-03-20판)를 `data/raw/hillstrom.csv`로 받고, SHA-256과 행 수(64,000)·열 이름을 확인한 뒤 `data/raw/hillstrom.parquet`로 저장한다. 해시는 스크립트의 `SHA256` 상수에 있다.
  - `scripts/build_db.py`가 Parquet를 `data/uplift.duckdb`에 적재하고 명세용 요약을 `artifacts/data/profile.json`으로 내보낸다.
  - 원본에는 고객 ID가 없어 원본 CSV의 행 순서(0부터)를 `customer_id`로 쓴다.
  - 체크섬 확인은 받을 때만 한다. 저장소 검사(`check`)에는 넣지 않는다. 받기는 환경마다 한 번이고, CI에는 데이터가 없다.
- 근거: 사용자 결정(2026-11-23). 해시는 2026-11-23에 처음 받은 파일의 값이다. 출처 설명은 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.
- 기각한 대안: `scikit-uplift`의 `fetch_hillstrom`. 다른 미러의 gz 파일을 받아 원 출처 파일과 같은지 그 해시로 확인할 수 없다.
- 승인: 2026-11-23

## 데이터 명세

수치는 전부 `artifacts/data/profile.json`에서 온다. 조건은 원본 전체 64,000행이고, 분할 전이다.

고객 특성(`customers`)에는 결측이 없다.

| 열 | 타입 | 값 |
| --- | --- | --- |
| `recency` | 정수 | 1\~12(마지막 구매 뒤 개월 수) |
| `history_segment` | 문자열 | 7구간: `1) $0 - $100`, `2) $100 - $200`, `3) $200 - $350`, `4) $350 - $500`, `5) $500 - $750`, `6) $750 - $1,000`, `7) $1,000 +` |
| `history` | 실수 | 29.99\~3,345.93(지난 1년 구매 금액, 달러) |
| `mens` | 0/1 | 1의 비율 0.551 |
| `womens` | 0/1 | 1의 비율 0.5497 |
| `zip_code` | 문자열 | `Rural`, `Surburban`, `Urban`. `Surburban`은 원본 표기를 그대로 둔다 |
| `newbie` | 0/1 | 1의 비율 0.5022 |
| `channel` | 문자열 | `Multichannel`, `Phone`, `Web` |

결과(`outcomes`)는 `visit`(0/1), `conversion`(0/1), `spend`(실수, 달러)다. 열 정의는 `docs/THEORY.md` "Hillstrom 데이터 구조" 절.

처치 그룹별 행 수와 결과 평균:

| 처치 | 행 수 | visit 비율 | conversion 비율 | spend 평균 |
| --- | --- | --- | --- | --- |
| No E-Mail | 21,306 | 0.1062 | 0.0057 | 0.6528 |
| Mens E-Mail | 21,307 | 0.1828 | 0.0125 | 1.4226 |
| Womens E-Mail | 21,387 | 0.1514 | 0.0088 | 1.0772 |

그룹 간 차이의 신뢰구간과 공변량 균형 점검은 M1에서 한다.
