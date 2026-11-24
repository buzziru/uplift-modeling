---
title: Uplift modeling 입문
sections: [정의와 푸는 문제, 고객 네 유형, 대표 방법, 평가, Hillstrom 데이터 구조]
---

# Uplift modeling 입문

## 정의와 푸는 문제

Uplift modeling은 마케팅 캠페인 같은 처치(treatment)가 고객의 행동을 얼마나 바꾸는지를 추정하는 기법이다 (Radcliffe & Surry, 2011; Gutierrez & Gérardy, 2017). 처치는 고객에게 하는 개입(이메일 발송, 쿠폰 지급 등)이다. <mark>예측 대상이 "살 확률"이 아니라 "처치 때문에 늘어나는 살 확률"이라는 점이 일반 분류 모델과 다르다.</mark>

이 구분이 필요한 이유는 기존 응답 모델(response model)이 처치가 없어도 살 사람까지 고르기 때문이다. 응답 모델은 처치했을 때 고객이 살 확률을 추정한다. Radcliffe & Surry (2011)는 고객 전체에 캠페인을 보냈을 때는 캠페인을 보내지 않은 비교 집단(대조군)보다 이익이 났지만, 응답 모델이 고른 상위 30%에만 보냈을 때는 증분 매출이 거의 0이었던 사례를 든다. 응답 모델이 어차피 살 사람만 골랐기 때문이다. 그래서 <mark>같은 예산으로 매출을 늘리려면 응답 확률이 아니라 응답 확률의 증가분으로 고객을 줄 세워야 한다.</mark>

<mark>이진 결과(구매 1, 비구매 0)에서 uplift는 처치를 받았을 때의 구매 확률에서 받지 않았을 때의 구매 확률을 뺀 값이다</mark> (Radcliffe & Surry, 2011). 특성 벡터를 $x$, 처치 여부를 $W$(처치 1, 대조 0), 결과를 $Y$라 쓴다.

$$
u(x) = P(Y = 1 \mid X = x, W = 1) - P(Y = 1 \mid X = x, W = 0)
$$

인과추론에서는 처치 효과를 잠재 결과(potential outcome)로 정의한다 (Rubin, 1974; Gutierrez & Gérardy, 2017). <mark>잠재 결과는 한 사람이 처치를 받았다면 나왔을 결과 $Y_i(1)$과 받지 않았다면 나왔을 결과 $Y_i(0)$을 함께 상정한 것이고, 그 사람의 처치 효과는 $\tau_i = Y_i(1) - Y_i(0)$이다</mark>. 특성이 같은 사람들의 평균 처치 효과를 조건부 평균 처치 효과(CATE, conditional average treatment effect)라 한다.

$$
\tau(x) = E[Y_i(1) \mid X_i = x] - E[Y_i(0) \mid X_i = x]
$$

결과가 0 또는 1이고 처치를 무작위로 배정했다면 $u(x)$와 $\tau(x)$는 같은 양이다. 결과가 0 또는 1이면 기댓값이 확률이고, 무작위 배정이면 처치군에서 관측한 $P(Y = 1 \mid X, W = 1)$이 $E[Y(1) \mid X]$와 같기 때문이다.

추정이 어려운 이유는 한 사람에게서 두 잠재 결과를 동시에 관측할 수 없기 때문이다. Holland (1986)는 이를 인과추론의 근본 문제(fundamental problem of causal inference)라 불렀다. 실제로 관측하는 값은 받은 쪽의 결과 하나, $Y_i^{obs} = W_i Y_i(1) + (1 - W_i) Y_i(0)$뿐이다 (Gutierrez & Gérardy, 2017). 그래서 개인마다 정답 $\tau_i$가 있는 지도학습처럼 풀 수 없다.

이 한계를 넘는 표준 방법은 고객을 무작위로 처치군과 대조군에 나누는 실험이다 (Gutierrez & Gérardy, 2017; Radcliffe & Surry, 2011). <mark>무작위로 나누면 두 군은 처치 말고는 평균적으로 같으므로, 특성이 비슷한 처치군 고객과 대조군 고객의 결과 차이를 처치 효과로 읽을 수 있다.</mark> 이 보고서의 방법과 평가는 모두 무작위 실험 데이터를 전제로 한다.

이 보고서에서 쓰는 기호는 아래와 같다.

