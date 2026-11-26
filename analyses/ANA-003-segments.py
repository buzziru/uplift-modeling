import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo
    import pandas as pd

    from uplift.db import TREATMENTS, load_frame
    from uplift.eda import (
        buyer_sample_size,
        effects_below_zero,
        funnel_ratio_ci,
        incremental_composition,
        product_segment,
        profile_above_floor,
        segment_effects,
        segment_profile,
        share_table,
        stacked_by_segment,
        threshold_effects,
    )
    from uplift.plots import ecdf_by_group, interval_plot, share_heatmap

    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "ANA-003"
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(root / "data" / "uplift.duckdb"), read_only=True) as con:
        df = load_frame(con, "train")
    df["treatment"] = df["treatment_id"].map(
        dict(zip(TREATMENTS["treatment_id"], TREATMENTS["name"], strict=True))
    )
    df["product"] = product_segment(df)
    segments = ["product", "channel", "zip_code", "newbie", "history_segment"]
    return (
        buyer_sample_size,
        df,
        effects_below_zero,
        ecdf_by_group,
        funnel_ratio_ci,
        incremental_composition,
        interval_plot,
        mo,
        out,
        pd,
        profile_above_floor,
        segment_effects,
        segment_profile,
        segments,
        share_heatmap,
        share_table,
        stacked_by_segment,
        threshold_effects,
    )


@app.cell
def _(df, mo):
    mo.md(f"""
    # ANA-003 고객 세그먼트와 메일 반응

    고객과 상품에 대한 질문을 던지고, 학습 세트({len(df):,}행)가 그 질문에 어디까지 답하는지 본다. 질문마다 가설, 데이터가 보여 주는 것, 데이터로 답할 수 없는 것을 함께 적는다. ANA-002에서 본 잘림과 정의 경계(`artifacts/ANA-002/summary.md`)를 해석에 반영한다.

    구매 상품 세그먼트(`product`)는 `mens`, `womens`를 남성 상품만(`mens_only`), 여성 상품만(`womens_only`), 둘 다(`both`)로 묶은 값이다. 둘 다 사지 않은 고객은 없다. 한 종류만 산 고객의 성별은 그 상품의 성별로 추정할 수 있지만 확정할 수는 없다.

    - A. 고객은 어떻게 구성되어 있나
    - B. 메일이 없을 때 누가 방문하고 사나(대조군)
    - C. 메일에 누가 반응했나
    - D. 담당자 질문: 여성용이 나은 고객군, 고액 구매, 지금 데이터로 답할 수 없는 질문
    - E. M2·M3에 넘길 가설

    C·D의 차이는 수십 개 비교 가운데 하나라 우연히 커 보일 수 있다. 판정하지 않고 95% 구간과 함께 가설로 둔다.
    """)
    return


@app.cell
def _(df, ecdf_by_group, mo, out, segment_profile):
    profile = segment_profile(df, "product")
    profile.to_csv(out / "tables" / "product_profile.csv", index=False)
    history_fig = ecdf_by_group(df, "history", "product", "history by product segment")
    history_fig.savefig(out / "figures" / "history_by_product.png", dpi=150)
    p = profile.set_index("product")
    mo.vstack(
        [
            mo.md("""
    ## A1. 두 종류를 모두 산 고객은 한 종류만 산 고객보다 많이 사는가

    가설: 남성 상품과 여성 상품을 함께 사는 고객은 자기 것만이 아니라 가족의 것을 사는 사람(배우자, 자녀, 따로 사는 부모의 것을 대신 사는 사람)일 수 있다. 그렇다면 한 종류만 사는 고객보다 지난 1년 구매액이 클 것이다.
    """),
            mo.ui.table(profile.round(3)),
            history_fig,
            mo.md(f"""
    - 데이터가 보여 주는 것: 둘 다 산 고객의 `history` 중앙값은 {p.loc["both", "history_median"]:.0f}로, 남성 상품만({p.loc["mens_only", "history_median"]:.0f}), 여성 상품만({p.loc["womens_only", "history_median"]:.0f})의 세 배가 넘는다. 신규 고객 비율({p.loc["both", "newbie_share"]:.0%})과 Multichannel 비율({p.loc["both", "multichannel_share"]:.0%})도 높다.
    - 주의할 점: 둘 다 산 고객의 `history` 최솟값은 {p.loc["both", "history_min"]:.2f}이고, 그 아래인 고객이 한 명도 없다. 두 종류를 사려면 적어도 두 개를 사야 하므로 구매액이 큰 것의 일부는 정의에서 나온다. 다만 하한이 29.99의 약 일곱 배라, 원본을 만들 때 둘 다 산 고객에게 따로 정한 경계로 보인다(Multichannel의 200 하한과 같은 꼴). 한 종류만 산 고객 중 이 하한 이상인 고객만 비교해도 차이가 남는지는 아래 표로 본다.
    - 남성 상품만 산 고객과 여성 상품만 산 고객은 `history` 분포가 거의 겹친다. 두 세그먼트의 다른 특성도 거의 같다.
    - 답할 수 없는 것: 가족을 위한 구매인지, 한 사람이 두 종류를 산 것인지는 데이터로 가를 수 없다. 구매 횟수, 받는 사람, 배송지가 없다.
    """),
        ]
    )
    return


