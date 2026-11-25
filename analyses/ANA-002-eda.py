import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo

    from uplift.db import TREATMENTS, load_frame
    from uplift.eda import (
        bootstrap_mean_ci,
        category_shares,
        cramers_v_matrix,
        numeric_summary,
        outcome_summary,
        product_segment,
        segment_profile,
        share_table,
        spearman_matrix,
    )
    from uplift.plots import (
        association_heatmaps,
        buyer_spend_ecdf,
        buyer_spend_plot,
        category_share_plot,
        numeric_distribution_plot,
    )

    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "ANA-002"
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(root / "data" / "uplift.duckdb"), read_only=True) as con:
        df = load_frame(con, "train")
    df["treatment"] = df["treatment_id"].map(
        dict(zip(TREATMENTS["treatment_id"], TREATMENTS["name"], strict=True))
    )
    return (
        association_heatmaps,
        bootstrap_mean_ci,
        buyer_spend_ecdf,
        buyer_spend_plot,
        category_share_plot,
        category_shares,
        cramers_v_matrix,
        df,
        mo,
        numeric_distribution_plot,
        numeric_summary,
        out,
        outcome_summary,
        product_segment,
        segment_profile,
        share_table,
        spearman_matrix,
    )


@app.cell
def _(df, mo):
    mo.md(f"""
    # ANA-002 분포 EDA

    학습 세트({len(df):,}행)에서 변수 하나하나의 분포, 변수끼리의 관계, 처치군별 결과 분포를 보고, 모델 입력의 변수 처리와 결과 변수의 특이점을 정한다. 고객 세그먼트와 메일 반응은 ANA-003에서 본다.

    1. 공변량 분포
    2. 결과 변수 분포
    3. 변수 사이의 관계
    4. 처치군별 결과 분포
    """)
    return


@app.cell
def _(
    category_share_plot,
    category_shares,
    df,
    mo,
    numeric_distribution_plot,
    numeric_summary,
    out,
    product_segment,
    share_table,
):
    numeric = numeric_summary(df, ["recency", "history"])
    shares = category_shares(
        df, ["history_segment", "zip_code", "channel", "mens", "womens", "newbie"]
    )
    product_mix = category_shares(df.assign(product=product_segment(df)), ["product"]).set_index(
        "level"
    )
    recency_by_newbie = share_table(df, "newbie", "recency")
    numeric.to_csv(out / "tables" / "numeric_summary.csv", index=False)
    shares.to_csv(out / "tables" / "category_shares.csv", index=False)
    product_mix.to_csv(out / "tables" / "product_shares.csv")
    recency_by_newbie.to_csv(out / "tables" / "recency_by_newbie.csv")
    numeric_fig = numeric_distribution_plot(df)
    numeric_fig.savefig(out / "figures" / "numeric_distribution.png", dpi=150)
    category_fig = category_share_plot(shares)
    category_fig.savefig(out / "figures" / "category_shares.png", dpi=150)
    history = numeric.set_index("column").loc["history"]
    mo.vstack(
        [
            mo.md("## 1. 공변량 분포"),
            mo.ui.table(numeric.round(3)),
            numeric_fig,
            mo.md(f"""
    - `history`(지난 1년 구매 금액): 고객의 {history["mode_share"]:.1%}가 최솟값 {history["min"]:.2f}에 몰려 있다. 이 값을 빼면 로그 축에서 종 모양이고, 중앙값 {history["p50"]:.0f}, p99 {history["p99"]:.0f}, 최댓값 {history["max"]:.0f}로 오른쪽 꼬리가 길다. 트리 모델은 순서만 쓰므로 변환하지 않는다. 같은 29.99가 결과 `spend`의 최솟값이기도 해서(2절), 최소 주문 금액이나 한 상품의 가격일 수 있다. 데이터로는 확인할 수 없다.
    - `recency`(마지막 구매 뒤 개월 수): 1개월에서 줄다가 9\\~10개월에 다시 높아진다. 9\\~10개월 전에 마지막으로 산 고객이 많다는 뜻이다. 아래 표처럼 신규 고객과 기존 고객에게 같은 모양이 나와, 그 시기에 고객을 많이 모은 것이 아니라 모든 고객의 구매가 몰린 시기(행사나 시즌)였다는 해석과 맞는다. 실험 날짜가 데이터에 없어 어느 행사인지는 알 수 없다.
    """),
            mo.ui.table(recency_by_newbie.reset_index()),
            mo.ui.table(shares.round(4)),
            category_fig,
            mo.md(f"""
    - `mens`, `womens`는 성별이 아니라 지난 1년 동안 남성 상품, 여성 상품을 샀는지다. 남성 상품만 {product_mix.loc["mens_only", "share"]:.1%}, 여성 상품만 {product_mix.loc["womens_only", "share"]:.1%}, 둘 다 {product_mix.loc["both", "share"]:.1%}이고, 둘 다 사지 않은 고객은 없다. 둘 다 산 고객이 있어 두 비율의 합이 100%를 넘는다.
    - `newbie`는 지난 1년 안에 처음 구매한 고객이다. 이 데이터는 지난 1년 안에 구매한 고객만 모았기 때문에 신규 고객이 절반을 차지한다.
    - 작은 범주: `zip_code` Rural, `channel` Multichannel, `history_segment` 상위 두 구간. 세그먼트별 추정이 흔들릴 수 있다.
    """),
        ]
    )
    return