| 기호                               | 뜻                                                                  | 출처 표기와의 차이                                                                           |
| ---------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| $x$, $X$                           | 고객 특성 벡터와 그 확률변수                                        |                                                                                              |
| $W$                                | 처치 여부(처치 1, 대조 0)                                           | Jaśkowski & Jaroszewicz (2012)는 $G$(값 $T$, $C$)                                            |
| $Y$, $Y(1)$, $Y(0)$                | 관측 결과, 처치를 받았을 때와 받지 않았을 때의 잠재 결과            |                                                                                              |
| $u(x)$, $\tau(x)$                  | uplift, 조건부 평균 처치 효과                                       |                                                                                              |
| $\mu_1(x)$, $\mu_0(x)$             | 처치군, 대조군 반응 함수 $E[Y(1) \mid X = x]$, $E[Y(0) \mid X = x]$ |                                                                                              |
| 모자(^)                            | 추정값                                                              |                                                                                              |
| 위첨자 1, 0                        | 처치군, 대조군 고객($Y^1_i$, $X^0_i$ 등)                            |                                                                                              |
| $g(x)$                             | X-learner의 가중치                                                  |                                                                                              |
| $Z$, $p$                           | class transformation의 새 레이블, 처치 확률                         |                                                                                              |
| $\pi(x)$, $\varphi$                 | DR-learner의 처치 확률 $P(W = 1 \mid X = x)$, pseudo-outcome      |                                                                                              |
| $Y^T_t$, $Y^C_t$, $N^T_t$, $N^C_t$ | 예측 uplift 상위 $t$명 안의 처치군·대조군 응답자 수와 고객 수       | 평가 절에서만 쓰며, $Y$가 개인의 결과가 아니라 응답자 수다                                   |
| $f(t)$, $q(t)$                     | uplift curve, Qini curve                                            | Gutierrez & Gérardy (2017)는 Qini curve를 $g(t)$로 쓴다. X-learner의 $g$와 겹쳐 $q$로 바꿨다 |

## 고객 네 유형

고객은 처치를 받았을 때와 받지 않았을 때 각각 살지 말지에 따라 네 유형으로 나뉜다 (Radcliffe, 2007). 처치를 받으면 살 확률이 오르는 고객이 Persuadables다. 처치가 거의 영향을 주지 않는 고객은 Immovables이고, 이들은 어느 쪽이든 사는 Sure Things와 어느 쪽이든 사지 않는 Lost Causes로 다시 나뉜다. 처치를 받으면 오히려 덜 사는 고객은 Sleeping Dogs다.

| 유형          | 처치를 받으면 | 처치를 받지 않으면 | 처치 효과 $\tau_i$ |
| ------------- | ------------- | ------------------ | ------------------ |
| Persuadables  | 구매          | 비구매             | 양수               |
| Sure Things   | 구매          | 구매               | 0                  |
| Lost Causes   | 비구매        | 비구매             | 0                  |
| Sleeping Dogs | 비구매        | 구매               | 음수               |

표: 두 잠재 결과의 조합으로 본 고객 유형 (Radcliffe, 2007).

<mark>증분 매출을 최소 비용으로 늘리려면 Persuadables만 고르는 것이 이상적이다</mark> (Radcliffe, 2007). Sure Things와 Lost Causes에 쓴 비용은 매출을 바꾸지 못하고, Sleeping Dogs에 쓴 비용은 매출을 줄인다. <mark>응답 모델은 처치 후 살 확률이 높은 Persuadables와 Sure Things를 함께 고르므로, Sure Things에 예산이 샌다.</mark> 앞 절의 상위 30% 사례가 이 경우다.

이 분류는 개념상의 것이어서, 한 고객이 어느 유형인지는 관측할 수 없다 (Radcliffe, 2007). 같은 고객을 동시에 처치하고 처치하지 않을 수 없기 때문이다. 그래서 <mark>uplift 모델은 유형을 맞히는 대신 $\tau(x)$를 추정해 Persuadables일 가능성이 높은 고객을 위로 올리는 순서를 만든다.</mark>

## 대표 방법

대표 방법은 두 갈래다. 하나는 기존 회귀·분류 모델을 조합해 $\tau(x)$를 추정하는 메타러너(meta-learner)로, S-learner, T-learner, X-learner가 여기에 든다 (Künzel et al., 2019). 메타러너에는 처치 확률로 보정한 대리 결과를 학습하는 DR-learner도 든다 (Kennedy, 2023). 다른 하나는 레이블을 바꿔 분류기 하나로 uplift를 학습하는 class transformation이다 (Jaśkowski & Jaroszewicz, 2012). 이 밖에 트리의 분기 기준을 바꿔 uplift를 직접 학습하는 uplift random forest가 있다 (Rzepakowski & Jaroszewicz, 2012; Guelman et al., 2015). Künzel et al. (2019)의 시뮬레이션에서 어느 메타러너도 모든 경우에 가장 좋지는 않았으므로, 방법은 데이터의 조건에 맞춰 고른다. 절 끝의 비교 표에 조건을 모았다.