@app.cell
def _(df, mo, out, profile_above_floor):
    above_floor = profile_above_floor(df, "product", "both")
    both_min = above_floor["history_floor"].iloc[0]
    above_floor.to_csv(out / "tables" / "product_profile_above_both_floor.csv", index=False)
    q = above_floor.set_index("product")
    mo.vstack(
        [
            mo.md(f"### history {both_min:.0f} 이상인 고객만 비교"),
            mo.ui.table(above_floor.round(3)),
            mo.md(f"""
    - 하한을 맞추면 중앙값이 둘 다 산 고객 {q.loc["both", "history_median"]:.0f}, 남성 상품만 {q.loc["mens_only", "history_median"]:.0f}, 여성 상품만 {q.loc["womens_only", "history_median"]:.0f}로, 세 배가 넘던 차이가 {q.loc["mens_only", "level_median_ratio"]:.1f}배로 줄어든다. 차이의 대부분은 하한에서 나왔다.
    - Multichannel 비율도 {q.loc["both", "multichannel_share"]:.0%} 대 {q.loc["mens_only", "multichannel_share"]:.0%}로 비슷해진다. A3에서 보는 Multichannel과 둘 다 산 고객의 관계도 두 세그먼트가 같은 200 하한을 가진 데서 나온 것일 수 있다.
    - 그래서 "둘 다 사는 고객은 가족을 위해 사서 더 많이 산다"는 가설은 이 데이터로 뒷받침되지 않는다. 남는 차이는 작고, 가족 구매와 한 사람의 잦은 구매를 가를 변수도 없다.
    - 시사점: 구매 상품 세그먼트를 모델 입력이나 세그먼트 규칙에 쓸 때, `both`의 효과에는 200 하한이 섞인다. 규칙이 `both`를 고르면 `history`를 맞춘 비교로 다시 확인한다.
    """),
        ]
    )
    return


