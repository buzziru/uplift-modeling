# ANA-002 요약: 분포 EDA

노트북: `analyses/ANA-002-eda.py`. 데이터는 학습 세트 44,800행이다.

## history는 29.99에 몰리고 꼬리가 길어, 트리 모델 입력에 변환 없이 history 하나만 쓴다

- 고객의 12.4%가 최솟값 29.99에 있고, 중앙값 158, p99 1,222, 최댓값 3,346이다(`tables/numeric_summary.csv`, `figures/numeric_distribution.png`).
- `history_segment`는 `history`를 구간으로 자른 값이라 Spearman 0.97이다(`tables/spearman.csv`).

## recency는 9\~10개월에 두 번째 봉우리가 있고, 신규·기존 고객 모두에게 나타난다

신규 고객과 기존 고객의 recency 분포가 같은 모양이다(`tables/recency_by_newbie.csv`). 그 시기에 고객을 많이 모은 것이 아니라 구매가 몰린 시기였다는 해석과 맞는다. 실험 날짜가 없어 어떤 행사인지는 알 수 없다.

## mens와 womens는 구매 상품 표시이고, 모든 고객이 둘 중 하나 이상을 샀다

남성 상품만 45.3%, 여성 상품만 44.6%, 둘 다 10.1%이고 둘 다 사지 않은 고객은 없다(`tables/product_shares.csv`).

## 기존 고객은 history가 500 아래에서 잘려 있고, Multichannel 고객은 history가 모두 200 이상이다

- 기존 고객의 `history` 최댓값은 499.95이고(`tables/history_by_newbie.csv`), 500달러 이상 구간의 고객은 모두 신규 고객이다(`tables/segment_by_newbie.csv`, Cramer's V 0.41, `tables/cramers_v.csv`).
- Multichannel 고객에게는 200달러 미만 구간이 없다(`tables/segment_by_channel.csv`, Cramer's V 0.33, `tables/cramers_v.csv`).
- 그 밖의 쌍은 `mens`·`womens`를 빼면 Cramer's V 0.13 이하다.

## 구매 고객의 spend는 4분의 1이 29.99이고 499에서 잘려 있다

구매 고객 405명의 중앙값은 78.9, 평균 117.4다. 24.9%가 최솟값 29.99를 썼고, 최댓값 499에 8명이 있다(`tables/outcome_summary.csv`, `figures/buyer_spend.png`).

## 구매 고객 1명당 금액은 처치군 사이에 차이를 가를 수 없다

남성용 117.9, 여성용 120.0, 미발송 112.3이고, 남성용 대 여성용 차이는 -2.1(95% 구간 -26.9\~23.1)이다(`tables/buyer_spend_mean_ci.csv`, `figures/buyer_spend_ecdf.png`). 처치 뒤 구매로 걸러진 고객끼리의 비교라 처치 효과가 아니다.
