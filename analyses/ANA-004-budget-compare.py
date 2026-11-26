import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo
    from pandas import concat as pd_concat

    from uplift import runs
    from uplift.budget import RATIOS, budget_differences, judge_budget
    from uplift.plots import budget_plot
    from uplift.policy import MENS, WOMENS
    from uplift.train_data import from_duckdb

    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "ANA-004"
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(root / "data" / "uplift.duckdb"), read_only=True)
    frame = from_duckdb(con).frame
    return (
        MENS,
        RATIOS,
        WOMENS,
        budget_differences,
        budget_plot,
        con,
        frame,
        judge_budget,
        mo,
        out,
        pd_concat,
        runs,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # ANA-004 예산 제약에서 uplift 모델 대 반응 모델

    ## 질문

    - 바뀔 결정: 프로젝트 방향. uplift 정책이 같은 발송 수의 반응 모델 정책을 `visit`에서 이기는 발송 비율이 있으면 uplift로 M3(비용·예산 정책)를 잇는다. 없으면 결과 변수를 `spend`로 두고 메일 비용 조사를 거쳐 비용과 예산을 고려하는 쪽으로 방향을 바꾸고 milestone을 조정한다(사용자 결정 2026-11-26). 방향 전환은 이 결과를 보고 사용자가 정한다.
    - 지킬 조건: 학습 세트만 쓴다. 새로 학습하지 않고 DuckDB에 있는 OOF 예측을 쓴다. uplift 모델은 1단계에서 승인된 S-learner(EXP-002 실행 `52938f3ec570`), 반응 모델은 EXP-001 실행 `cfb0d1dade18`이다. 결과 변수는 `visit`, 추정량은 Hájek이다.
    - 못 정한 질문: 메일 비용과 마진을 넣은 이익 최대화형 정책은 비용 가정 승인 뒤에 본다.

    ## 설계

    - 질문 유형: 결정.
    - 추정 대상: 발송 비율 k(10%, 20%, ..., 90%)마다 두 정책의 `visit` 정책 가치 차이(uplift − 반응 모델). 두 정책 모두 `policy.top_k`로 만든다. 메일별 점수 가운데 큰 메일을 고르고 그 점수 순으로 상위 k명에게 보낸다. uplift 정책의 점수는 메일별 uplift, 반응 모델 정책의 점수는 메일별 방문 확률이다.
    - 추정: seed 42, 154, 1592의 OOF 예측마다 Hájek 차이와 고객 복원 추출 부트스트랩 1,000회의 95% 구간(부트스트랩 seed는 실행 seed).
    - 판정 규칙: k마다 세 seed 차이의 평균 $\bar d$와 범위 $R$을 구하고 문턱을 $\max(R, 0.0038)$로 둔다(EXP-002와 같은 규칙). $\bar d$가 문턱 이상이면 그 k에서 uplift가 이긴다, $-\bar d$가 문턱 이상이면 반응 모델이 이긴다, 그 밖에는 가를 수 없다고 본다. 어느 k에서도 uplift가 이기지 못하면 "uplift가 이기는 예산이 없다"로 보고한다.
    - 이미 본 것: 발송 100% 부근에서 S-learner 정책과 같은 발송 수의 반응 모델 정책은 가를 수 없었다(`artifacts/EXP-002/tables/response_same_send.csv`). 정규화 Qini는 여성용 대 미발송에서 uplift 모델이 높고, 남성용 대 미발송에서 반응 모델이 높았다(`artifacts/EXP-002/tables/ranking.csv`, `artifacts/EXP-001/tables/response_ranking.csv`).
    - 걸리는 점: k 아홉 개를 보므로, 한 k에서 우연히 문턱을 넘을 수 있다. 이기는 k가 하나뿐이고 이웃 k가 가를 수 없으면 그렇게 보고한다.
    """)
    return


@app.cell
def _(MENS, RATIOS, WOMENS, budget_differences, con, frame, pd_concat, runs):
    UPLIFT_RUN = "52938f3ec570"
    RESPONSE_RUN = "cfb0d1dade18"
    SEEDS = (42, 154, 1592)
    N_BOOT = 1000
    indexed = frame.set_index("customer_id")
    parts = []
    for seed in SEEDS:
        uplift = runs.load_scores(con, UPLIFT_RUN, f"s_learner_s{seed}", (MENS, WOMENS))
        response = runs.load_scores(
            con, RESPONSE_RUN, f"response_lgbm_s{seed}", (MENS, WOMENS)
        ).reindex(uplift.index)
        rows = indexed.loc[uplift.index]
        parts.append(
            budget_differences(
                uplift.to_numpy(),
                response.to_numpy(),
                rows["treatment_id"].to_numpy(),
                rows["visit"].to_numpy(),
                RATIOS,
                N_BOOT,
                seed,
            )
        )
    differences = pd_concat(parts, ignore_index=True)
    return (differences,)


@app.cell
def _(budget_plot, differences, judge_budget, out):
    FLOOR = 0.0038
    judged = judge_budget(differences, FLOOR)
    differences.to_csv(out / "tables" / "budget_differences.csv", index=False)
    judged.to_csv(out / "tables" / "budget_judgement.csv", index=False)
    budget_plot(differences, judged).savefig(out / "figures" / "budget_differences.png", dpi=150)
    judged
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## visit: S-learner 정책이 반응 모델 정책을 이기는 발송 비율이 없다

    발송 비율 10%\~90% 아홉 개 가운데 uplift가 이긴 비율은 없고, 반응 모델이 50%와 60%에서 이겼다. 나머지 일곱 비율은 가를 수 없다(`tables/budget_judgement.csv`).
    """)
    return


if __name__ == "__main__":
    app.run()