@app.cell
def _(df, mo, out, share_heatmap, share_table):
    by_zip = share_table(df, "zip_code", "product")
    by_channel = share_table(df, "channel", "product")
    channel_by_zip = share_table(df, "zip_code", "channel")
    by_zip.to_csv(out / "tables" / "product_by_zip.csv")
    by_channel.to_csv(out / "tables" / "product_by_channel.csv")
    channel_by_zip.to_csv(out / "tables" / "channel_by_zip.csv")
    zip_fig = share_heatmap(by_zip, "product mix by zip_code")
    zip_fig.savefig(out / "figures" / "product_by_zip.png", dpi=150)
    channel_fig = share_heatmap(by_channel, "product mix by channel")
    channel_fig.savefig(out / "figures" / "product_by_channel.png", dpi=150)
    channel_zip_fig = share_heatmap(channel_by_zip, "channel mix by zip_code")
    channel_zip_fig.savefig(out / "figures" / "channel_by_zip.png", dpi=150)
    mo.vstack(
        [
            mo.md("""
    ## A2. 사는 곳에 따라 사는 상품이 다른가

    가설: 도시에 사는 자녀가 시골의 부모를 위해 사거나, 지역마다 가구 구성이 달라 상품 구성이 다를 수 있다.
    """),
            zip_fig,
            mo.md(f"""
    - 데이터가 보여 주는 것: 세 지역의 구성이 거의 같다. 둘 다 산 고객의 비율이 Rural {by_zip.loc["Rural", "product=both"]:.1%}, Suburban {by_zip.loc["Suburban", "product=both"]:.1%}, Urban {by_zip.loc["Urban", "product=both"]:.1%}다.
    - 답할 수 없는 것: `zip_code`는 고객 주소의 지역 구분이고 배송지가 아니다. 도시 자녀가 시골 부모에게 보내는 구매는 구매자 주소(도시)로만 남아 이 데이터로는 보이지 않는다.

    ## A3. 평소 이용 채널에 따라 사는 상품이 다른가
    """),
            channel_fig,
            mo.md(f"""
    - Multichannel 고객은 둘 다 산 비율이 {by_channel.loc["Multichannel", "product=both"]:.1%}로, Phone({by_channel.loc["Phone", "product=both"]:.1%})과 Web({by_channel.loc["Web", "product=both"]:.1%})의 세 배다. 여러 채널로 사는 고객이 여러 종류를 산다.
    - 주의할 점: Multichannel 고객은 `history`가 모두 200 이상이라(`artifacts/ANA-002/tables/segment_by_channel.csv`), 이 차이에는 구매액 차이가 섞여 있다.

    ## A4. 지역마다 이용 채널이 다른가
    """),
            channel_zip_fig,
            mo.md("""
    - 세 지역의 채널 구성이 거의 같다. `zip_code`는 이 데이터의 다른 고객 특성과 거의 관계가 없다(ANA-002 Cramer's V 0.02 이하).
    - 시사점: 지역은 다른 특성과 겹치지 않으므로, 지역에 따른 결과 차이가 있으면(B, C) 다른 특성의 차이로 설명되지 않는 독립된 정보다.
    """),
        ]
    )
    return


@app.cell
def _(df, interval_plot, mo, out, segments, stacked_by_segment):
    control = df[df["treatment_id"] == 0]
    baseline = stacked_by_segment(control, segments, ["visit", "conversion", "spend"], "means")
    baseline.to_csv(out / "tables" / "control_by_segment.csv", index=False)
    visit_base_fig = interval_plot(
        baseline[baseline["outcome"] == "visit"],
        "label",
        "outcome",
        "mean",
        "visit rate without email (control)",
        "visit rate",
    )
    visit_base_fig.savefig(out / "figures" / "control_visit.png", dpi=150)
    spend_base_fig = interval_plot(
        baseline[baseline["outcome"] == "spend"],
        "label",
        "outcome",
        "mean",
        "spend per customer without email (control)",
        "USD",
    )
    spend_base_fig.savefig(out / "figures" / "control_spend.png", dpi=150)
    bv = baseline[baseline["outcome"] == "visit"].set_index("label")["mean"]
    bs = baseline[baseline["outcome"] == "spend"].set_index("label")["mean"]
    mo.vstack(
        [
            mo.md("""
    ## B. 메일이 없을 때 누가 방문하고 사나

    대조군(메일을 받지 않은 고객)만 본다. 메일 효과를 읽을 때 출발점이 되는 평소 행동이다.

    ### B1. 이용 채널에 따라 방문과 구매가 다른가
    """),
            visit_base_fig,
            mo.md(f"""
    - 방문율은 Phone {bv["channel: Phone"]:.3f}, Web {bv["channel: Web"]:.3f}, Multichannel {bv["channel: Multichannel"]:.3f}이다. 전화로 사는 고객이 웹사이트에 덜 온다. `visit`은 웹사이트 방문이라 자연스러운 차이다.
    - 고객 1명당 `spend`는 채널 사이에 구간이 겹쳐 차이를 가를 수 없다(아래 그림). 구매 고객이 대조군에서 86명뿐이라 금액 비교는 대부분 이렇다.
    - 시사점: Phone 고객은 메일로 웹 방문을 늘릴 여지가 크지만, 구매가 전화로 일어나면 `visit`이 매출을 덜 대신한다. C에서 Phone 고객의 `visit` 효과와 `spend` 효과를 함께 본다.

    ### B2. 사는 곳에 따라 방문과 구매 금액이 다른가

    - Rural 고객의 방문율이 {bv["zip_code: Rural"]:.3f}로 Suburban({bv["zip_code: Suburban"]:.3f}), Urban({bv["zip_code: Urban"]:.3f})보다 높다. A4에서 지역이 다른 특성과 겹치지 않았으므로, 이 차이는 구매액이나 채널로 설명되지 않는다. 가까운 매장이 적어 온라인을 더 찾는다는 해석과 맞지만 데이터로 확인할 수는 없다.
    - 고객 1명당 `spend`는 세 지역의 구간이 겹친다.
    - 시사점: 평소 방문율은 uplift 모델이 고객을 고르는 기준이 아니다. uplift 모델은 메일로 늘어나는 몫(C절)으로 고른다. 평소 방문율은 메일을 받았을 때의 방문 확률로 고르는 방식(반응 확률로 고르기)이 왜 다른 고객을 고르는지 설명할 때 쓴다. Rural 고객은 평소 방문율이 높지만 `visit` 효과는 다른 지역보다 크지 않아(C1), 두 방식의 선택이 갈라지는 후보다.

    ### B3. 신규 고객과 구매액에 따라 다른가

    - 기존 고객의 방문율({bv["newbie: 0"]:.3f})이 신규 고객({bv["newbie: 1"]:.3f})보다 높다.
    - 구매액이 클수록 방문율이 높아지다가({bv["history_segment: 1) $0 - $100"]:.3f}에서 {bv["history_segment: 4) $350 - $500"]:.3f}), 500\\~750 구간에서 {bv["history_segment: 5) $500 - $750"]:.3f}로 떨어졌다가 그 위 구간에서 다시 높다. 500달러 이상 구간은 모두 신규 고객이라(ANA-002), 구매액 효과와 신규 고객 효과가 겹친다.
    - 둘 다 산 고객의 방문율({bv["product: both"]:.3f})이 한 종류만 산 고객(약 {bv["product: mens_only"]:.2f})의 두 배에 가깝다.
    - 고객 1명당 `spend`는 대부분의 세그먼트 사이에 구간이 겹치지만, 기존 고객({bs["newbie: 0"]:.2f})과 신규 고객({bs["newbie: 1"]:.2f})은 겹치지 않는다. 기존 고객은 메일 없이도 더 많이 산다.
    """),
            spend_base_fig,
        ]
    )
    return