@app.cell
def _(buyer_spend_plot, df, mo, out, outcome_summary):
    outcomes = outcome_summary(df.assign(group="All"), "group")
    outcomes.to_csv(out / "tables" / "outcome_summary.csv", index=False)
    spend_fig = buyer_spend_plot(df["spend"])
    spend_fig.savefig(out / "figures" / "buyer_spend.png", dpi=150)
    row = outcomes.iloc[0]
    mo.vstack(
        [
            mo.md("## 2. 결과 변수 분포"),
            mo.ui.table(outcomes.round(4)),
            spend_fig,
            mo.md(f"""
    - 방문율 {row["visit_rate"]:.3f}, 구매율 {row["conversion_rate"]:.4f}. 구매 고객은 {row["buyers"]:,}명뿐이다.
    - 구매 고객의 `spend`: 중앙값 {row["buyer_p50"]:.1f}, 평균 {row["buyer_spend_mean"]:.1f}, p90 {row["buyer_p90"]:.1f}. 구매 고객의 {row["buyers_at_min_share"]:.0%}가 최솟값 {row["buyer_min"]:.2f}를 썼다.
    - 최댓값 {row["buyer_max"]:.0f}에 {row["buyers_at_max"]}명이 있고 p99도 같은 값이다. 원본이 이 값에서 잘렸을 수 있다. 그렇다면 고액 구매자의 금액은 실제보다 작게 기록돼 있고, 금액 평균의 비교는 고액 쪽 차이를 덜 보인다.
    """),
        ]
    )
    return