### S-learner

S-learner는 <mark>처치 여부 $W$를 다른 특성과 똑같은 입력 하나로 넣어 모델 하나를 전체 데이터에 학습한다</mark> (Künzel et al., 2019). 이 모델이 $\mu(x, w) = E[Y \mid X = x, W = w]$를 추정하면, <mark>같은 $x$에 $w$만 1과 0으로 바꿔 넣은 두 예측의 차이를 처치 효과로 쓴다.</mark>

$$
\hat\tau_S(x) = \hat\mu(x, 1) - \hat\mu(x, 0)
$$

S-learner는 $W$를 특별히 다루지 않으므로, lasso나 랜덤 포레스트 같은 모델은 $W$를 변수로 고르지 않거나 분기에 쓰지 않아 처치를 아예 무시할 수 있다 (Künzel et al., 2019). 처치 효과가 대부분 0인 데이터에서는 이것이 이점이다. 그렇지 않은 데이터에서는 추정이 0 쪽으로 치우친다.

### T-learner

<mark>T-learner는 대조군 데이터로 $\mu_0$를, 처치군 데이터로 $\mu_1$을 따로 학습한 뒤 두 예측의 차이를 처치 효과로 쓴다</mark> (Künzel et al., 2019). Gutierrez & Gérardy (2017)는 같은 방법을 <mark>Two-Model approach</mark>라 부른다.

$$
\hat\tau_T(x) = \hat\mu_1(x) - \hat\mu_0(x)
$$

T-learner의 강점은 단순함이다 (Gutierrez & Gérardy, 2017). 두 군을 따로 학습하므로 랜덤 포레스트나 XGBoost 같은 기존 예측 모델을 그대로 쓸 수 있다. 약점은 <mark>두 모델이 각각 결과를 맞히는 데 집중해서, 결과보다 훨씬 작은 uplift 신호를 놓치기 쉽다</mark>는 점이다. Künzel et al. (2019)는 <mark>두 군을 합치지 않는 T-learner가 처치 효과가 단순할 때 불리하고, 처치 효과가 복잡해 두 반응 함수에 공통된 흐름이 없을 때 특히 잘한다</mark>고 정리한다.

### X-learner

X-learner는 T-learner의 두 모델로 개인별 처치 효과를 대신 만든 뒤, 그것을 다시 학습한다 (Künzel et al., 2019). 단계는 셋이다.

1. T-learner처럼 $\hat\mu_0$, $\hat\mu_1$을 학습한다.
2. 처치군 고객에게는 $\tilde D^1_i = Y^1_i - \hat\mu_0(X^1_i)$, 대조군 고객에게는 $\tilde D^0_i = \hat\mu_1(X^0_i) - Y^0_i$를 계산한다. 이 값을 대체 처치 효과(imputed treatment effect)라 한다. 처치군 고객은 처치를 받은 결과가 있으므로 받지 않았을 결과만 대조군 모델로 채우고, 대조군 고객은 그 반대다. 그다음 각 군에서 대체 처치 효과를 반응 변수로 삼아 $\hat\tau_1(x)$와 $\hat\tau_0(x)$를 학습한다.
3. 가중치 $g(x) \in [0, 1]$로 두 추정을 섞는다.

$$
\hat\tau_X(x) = g(x)\,\hat\tau_0(x) + (1 - g(x))\,\hat\tau_1(x)
$$

Künzel et al. (2019)는 $g$로 성향 점수(propensity score, 고객이 처치군에 배정될 확률)의 추정값을 쓰는 것이 좋았고, 처치군이 대조군보다 매우 크거나 작으면 $g$를 1이나 0으로 두어도 된다고 쓴다. X-learner는 한 군(보통 대조군)이 다른 군보다 훨씬 클 때 특히 효과적이다. 큰 군으로 학습한 정확한 모델이 작은 군 고객의 대체 처치 효과를 만들어 주므로, 작은 군의 정보 부족이 덜 문제가 되는 것으로 이해할 수 있다.

### Class transformation