@app.cell
def _(df, effects_below_zero, interval_plot, mo, out, segments, stacked_by_segment):
    effects = stacked_by_segment(df, segments, ["visit", "spend"], "effects")
    effects.to_csv(out / "tables" / "segment_effects.csv", index=False)
    visit_eff_fig = interval_plot(
        effects[effects["outcome"] == "visit"],
        "label",
        "comparison",
        "effect",
        "visit effect by segment",
        "difference in visit rate",
    )
    visit_eff_fig.savefig(out / "figures" / "effect_visit.png", dpi=150)
    spend_eff_fig = interval_plot(
        effects[effects["outcome"] == "spend"],
        "label",
        "comparison",
        "effect",
        "spend effect by segment",
        "difference in spend per customer (USD)",
    )
    spend_eff_fig.savefig(out / "figures" / "effect_spend.png", dpi=150)
    ev = effects.set_index(["outcome", "label", "comparison"])
    womens_better = effects_below_zero(effects, ["Mens - Womens"])
    harmed = effects_below_zero(effects, ["Mens - None", "Womens - None"])
    mo.vstack(
        [
            mo.md("""
    ## C. 메일에 누가 반응했나

    세그먼트마다 남성용 대 미발송, 여성용 대 미발송, 남성용 대 여성용의 차이와 95% 구간이다.

    ### C1. 구매 상품과 메일 종류가 맞으면 더 반응하는가
    """),
            visit_eff_fig,
            mo.md(f"""
    - 여성 상품만 산 고객: 여성용 메일의 방문 효과({ev.loc[("visit", "product: womens_only", "Womens - None"), "effect"]:.3f})가 남성용({ev.loc[("visit", "product: womens_only", "Mens - None"), "effect"]:.3f})과 같다(차이 구간 {ev.loc[("visit", "product: womens_only", "Mens - Womens"), "ci_low"]:.3f}\\~{ev.loc[("visit", "product: womens_only", "Mens - Womens"), "ci_high"]:.3f}).
    - 남성 상품만 산 고객: 여성용 메일의 방문 효과가 {ev.loc[("visit", "product: mens_only", "Womens - None"), "effect"]:.3f}로 거의 없다. 남성용은 {ev.loc[("visit", "product: mens_only", "Mens - None"), "effect"]:.3f}다.
    - 둘 다 산 고객: 남성용 메일의 방문 효과가 {ev.loc[("visit", "product: both", "Mens - None"), "effect"]:.3f}로 세그먼트 가운데 가장 크다.
    - 남성용 메일은 모든 구매 상품 세그먼트에서 여성용과 같거나 더 크다. 다른 세그먼트 변수(채널, 지역, 신규 여부, 구매액 구간)에서도 `visit` 효과가 여성용이 남성용보다 큰 곳은 없다.
    - 해석: 여성용 메일의 방문 효과는 여성 상품만 산 고객에게 가장 크고, 남성 상품만 산 고객에게는 매우 작다. 남성용 메일은 세 세그먼트 모두에서 효과가 비슷하거나 더 크다. 남성용 메일의 내용이나 상품이 더 넓은 고객에게 맞았을 수 있으나, 메일 내용이 데이터에 없어 확인할 수 없다.
    - 시사점: `visit` 기준으로 고객마다 메일을 고르는 정책은 대부분의 고객에게 남성용을 고르게 된다. 여성 상품만 산 고객에게는 두 메일이 같아 어느 쪽이든 정책 가치가 같다. 그래서 M2의 고른 정책이 전체 발송 정책을 `visit`으로 크게 넘기 어렵다고 예상한다.
    """),
            spend_eff_fig,
            mo.md(f"""
    - `spend` 효과는 구간이 넓다. 여성용이 남성용보다 큰 점추정은 Urban({ev.loc[("spend", "zip_code: Urban", "Mens - Womens"), "effect"]:.2f}) 등 몇 곳에 있지만, 구간이 0을 포함한다. 여성용이 남성용보다 확실히 나은 세그먼트(차이 구간 상한이 0 미만)는 `visit`과 `spend`를 합쳐 {len(womens_better)}곳이다.
    - 둘 다 산 고객에게는 남성용 메일의 `spend` 효과({ev.loc[("spend", "product: both", "Mens - None"), "effect"]:.2f})가 여성용({ev.loc[("spend", "product: both", "Womens - None"), "effect"]:.2f})보다 크다.
    - 신규 고객은 메일 없이의 매출이 기존 고객보다 적지만(B3), `spend` 효과는 더 크다. 남성용 {ev.loc[("spend", "newbie: 1", "Mens - None"), "effect"]:.2f} 대 {ev.loc[("spend", "newbie: 0", "Mens - None"), "effect"]:.2f}, 여성용 {ev.loc[("spend", "newbie: 1", "Womens - None"), "effect"]:.2f} 대 {ev.loc[("spend", "newbie: 0", "Womens - None"), "effect"]:.2f}다. `visit` 효과는 두 집단이 비슷하다. 신규 고객에게는 두 메일의 `spend` 효과 차이({ev.loc[("spend", "newbie: 1", "Mens - Womens"), "effect"]:.2f}, 구간 {ev.loc[("spend", "newbie: 1", "Mens - Womens"), "ci_low"]:.2f}\\~{ev.loc[("spend", "newbie: 1", "Mens - Womens"), "ci_high"]:.2f})를 가를 수 없다.
    - 메일이 결과를 확실히 줄인 세그먼트(효과 구간 상한이 0 미만)는 {len(harmed)}곳이다. 세그먼트 단위에서는 Sleeping Dogs가 보이지 않는다. 있다면 고객별 예측에서 찾아야 한다.
    """),
        ]
    )
    return


