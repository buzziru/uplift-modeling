import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path

    import duckdb
    import marimo as mo
    import pandas as pd

    from uplift.db import CUSTOMER_COLUMNS, load_frame
    from uplift.plots import smd_plot
    from uplift.randomization import (
        SMD_THRESHOLD,
        ate_diff,
        funnel_ratios,
        precision_at_test_size,
        smd_table,
        srm_test,
    )

    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "ANA-001"
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(root / "data" / "uplift.duckdb"), read_only=True) as con:
        df = load_frame(con)
        test_counts = (
            con.sql(
                """
            SELECT a.treatment_id, count(*) AS n
            FROM splits AS s
            INNER JOIN assignments AS a ON s.customer_id = a.customer_id
            WHERE s.split = 'test'
            GROUP BY a.treatment_id
            """
            )
            .df()
            .set_index("treatment_id")["n"]
        )
    names = {0: "No E-Mail", 1: "Mens E-Mail", 2: "Womens E-Mail"}
    return (
        CUSTOMER_COLUMNS,
        SMD_THRESHOLD,
        ate_diff,
        df,
        funnel_ratios,
        json,
        mo,
        names,
        out,
        pd,
        smd_plot,
        smd_table,
        srm_test,
        test_counts,
        precision_at_test_size,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # ANA-001 무작위 배정 점검과 처치별 ATE

    ## 질문

    - 바뀔 결정: 이후 추정을 보정 없이 할지(Q1), 승인 지점 1의 결과 변수와 성공 기준(Q2), 승인 지점 2의 분할과 검증(Q3). SPEC.md 11절.
    - 지킬 조건: 이 노트북은 실험 전체(분할 전 64,000행)의 기술 통계를 낸다. 시험 세트는 행 수만 읽고(판정 기준의 비용 절), 결과는 시험 세트를 따로 떼어 보지 않는다.

    ## 이미 본 것

    - 분할 전 전체 데이터의 처치별 visit, conversion, spend 차이, 깔때기 구조, 세 군의 SRM, `history` 한 변수의 SMD. M1 준비 메모에서 설명용으로 계산했다. 이 노트북의 수치는 그 메모를 인용하지 않고 `src/` 함수로 다시 계산한다.
    - 나머지 공변량의 SMD는 보지 않았다.

    ## 판정 규칙 (나머지 공변량을 보기 전에 정함)

    - SRM: 세 군의 크기를 설계 비율(1/3씩)과 카이제곱으로 비교한다. p < 0.001이면 분석을 멈추고 배정과 기록을 조사한다.
    - 균형: 원본 공변량(범주형은 범주별 비율)의 |SMD|를 세 군 정의(남성용, 여성용 각각 대 미발송)와 이진 정의(메일 전체 대 미발송)로 구한다. 모두 0.1 미만이면 평균 차이를 ATE로 쓴다. 0.1 이상이 하나라도 있으면 Y = α + τ·T + βX 회귀의 τ를 ATE로 쓴다.
    - "크다"는 점추정이 아니라 95% 신뢰구간으로 판정한다. 정책 비교는 두 정책 가치 차이의 구간으로 한다. 이 기준의 비용은 아래 판정 기준의 비용 절에 적는다.
    """)
    return


@app.cell
def _(df, json, mo, names, out, pd, srm_test):
    srm = srm_test(
        df["treatment_id"].map(names).value_counts().sort_index(),
        pd.Series({n: 1 for n in names.values()}),
    )
    (out / "tables" / "srm.json").write_text(
        json.dumps(srm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    mo.stop(srm["mismatch"], mo.md(f"SRM p = {srm['p_value']:.4f}: 규칙에 따라 멈춘다."))
    mo.md(f"""
    ## SRM

    관측 {srm["counts"]}, 기대 {srm["expected"]}. χ² = {srm["chi2"]:.3f}, p = {srm["p_value"]:.3f}. 기준 p < 0.001에 걸리지 않는다.
    """)
    return


@app.cell
def _(CUSTOMER_COLUMNS, SMD_THRESHOLD, df, mo, out, pd, smd_plot, smd_table):
    covariates = df[CUSTOMER_COLUMNS]
    smd = pd.concat(
        [
            smd_table(covariates, df["treatment_id"]).assign(
                comparison=lambda d: d["treatment"].map({1: "Mens vs None", 2: "Womens vs None"})
            ),
            smd_table(covariates, (df["treatment_id"] > 0).astype(int)).assign(
                comparison="Mail vs None"
            ),
        ],
        ignore_index=True,
    ).drop(columns="treatment")
    smd.to_csv(out / "tables" / "smd.csv", index=False)
    smd_plot(smd, SMD_THRESHOLD).savefig(out / "figures" / "smd.png", dpi=150)
    worst = smd.loc[smd["smd"].abs().idxmax()]
    mo.stop(
        not smd["balanced"].all(),
        mo.md("|SMD| ≥ 0.1인 공변량이 있다. 규칙에 따라 공변량 보정 회귀로 ATE를 구한다."),
    )
    mo.md(f"""
    ## 공변량 균형

    공변량·범주 {smd["covariate"].str.cat(smd["level"].astype(str)).nunique()}개를 세 비교로 본 SMD {len(smd)}개 모두 |SMD| < {SMD_THRESHOLD}. 가장 큰 값은 {worst["comparison"]}의 {worst["covariate"]}{"" if pd.isna(worst["level"]) else " = " + str(worst["level"])}에서 {worst["smd"]:.4f}다. 규칙에 따라 평균 차이를 ATE로 쓴다.
    """)
    return


@app.cell
def _(ate_diff, df, mo, out, pd):
    ate = pd.concat(
        [
            ate_diff(df[y], definition).assign(outcome=y, comparison=label)
            for y in ["visit", "conversion", "spend"]
            for definition, label in [
                (df["treatment_id"], None),
                ((df["treatment_id"] > 0).astype(int), "Mail vs None"),
            ]
        ],
        ignore_index=True,
    )
    ate["comparison"] = ate["comparison"].fillna(
        ate["treatment"].map({1: "Mens vs None", 2: "Womens vs None"})
    )
    ate = ate.drop(columns="treatment")
    ate.to_csv(out / "tables" / "ate.csv", index=False)
    mo.vstack([mo.md("## 처치별 ATE (전체 데이터, 95% 신뢰구간)"), mo.ui.table(ate.round(5))])
    return (ate,)


@app.cell
def _(ate, df, funnel_ratios, mo, out):
    funnel = funnel_ratios(
        ate.pivot(index="comparison", columns="outcome", values="effect"),
        df[df["treatment_id"] == 0],
    )
    funnel.to_csv(out / "tables" / "funnel.csv")
    mo.vstack(
        [
            mo.md("""
    ## 깔때기: 추가로 생긴 방문의 구매율

    처치 행은 효과의 비(구매 증가 / 방문 증가, 매출 증가 / 구매 증가)이고, 대조군 행은 대조군의 비율이다. 처치 행이 대조군 행과 다르면 방문 1회의 가치를 하나로 가정할 수 없다(`docs/PROBLEM.md` 결과 변수 절의 기각한 대안).
    """),
            mo.ui.table(funnel.round(4).reset_index(names="comparison")),
        ]
    )
    return


@app.cell
def _(df, mo, names, out, pd, test_counts, precision_at_test_size):
    precision = pd.concat(
        [
            precision_at_test_size(df[_y], df["treatment_id"], test_counts).assign(outcome=_y)
            for _y in ["visit", "conversion", "spend"]
        ],
        ignore_index=True,
    )
    precision["comparison"] = precision["treatment"].map(names) + " vs No E-Mail"
    precision = precision.drop(columns="treatment")
    precision.to_csv(out / "tables" / "precision.csv", index=False)
    mo.vstack(
        [
            mo.md(f"""
    ## 판정 기준의 비용

    시험 세트 크기(처치별 {dict(test_counts.rename(names))})에서 처치군 대 대조군 차이의 95% 구간 반폭과, 검정력 80%로 0이 아님을 가를 수 있는 최소 효과(MDE)다. 분산은 전체 데이터에서 구했다. 실제 개선이 이 반폭보다 작으면 "크다"로 판정되지 않는다. 정책 간 비교는 같은 고객에 두 정책을 적용한 차이의 구간이라, 두 정책이 같은 처치를 추천한 고객의 몫만큼 이보다 좁다.
    """),
            mo.ui.table(precision.round(5)),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