Class transformation은 <mark>처치 여부와 결과를 합친 새 이진 레이블 $Z$를 만들고, 일반 분류기로 $P(Z = 1 \mid X)$를 학습해 uplift로 바꾼다</mark> (Jaśkowski & Jaroszewicz, 2012). $Z$는 처치군에서 산 고객과 대조군에서 사지 않은 고객이 1이고, 나머지가 0이다.

$$
Z = W Y + (1 - W)(1 - Y)
$$

이 레이블에서 uplift가 나오는 과정은 네 단계다 (Jaśkowski & Jaroszewicz, 2012).

1. 전확률 법칙으로 처치군과 대조군을 나눈다: $P(Z = 1 \mid X) = P(Z = 1 \mid X, W = 1) P(W = 1 \mid X) + P(Z = 1 \mid X, W = 0) P(W = 0 \mid X)$.

2. 처치군에서는 $Z = Y$, 대조군에서는 $Z = 1 - Y$이므로 $P(Z = 1 \mid X) = P(Y = 1 \mid X, W = 1) P(W = 1 \mid X) + P(Y = 0 \mid X, W = 0) P(W = 0 \mid X)$이다.

3. 처치 확률이 1/2이라고 가정한다. 무작위 배정이면 처치 확률이 $X$와 무관하므로 $P(W = 1 \mid X) = P(W = 0 \mid X) = 1/2$이다. 이 값과 $P(Y = 0 \mid X, W = 0) = 1 - P(Y = 1 \mid X, W = 0)$을 2단계 식에 넣는다.

   $$
   P(Z = 1 \mid X) = \tfrac{1}{2} P(Y = 1 \mid X, W = 1) + \tfrac{1}{2}\,\bigl(1 - P(Y = 1 \mid X, W = 0)\bigr)
   $$

4. 양변에 2를 곱하고 1을 빼면 $2P(Z = 1 \mid X) - 1 = P(Y = 1 \mid X, W = 1) - P(Y = 1 \mid X, W = 0)$, 즉 $u(x)$다.

이 방법은 Two-Model approach보다 잘하는 경우가 많으면서도 단순해서 널리 쓰인다 (Gutierrez & Gérardy, 2017). 다만 <mark>결과가 이진이어야 하고 처치군과 대조군의 크기가 같아야 한다는 두 가정이 제약이다</mark>. <mark>처치 확률이 1/2이 아니면 3단계가 성립하지 않으므로, 원 논문은 학습 데이터를 재가중하거나 재표집해 가정을 맞추라고 한다</mark> (Jaśkowski & Jaroszewicz, 2012).

두 가정을 불균형 배정과 연속 결과로 넓힌 것이 transformed outcome이다 (Athey & Imbens, 2016; Gutierrez & Gérardy, 2017). 처치 확률을 $p$라 하면 결과를 $Y^*_i = Y_i (W_i - p) / (p(1 - p))$로 바꾼다 (Athey & Imbens, 2016). 이 값의 조건부 기댓값이 $\tau(x)$이므로, 일반 회귀 모델로 $Y^*$를 학습하면 uplift를 추정할 수 있다.

이 성질은 다음처럼 확인할 수 있다. $W = 1$이면 $Y^* = Y / p$, $W = 0$이면 $Y^* = -Y / (1 - p)$다. 무작위 배정이면 $X$를 고정해도 $W = 1$일 확률이 $p$이므로, 두 경우를 확률로 가중해 더한다.

$$
E[Y^* \mid X] = p \cdot \frac{E[Y \mid X, W = 1]}{p} - (1 - p) \cdot \frac{E[Y \mid X, W = 0]}{1 - p} = E[Y \mid X, W = 1] - E[Y \mid X, W = 0]
$$

무작위 배정이면 $W$가 잠재 결과와 독립이어서 우변의 두 항이 $E[Y(1) \mid X]$, $E[Y(0) \mid X]$와 같으므로 $E[Y^* \mid X] = \tau(X)$다.

### DR-learner

DR-learner는 <mark>결과 모델과 처치 확률을 함께 써서 고객마다 pseudo-outcome(대리 결과) $\varphi$를 만들고, 그 값을 $X$에 회귀해 $\tau(x)$를 추정한다</mark> (Kennedy, 2023). $\varphi$는 고객 한 명의 처치 효과를 대신하는 값이다. 처치 확률 $\pi(x) = P(W = 1 \mid X = x)$는 무작위 실험이면 설계로 정해진 값이다.