@app.cell
def _(df, funnel_ratio_ci, incremental_composition, mo, out, pd, segment_effects):
    composition = pd.concat(
        [
            incremental_composition(segment_effects(df, "product", outcome), "product").assign(
                outcome=outcome
            )
            for outcome in ["visit", "spend"]
        ],
        ignore_index=True,
    )
    composition.to_csv(out / "tables" / "incremental_composition.csv", index=False)
    funnel = pd.concat([funnel_ratio_ci(df, "product", t) for t in (1, 2)], ignore_index=True)
    funnel.to_csv(out / "tables" / "funnel_by_product.csv", index=False)
    cv = composition.set_index(["outcome", "comparison", "product"])["share"]
    fv = funnel.set_index(["treatment", "product"])
    mo.vstack(
        [
            mo.md("""
    ### C2. 메일로 늘어난 방문과 매출은 어느 고객에게서 나왔나

    고객 한 명이 반응했는지는 알 수 없다(한 고객은 메일을 받은 경우와 받지 않은 경우 중 하나만 관측된다). 그래서 세그먼트마다 효과에 고객 수를 곱해, 늘어난 방문과 매출이 어느 세그먼트에서 왔는지 나눈다.
    """),
            mo.ui.table(composition.round(3)),
            mo.md(f"""
    - 여성용 메일로 늘어난 방문의 {cv[("visit", "Womens - None", "womens_only")]:.0%}가 여성 상품만 산 고객에게서 나왔다. 남성용 메일로 늘어난 방문은 남성 상품만({cv[("visit", "Mens - None", "mens_only")]:.0%}), 여성 상품만({cv[("visit", "Mens - None", "womens_only")]:.0%}), 둘 다({cv[("visit", "Mens - None", "both")]:.0%})로 고르게 나뉜다.
    - 둘 다 산 고객은 전체의 10%인데, 남성용 메일로 늘어난 매출의 {cv[("spend", "Mens - None", "both")]:.0%}를 차지한다. `spend` 효과의 구간이 넓어 이 몫도 흔들린다.

    ### C3. 늘어난 방문 1회당 구매는 고객마다 같은가

    퍼널 분해(M2 금액 모델 후보)는 처치마다 늘어난 방문 1회당 구매가 고객 특성으로는 크게 다르지 않다고 가정한다. 구매 상품 세그먼트로 이 가정을 본다.
    """),
            mo.ui.table(funnel.round(3)),
            mo.md(f"""
    - 남성용 메일의 늘어난 방문 1회당 구매는 둘 다 산 고객 {fv.loc[(1, "both"), "conversion_per_visit"]:.3f}, 남성 상품만 {fv.loc[(1, "mens_only"), "conversion_per_visit"]:.3f}, 여성 상품만 {fv.loc[(1, "womens_only"), "conversion_per_visit"]:.3f}이고 구간이 서로 겹친다. 가정을 기각할 근거는 없지만, 구간이 넓어 같다고 확인한 것도 아니다.
    - 여성용 메일은 남성 상품만 산 고객의 방문 효과가 거의 0이라 비율의 구간이 매우 넓다({fv.loc[(2, "mens_only"), "ci_low"]:.2f}\\~{fv.loc[(2, "mens_only"), "ci_high"]:.2f}).
    - 시사점: 퍼널 분해를 쓸 때 처치별 비율 하나를 쓰는 것이 이 데이터에서 반박되지 않는다. M2 금액 모델 비교에서 두 부분 모델과의 차이를 볼 때 이 결과를 출발점으로 쓴다.
    """),
        ]
    )
    return


