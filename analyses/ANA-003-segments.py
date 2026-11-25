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
    from uplift.eda import product_segment, segment_profile
    from uplift.plots import ecdf_by_group, share_heatmap

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
    both_min = df.loc[df["product"] == "both", "history"].min()
    return both_min, df, ecdf_by_group, mo, out, pd, segment_profile, share_heatmap


@app.cell
def _(df, mo):
    mo.md(f"""
    # ANA-003 고객 세그먼트와 메일 반응

    고객과 상품에 대한 질문을 던지고, 학습 세트({len(df):,}행)가 그 질문에 어디까지 답하는지 본다. 질문마다 가설, 데이터가 보여 주는 것, 데이터로 답할 수 없는 것을 함께 적는다. ANA-002에서 본 잘림과 정의 경계(`artifacts/ANA-002/summary.md`)를 해석에 반영한다.

    구매 상품 세그먼트(`product`)는 `mens`, `womens`를 남성 상품만(`mens_only`), 여성 상품만(`womens_only`), 둘 다(`both`)로 묶은 값이다. 둘 다 사지 않은 고객은 없다. 한 종류만 산 고객의 성별은 그 상품의 성별로 추정할 수 있지만 확정할 수는 없다.

    A. 고객은 어떻게 구성되어 있나
    """)
    return


@app.cell
def _(both_min, df, ecdf_by_group, mo, out, segment_profile):
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
    - 주의할 점: 둘 다 산 고객의 `history` 최솟값은 {both_min:.2f}이고, 그 아래인 고객이 한 명도 없다. 두 종류를 사려면 적어도 두 개를 사야 하므로 구매액이 큰 것의 일부는 정의에서 나온다. 다만 하한이 29.99의 약 일곱 배라, 원본을 만들 때 둘 다 산 고객에게 따로 정한 경계로 보인다(Multichannel의 200 하한과 같은 꼴). 한 종류만 산 고객 중 이 하한 이상인 고객만 비교해도 차이가 남는지는 아래 표로 본다.
    - 남성 상품만 산 고객과 여성 상품만 산 고객은 `history` 분포가 거의 겹친다. 두 세그먼트의 다른 특성도 거의 같다.
    - 답할 수 없는 것: 가족을 위한 구매인지, 한 사람이 두 종류를 산 것인지는 데이터로 가를 수 없다. 구매 횟수, 받는 사람, 배송지가 없다.
    """),
        ]
    )
    return


@app.cell
def _(both_min, df, mo, out, segment_profile):
    above_floor = segment_profile(df[df["history"] >= both_min], "product")
    above_floor.to_csv(out / "tables" / "product_profile_above_both_floor.csv", index=False)
    q = above_floor.set_index("product")
    mo.vstack(
        [
            mo.md(f"### history {both_min:.0f} 이상인 고객만 비교"),
            mo.ui.table(above_floor.round(3)),
            mo.md(f"""
    - 하한을 맞추면 중앙값이 둘 다 산 고객 {q.loc["both", "history_median"]:.0f}, 남성 상품만 {q.loc["mens_only", "history_median"]:.0f}, 여성 상품만 {q.loc["womens_only", "history_median"]:.0f}로, 세 배가 넘던 차이가 {q.loc["both", "history_median"] / q.loc["mens_only", "history_median"]:.1f}배로 줄어든다. 차이의 대부분은 하한에서 나왔다.
    - Multichannel 비율도 {q.loc["both", "multichannel_share"]:.0%} 대 {q.loc["mens_only", "multichannel_share"]:.0%}로 비슷해진다. A3에서 보는 Multichannel과 둘 다 산 고객의 관계도 두 세그먼트가 같은 200 하한을 가진 데서 나온 것일 수 있다.
    - 그래서 "둘 다 사는 고객은 가족을 위해 사서 더 많이 산다"는 가설은 이 데이터로 뒷받침되지 않는다. 남는 차이는 작고, 가족 구매와 한 사람의 잦은 구매를 가를 변수도 없다.
    """),
        ]
    )
    return


@app.cell
def _(df, mo, out, pd, share_heatmap):
    by_zip = pd.crosstab(df["zip_code"], df["product"], normalize="index")
    by_channel = pd.crosstab(df["channel"], df["product"], normalize="index")
    channel_by_zip = pd.crosstab(df["zip_code"], df["channel"], normalize="index")
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
    - 데이터가 보여 주는 것: 세 지역의 구성이 거의 같다. 둘 다 산 고객의 비율이 Rural {by_zip.loc["Rural", "both"]:.1%}, Suburban {by_zip.loc["Suburban", "both"]:.1%}, Urban {by_zip.loc["Urban", "both"]:.1%}다.
    - 답할 수 없는 것: `zip_code`는 고객 주소의 지역 구분이고 배송지가 아니다. 도시 자녀가 시골 부모에게 보내는 구매는 구매자 주소(도시)로만 남아 이 데이터로는 보이지 않는다.

    ## A3. 평소 이용 채널에 따라 사는 상품이 다른가
    """),
            channel_fig,
            mo.md(f"""
    - Multichannel 고객은 둘 다 산 비율이 {by_channel.loc["Multichannel", "both"]:.1%}로, Phone({by_channel.loc["Phone", "both"]:.1%})과 Web({by_channel.loc["Web", "both"]:.1%})의 세 배다. 여러 채널로 사는 고객이 여러 종류를 산다.
    - 주의할 점: Multichannel 고객은 `history`가 모두 200 이상이라(`artifacts/ANA-002/tables/segment_by_channel.csv`), 이 차이에는 구매액 차이가 섞여 있다.

    ## A4. 지역마다 이용 채널이 다른가
    """),
            channel_zip_fig,
            mo.md("""
    - 세 지역의 채널 구성이 거의 같다. `zip_code`는 이 데이터의 다른 고객 특성과 거의 관계가 없다(ANA-002 Cramer's V 0.02 이하).
    """),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