$$
\varphi = \hat\mu_1(X) - \hat\mu_0(X) + \frac{W\,(Y - \hat\mu_1(X))}{\hat\pi(X)} - \frac{(1 - W)\,(Y - \hat\mu_0(X))}{1 - \hat\pi(X)}
$$

앞 두 항은 T-learner의 추정이고, 뒤 두 항은 그 추정이 관측 결과와 어긋난 만큼을 처치 확률로 나눠 되돌리는 보정이다. 무작위 실험에서 $\hat\pi = \pi$이면 $E[\varphi \mid X] = \tau(X)$이고, 이는 결과 모델이 틀려도 성립한다. 단계는 셋이다.

1. 셋째 항: $W = 1$일 확률이 $\pi(X)$이고 그때만 항이 0이 아니므로 $E\left[\frac{W(Y - \hat\mu_1(X))}{\pi(X)} \,\middle|\, X\right] = \pi(X) \cdot \frac{E[Y \mid X, W = 1] - \hat\mu_1(X)}{\pi(X)} = \mu_1(X) - \hat\mu_1(X)$다.
2. 넷째 항: 같은 방법으로 $W = 0$일 확률 $1 - \pi(X)$를 곱하면 $\mu_0(X) - \hat\mu_0(X)$다.
3. 세 값을 더한다: $\hat\mu_1 - \hat\mu_0 + (\mu_1 - \hat\mu_1) - (\mu_0 - \hat\mu_0) = \mu_1(X) - \mu_0(X)$이고, 무작위 배정이면 이것이 $\tau(X)$다(앞 절의 transformed outcome과 같은 이유).

결과 모델을 0으로 두면 $\varphi$는 앞 절의 transformed outcome $Y^*$와 같다. 결과 모델이 $Y$를 잘 맞힐수록 $Y - \hat\mu$가 작아져 처치 확률로 나누는 항의 분산이 줄어든다. 그래서 DR-learner는 transformed outcome의 큰 분산을 결과 모델로 줄인 방법으로 읽을 수 있다.

Kennedy (2023)는 결과 모델과 처치 확률을 한 표본에서 학습하고 $\varphi$의 회귀는 다른 표본에서 하라고 한다(Algorithm 1). 두 표본의 역할을 바꿔 한 번 더 하고 평균하는 cross-fitting도 쓸 수 있다. 같은 표본을 쓰면 결과 모델이 외운 잡음이 $\varphi$에 들어간다. 이 논문에서 doubly robust는 DR-learner의 오차가 이상적인 추정의 오차에서 처치 확률 오차와 결과 모델 오차의 곱만큼만 벗어난다는 뜻이다. 두 오차가 모두 작지 않아도 곱은 작을 수 있다.

### Uplift random forest

Uplift random forest는 <mark>처치군과 대조군의 결과 분포 차이가 커지도록 나누는 uplift tree를 여러 개 만들어 예측을 평균한다</mark> (Guelman et al., 2014; Guelman et al., 2015). 부품 모델 없이 트리가 직접 uplift를 추정한다.

Uplift tree의 분기 기준은 일반 결정 트리와 다르다. 일반 트리는 자식 노드 안의 결과가 고르게 되도록 나누지만, uplift tree는 자식 노드에서 처치군과 대조군의 결과 분포가 서로 달라지도록 나눈다 (Rzepakowski & Jaroszewicz, 2012). 분포 차이는 KL divergence, 제곱 유클리드 거리, 카이제곱 divergence로 재고, 나누기 전보다 차이가 얼마나 커졌는지를 이득으로 쓴다. 잎의 uplift는 그 잎 안 처치군 응답률에서 대조군 응답률을 뺀 값이다. 원 논문은 처치가 여럿인 경우로 넓혀, 각 처치와 대조군의 차이와 처치끼리의 차이를 가중합한 분포 차이를 쓴다(5절).

Forest는 트리마다 학습 데이터의 일부를 뽑고, 분기마다 특성 일부만 후보로 두어 트리들이 서로 달라지게 한다 (Guelman et al., 2014). 같은 저자들은 일반 random forest의 bootstrap 대신 비복원으로 일부를 뽑았다. 이 프로젝트가 쓰는 `causalml`의 `UpliftRandomForestClassifier`는 처치 군을 여럿 받아 처치마다 uplift를 내고, 분기 기준으로 KL, ED, Chi 등을 고른다 (causalml, 2026).

### 비교