@app.cell
def _(buyer_sample_size, df, mo, out, threshold_effects):
    thresholds = threshold_effects(df, [50.0, 100.0, 200.0])
    thresholds.to_csv(out / "tables" / "threshold_effects.csv", index=False)
    th = thresholds.set_index(["threshold", "treatment"])
    sample = buyer_sample_size(df, 10.0)
    sample.to_csv(out / "tables" / "sample_size.csv", index=False)
    s = sample.iloc[0]
    mo.vstack(
        [
            mo.md("""
    ## D. 담당자 질문

    ### D1. 여성용 메일이 남성용보다 나은 고객군이 있는가

    C1에서 본 대로, `visit`과 `spend` 어느 쪽에서도 여성용이 남성용보다 확실히 나은 세그먼트는 없다. 여성 상품만 산 고객에게는 두 메일이 같다.

    ### D2. 메일이 고액 구매를 늘리는가

    `spend`가 문턱을 넘는 고객의 비율을 처치군과 대조군으로 비교한다. 전체 고객을 비교하므로, 구매 고객끼리 비교할 때와 달리 처치 효과로 읽을 수 있다. 문턱은 499 잘림 아래에 둔다.
    """),
            mo.ui.table(thresholds.round(4)),
            mo.md(f"""
    - 남성용 메일은 200달러 넘게 사는 고객의 비율을 {th.loc[(200.0, 1), "mean_control"]:.4f}에서 {th.loc[(200.0, 1), "mean_treated"]:.4f}로 높였다(구간 {th.loc[(200.0, 1), "ci_low"]:.4f}\\~{th.loc[(200.0, 1), "ci_high"]:.4f}). 여성용은 {th.loc[(200.0, 2), "mean_treated"]:.4f}이고 구간이 0에 닿는다.
    - 100달러 문턱에서는 두 메일 모두 비율을 대조군의 약 두 배로 높였다.
    - 시사점: 메일은 소액 구매만 늘린 것이 아니다. 고액 구매자 수는 여전히 적어(학습 세트 전체에서 수십 명) 세그먼트별로 나누어 보기는 어렵다.

    ### D3. 지금 데이터로 답할 수 없는 질문

    | 질문 | 없는 정보 |
    | --- | --- |
    | 남성용 메일로 구매 금액을 어떻게 높이나 | 메일 내용, 상품, 가격의 변형. 처치마다 메일이 한 종류다 |
    | 여성용 메일의 방문을 어떻게 늘리나 | 같음 |
    | 둘 다 사는 고객은 가족을 위해 사나 | 구매 횟수, 받는 사람, 배송지 |
    | 구매 고객 1명당 금액이 메일마다 다른가 | 구매 고객 수. 아래 표본 크기 |

    - 구매 고객 1명당 금액의 차이 10달러를 검정력 80%로 가르려면 군마다 구매 고객 {s["buyers_per_arm"]:,.0f}명이 필요하다(구매 고객 `spend`의 표준편차 {s["buyer_spend_sd"]:.0f}로 계산). 메일 받은 고객의 구매율 {s["mailed_conversion"]:.2%}로 나누면 군마다 고객 약 {s["customers_per_arm"]:,.0f}명이다. 지금 학습 세트는 군마다 약 15,000명이다.
    - 후속 실험 제안: 메일 내용(상품 구성, 가격대)을 바꾼 처치를 둔 실험을 이 크기로 설계하거나, 구매 금액 대신 장바구니 크기처럼 구매 고객이 아니어도 관측되는 지표를 함께 기록한다.
    """),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## E. M2·M3에 넘길 가설

    | 가설 | 근거 | 확인할 곳 |
    | --- | --- | --- |
    | 구매 상품(`mens`, `womens`)과 메일 종류의 짝이 고객별 효과 차이를 가장 크게 만든다 | C1 | M2 모델의 변수 중요도, M3 세그먼트 규칙 |
    | `visit` 기준 고른 정책은 대부분 남성용을 골라 전체 발송 정책과의 차이가 작다 | C1, D1 | M2 첫 실험에서 재는 seed 간 범위와 고른 정책의 정책 가치 차이 |
    | Rural 고객은 평소 방문율이 높지만 `visit` 효과는 크지 않아, 반응 확률로 고를 때와 효과로 고를 때 선택이 갈라진다 | B2, C1 | M2 비교 정책과 uplift 모델의 고객 선택 비교 |
    | 신규 고객은 `visit` 효과는 기존 고객과 비슷하지만 `spend` 효과가 더 크다 | C1 | M2 금액 모델, M3 이익 최대화형 정책 |
    | 메일이 결과를 줄이는 고객은 세그먼트 단위에서 보이지 않는다 | C1 | M3 Sleeping Dogs 점검(고객별 예측) |
    | 모델이 예측한 uplift의 세그먼트 평균이 이 노트북의 세그먼트 효과와 맞는다 | C1 | M2 모델 점검 |
    | Phone 고객은 `visit` 효과에 비해 매출로 덜 이어진다 | B1 | M3 이익 최대화형 정책에서 채널별 증분 이익 |
    | 늘어난 방문 1회당 구매는 처치 안에서 구매 상품 세그먼트로 크게 다르지 않다 | C3 | M2 금액 모델(퍼널 분해 대 두 부분 모델) |
    | 둘 다 산 고객의 효과에는 `history` 200 하한이 섞인다 | A1 | M3 세그먼트 규칙을 `history`를 맞춰 다시 확인 |
    """)
    return


if __name__ == "__main__":
    app.run()