@app.cell
def _(
    association_heatmaps,
    cramers_v_matrix,
    df,
    mo,
    out,
    segment_profile,
    share_table,
    spearman_matrix,
):
    spearman = spearman_matrix(
        df, ["recency", "history", "history_segment", "mens", "womens", "newbie"]
    )
    cramers = cramers_v_matrix(
        df, ["history_segment", "recency", "zip_code", "channel", "mens", "womens", "newbie"]
    )
    segment_by_newbie = share_table(df, "newbie", "history_segment")
    segment_by_channel = share_table(df, "channel", "history_segment")
    history_by_newbie = segment_profile(df, "newbie")
    history_by_newbie.to_csv(out / "tables" / "history_by_newbie.csv", index=False)
    segment_by_newbie.to_csv(out / "tables" / "segment_by_newbie.csv")
    segment_by_channel.to_csv(out / "tables" / "segment_by_channel.csv")
    spearman.to_csv(out / "tables" / "spearman.csv")
    cramers.to_csv(out / "tables" / "cramers_v.csv")
    assoc_fig = association_heatmaps(spearman, cramers)
    assoc_fig.savefig(out / "figures" / "associations.png", dpi=150)
    mo.vstack(
        [
            mo.md("## 3. 변수 사이의 관계"),
            assoc_fig,
            mo.ui.table(segment_by_newbie.round(3).reset_index()),
            mo.ui.table(segment_by_channel.round(3).reset_index()),
            mo.md(f"""
    - `history`와 `history_segment`는 Spearman {spearman.loc["history", "history_segment"]:.2f}로 같은 정보다. `history_segment`는 `history`를 구간으로 자른 값이라 모델 입력에는 `history` 하나만 쓴다.
    - `mens`와 `womens`는 Spearman {spearman.loc["mens", "womens"]:.2f}다. 둘 다 0인 고객이 없어서, 한쪽이 0이면 다른 쪽은 반드시 1이다.
    - `history_segment`와 `newbie`(Cramer's V {cramers.loc["history_segment", "newbie"]:.2f}): 기존 고객(`newbie = 0`)은 `history` 최댓값이 {history_by_newbie.set_index("newbie").loc[0, "history_max"]:.0f}이고, 500달러 이상 구간(5\\~7)의 고객은 모두 신규 고객이다(아래 표). 기존 고객의 금액만 500에서 잘린 것으로 보이며, 원본이 그렇게 만들어진 이유는 데이터로 알 수 없다. 그래서 `history`가 500 이상이면 신규 고객이라는 것이 확정되고, 두 변수를 함께 쓰는 모델은 이 경계를 학습한다.
    - `history_segment`와 `channel`(Cramer's V {cramers.loc["history_segment", "channel"]:.2f}): Multichannel 고객은 `history`가 모두 200달러 이상이다(구간 1, 2가 없음). 여러 채널로 산 고객이 구매액이 큰 것은 자연스럽지만, 200 미만이 한 명도 없는 것은 정의에서 온 경계로 보인다.
    - 나머지 쌍은 `mens`·`womens`를 빼면 Cramer's V가 0.13 이하로, 서로 거의 독립이다.
    """),
        ]
    )
    return


@app.cell
def _(bootstrap_mean_ci, buyer_spend_ecdf, df, mo, out, outcome_summary):
    by_treatment = outcome_summary(df, "treatment")
    buyer_means = bootstrap_mean_ci(
        {
            name: df.loc[(df["treatment"] == name) & (df["spend"] > 0), "spend"].to_numpy()
            for name in ["Mens E-Mail", "Womens E-Mail", "No E-Mail"]
        }
    )
    by_treatment.to_csv(out / "tables" / "outcome_by_treatment.csv", index=False)
    buyer_means.to_csv(out / "tables" / "buyer_spend_mean_ci.csv", index=False)
    ecdf_fig = buyer_spend_ecdf(df, "treatment")
    ecdf_fig.savefig(out / "figures" / "buyer_spend_ecdf.png", dpi=150)
    diff = buyer_means.set_index("group").loc["Mens E-Mail - Womens E-Mail"]
    mo.vstack(
        [
            mo.md("## 4. 처치군별 결과 분포"),
            mo.ui.table(by_treatment.round(4)),
            ecdf_fig,
            mo.ui.table(buyer_means.round(2)),
            mo.md(f"""
    - 구매 고객 1명당 금액의 남성용 대 여성용 차이는 {diff["mean"]:.1f}이고, 부트스트랩 95% 구간이 {diff["ci_low"]:.1f}\\~{diff["ci_high"]:.1f}로 0을 포함한다. 구매 고객이 군마다 100\\~200명이라 이 비교로는 어느 쪽이 많이 쓰는지 가를 수 없다.
    - 이 비교는 처치 뒤에 구매로 걸러진 고객끼리라 처치 효과가 아니다. 군별 구매 고객의 구성이 다를 수 있다. 인과 비교는 ANA-003에서 전체 고객의 `spend` 문턱 초과 확률로 한다.
    """),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