| 방법                 | 가정                     | 강점                                | 약점                             | 언제 쓰나                              |
| -------------------- | ------------------------ | ----------------------------------- | -------------------------------- | -------------------------------------- |
| S-learner            | 없음(무작위 실험)        | 모델 하나, 효과가 대부분 0이면 유리 | 추정이 0 쪽으로 치우칠 수 있음   | 처치 효과가 대부분 0일 때              |
| T-learner            | 없음(무작위 실험)        | 단순, 기존 모델 그대로 사용         | 작은 uplift 신호를 놓치기 쉬움   | 두 군의 반응이 크게 다를 때, 비교 기준 |
| X-learner            | 없음(무작위 실험)        | 군 크기가 불균형해도 강함           | 모델 넷과 가중치 $g$를 정해야 함 | 한 군이 다른 군보다 훨씬 클 때         |
| Class transformation | 이진 결과, 처치 확률 1/2 | 분류기 하나로 바로 학습             | 가정이 깨지면 재가중 필요        | 균형 잡힌 이진 결과 실험               |
| Transformed outcome  | 처치 확률 $p$를 앎       | 불균형과 연속 결과에도 사용         | 변환한 결과의 분산이 큼          | 불균형 실험, 연속 결과                 |
| DR-learner           | 처치 확률을 앎(무작위 실험) | transformed outcome보다 분산이 작음 | 표본을 나눠 결과 모델 둘과 최종 회귀를 학습해야 함 | 처치 확률을 아는 실험에서 분산을 줄일 때 |
| Uplift random forest | 없음(무작위 실험)        | 부품 모델 없이 여러 처치를 직접 다룸 | 잎마다 두 군이 있어야 해 데이터가 많이 듦 | 처치가 여럿인 실험                     |

표: 대표 방법 비교 (Künzel et al., 2019; Gutierrez & Gérardy, 2017; Jaśkowski & Jaroszewicz, 2012; Athey & Imbens, 2016; Kennedy, 2023; Rzepakowski & Jaroszewicz, 2012). Transformed outcome 행의 분산은 $Y^*$가 $1/p$, $1/(1 - p)$배로 커지는 데서 온 판단이다. Uplift random forest 행의 약점은 잎마다 처치군과 대조군의 응답률을 따로 구하는 데서 온 판단이다.

## 평가

Uplift 모델은 예측값과 정답을 고객마다 비교해 평가할 수 없다 (Surry & Radcliffe, 2011). <mark>개인의 진짜 uplift가 관측되지 않기 때문이다</mark>. <mark>그래서 모델이 매긴 예측 uplift 순서대로 고객을 잘라, 그 묶음 안에서 처치군과 대조군의 결과를 비교한다</mark> (Gutierrez & Gérardy, 2017).

### Uplift curve와 Qini curve

두 곡선 모두 시험 데이터를 예측 uplift가 큰 순서로 정렬하고, 상위 $t$명 안의 처치군·대조군 응답자 수($Y^T_t$, $Y^C_t$)와 고객 수($N^T_t$, $N^C_t$)로 계산한다 (Gutierrez & Gérardy, 2017).

<mark>Uplift curve는 상위 $t$명 안의 처치군 응답률과 대조군 응답률의 차이에 그 인원을 곱한 값이다</mark> (Gutierrez & Gérardy, 2017). 응답률 차이는 고객 한 사람의 구매 확률이 처치로 얼마나 오르는가이고, 인원을 곱하면 묶음 전체의 증분 응답자 수가 된다.

$$
f(t) = \left( \frac{Y^T_t}{N^T_t} - \frac{Y^C_t}{N^C_t} \right) (N^T_t + N^C_t)
$$

Qini curve는 Radcliffe가 제안한 곡선으로, 대조군 응답자 수에 $N^T_t / N^C_t$를 곱해 처치군 크기 기준으로 바꾼 뒤 처치군 응답자 수에서 뺀다 (Gutierrez & Gérardy, 2017). 응답자 수는 군 크기에 비례하므로, 크기를 맞추지 않고 빼면 증분이 아니라 두 군의 크기 차이가 섞이기 때문이다.

$$
q(t) = Y^T_t - Y^C_t \frac{N^T_t}{N^C_t}
$$

두 곡선은 $f(t) = q(t)(N^T_t + N^C_t) / N^T_t$로 이어진다 (Gutierrez & Gérardy, 2017). $q(t)$를 $N^T_t$로 나누면 응답률 차이가 되고, 여기에 인원 $N^T_t + N^C_t$를 곱하면 $f(t)$이기 때문이다. 이 계수 $(N^T_t + N^C_t)/N^T_t$는 상위 $t$명 안의 처치군 비율에 따라 바뀌며, 두 군이 균형이면 2 근처라서 두 곡선은 거의 두 배 비례한다.

예를 들어 상위 100명에 처치군 60명(응답 12명)과 대조군 40명(응답 4명)이 있으면 $q = 12 - 4 \times 60 / 40 = 6$이고, $f = (12/60 - 4/40) \times 100 = 10$이다. 관계식으로도 $6 \times 100 / 60 = 10$이 나온다. Qini는 "처치군 60명 기준으로 6명이 더 샀다"를, uplift curve는 "100명 모두에게 처치했다면 10명이 더 샀을 것"을 말한다.

### Qini 계수와 AUUC

곡선 하나를 숫자 하나로 줄여 모델을 비교할 때는 곡선 아래 면적을 쓴다. Qini 계수(Qini coefficient)는 누적 증분 곡선 아래 면적에서 무작위 대각선 아래 면적을 뺀 값, 즉 무작위로 고객을 골랐을 때보다 평균적으로 얼마나 더 나은지다 (Surry & Radcliffe, 2011). 이 보고서에서는 누적 증분 곡선으로 앞의 Qini curve $q(t)$를 쓴다. 무작위 대각선은 고객을 무작위 순서로 골랐을 때의 곡선이므로, Qini 계수가 0이면 모델의 순서가 무작위와 다르지 않다. 원 정의는 이 값을 가장 좋은 순서일 때의 값으로 나눠 정규화하므로, 계수는 최선의 모델에 견준 비율로 읽는다.

AUUC(area under the uplift curve)는 uplift curve나 Qini curve 아래 면적이다 (Devriendt et al., 2022). 문헌에 따라 무작위 기준선의 면적을 빼기도 하고 빼지 않기도 한다. 같은 데이터에서 모델끼리 비교할 때는 기준선이 상수라 순위가 같지만, 다른 문헌의 수치와 비교할 때는 어느 곡선을 썼는지와 기준선을 뺐는지부터 맞춰야 한다.

## Hillstrom 데이터 구조

Hillstrom 데이터는 Kevin Hillstrom이 2008년 MineThatData 블로그에 공개한 이메일 마케팅 무작위 실험 데이터다 (Hillstrom, 2008). 지난 12개월 안에 구매한 고객 64,000명을 무작위로 셋으로 나눠, 1/3에는 남성 상품 이메일을, 1/3에는 여성 상품 이메일을 보내고, 나머지 1/3에는 보내지 않았다. 결과는 발송 뒤 2주 동안 추적했다.

| 변수       | 정의                             |
| ---------- | -------------------------------- |
| visit      | 2주 안에 웹사이트를 방문했으면 1 |
| conversion | 2주 안에 상품을 구매했으면 1     |
| spend      | 2주 안에 쓴 금액(달러)           |

표: 결과 변수 (Hillstrom, 2008).

| 변수            | 정의                                               | 역할 |
| --------------- | -------------------------------------------------- | ---- |
| recency         | 마지막 구매 뒤 지난 개월 수                        | 특성 |
| history_segment | 지난 1년 구매 금액의 구간                          | 특성 |
| history         | 지난 1년 실제 구매 금액(달러)                      | 특성 |
| mens            | 지난 1년 남성 상품 구매 여부(1/0)                  | 특성 |
| womens          | 지난 1년 여성 상품 구매 여부(1/0)                  | 특성 |
| zip_code        | 우편번호 구분(Urban, Suburban, Rural)              | 특성 |
| newbie          | 지난 12개월 안의 신규 고객 여부(1/0)               | 특성 |
| channel         | 지난 1년 구매 채널                                 | 특성 |
| segment         | 받은 이메일(Mens E-Mail, Womens E-Mail, No E-Mail) | 처치 |

표: 특성 여덟 개와 처치 변수 (Hillstrom, 2008).

처치가 두 종류라서, 대표 방법 절의 이진 처치 방법에 넣으려면 $W$를 먼저 정해야 한다. 결과는 visit이나 conversion을 이진 $Y$로 쓴다. $W$를 만드는 구성은 둘이다.

- 이메일 한 종류만 남김: 한 이메일 군과 No E-Mail 군이 각각 1/3씩이라 처치 확률이 1/2이므로, class transformation을 그대로 쓴다 (Jaśkowski & Jaroszewicz, 2012).
- 두 이메일 군을 합침: 처치 확률이 2/3이므로, class transformation에는 재가중(Jaśkowski & Jaroszewicz, 2012)이나 transformed outcome(Athey & Imbens, 2016)이 필요하다.

S·T·X-learner, DR-learner와 Qini curve는 처치 확률이 1/2이라는 가정을 쓰지 않으므로 어느 구성에서도 쓸 수 있다. DR-learner는 설계로 정해진 처치 확률(1/2 또는 2/3)을 그대로 쓴다. Uplift random forest는 이진 $W$를 만들지 않고 세 군을 그대로 받을 수 있다 (Rzepakowski & Jaroszewicz, 2012).

## 참고문헌

- Athey, S., & Imbens, G. W. (2016). Recursive partitioning for heterogeneous causal effects. Proceedings of the National Academy of Sciences, 113(27), 7353-7360. https://doi.org/10.1073/pnas.1510489113
- causalml. (2026). UpliftRandomForestClassifier, causalml 0.18.0 documentation. Retrieved 2026-11-24, from https://causalml.readthedocs.io/en/stable/causalml.html
- Devriendt, F., Van Belle, J., Guns, T., & Verbeke, W. (2022). Learning to rank for uplift modeling. IEEE Transactions on Knowledge and Data Engineering, 34(10), 4888-4904. https://doi.org/10.1109/TKDE.2020.3048510
- Gutierrez, P., & Gérardy, J.-Y. (2017). Causal inference and uplift modelling: A review of the literature. Proceedings of Machine Learning Research, 67, 1-13. https://proceedings.mlr.press/v67/gutierrez17a.html
- Hillstrom, K. (2008, March 20). The MineThatData e-mail analytics and data mining challenge. MineThatData. https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html
- Guelman, L., Guillén, M., & Pérez-Marín, A. M. (2014). Optimal personalized treatment rules for marketing interventions: A review of methods, a new proposal, and an insurance case study (UB Riskcenter Working Paper 2014/06). University of Barcelona. http://www.ub.edu/rfa/research/WP/UBriskcenterWP201406.pdf
- Guelman, L., Guillén, M., & Pérez-Marín, A. M. (2015). Uplift random forests. Cybernetics and Systems, 46(3-4), 230-248. https://doi.org/10.1080/01969722.2015.1012892
- Holland, P. W. (1986). Statistics and causal inference. Journal of the American Statistical Association, 81(396), 945-960. https://doi.org/10.1080/01621459.1986.10478354
- Jaśkowski, M., & Jaroszewicz, S. (2012). Uplift modeling for clinical trial data. ICML 2012 Workshop on Machine Learning for Clinical Data Analysis. https://people.cs.pitt.edu/~milos/icml_clinicaldata_2012/Papers/Oral_Jaroszewitz_ICML_Clinical_2012.pdf
- Kennedy, E. H. (2023). Towards optimal doubly robust estimation of heterogeneous causal effects. Electronic Journal of Statistics, 17(2), 3008-3049. https://doi.org/10.1214/23-EJS2157
- Künzel, S. R., Sekhon, J. S., Bickel, P. J., & Yu, B. (2019). Metalearners for estimating heterogeneous treatment effects using machine learning. Proceedings of the National Academy of Sciences, 116(10), 4156-4165. https://doi.org/10.1073/pnas.1804597116
- Radcliffe, N. J. (2007). Generating incremental sales: Maximizing the incremental impact of cross-selling, up-selling and deep-selling through uplift modelling [White paper]. Stochastic Solutions. https://stochasticsolutions.com/pdf/CrossSell.pdf
- Radcliffe, N. J., & Surry, P. D. (2011). Real-world uplift modelling with significance-based uplift trees (Portrait Technical Report TR-2011-1). Stochastic Solutions. https://stochasticsolutions.com/pdf/sig-based-up-trees.pdf
- Rzepakowski, P., & Jaroszewicz, S. (2012). Decision trees for uplift modeling with single and multiple treatments. Knowledge and Information Systems, 32(2), 303-327. https://doi.org/10.1007/s10115-011-0434-0
- Rubin, D. B. (1974). Estimating causal effects of treatments in randomized and nonrandomized studies. Journal of Educational Psychology, 66(5), 688-701. https://doi.org/10.1037/h0037350
- Surry, P. D., & Radcliffe, N. J. (2011). Quality measures for uplift models. KDD 2011. https://stochasticsolutions.com/pdf/kdd2011late.pdf
