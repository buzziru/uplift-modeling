import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo

    db_path = Path(__file__).resolve().parents[1] / "data" / "uplift.duckdb"
    con = duckdb.connect(str(db_path), read_only=True)
    return con, mo


@app.cell
def _(mo):
    mo.md("""
    # DuckDB 테이블 둘러보기

    `data/uplift.duckdb`를 읽기 전용으로 연다. 먼저 `scripts/fetch_data.py`, `scripts/build_db.py`를 돌린다.
    아래 SQL 셀의 쿼리를 바꿔 원하는 것을 본다. 결과는 저장하지 않는다.
    """)
    return


@app.cell
def _(con, mo):
    mo.sql(
        """
        SELECT table_name, estimated_size AS rows, column_count
        FROM duckdb_tables()
        ORDER BY table_name
        """,
        engine=con,
    )
    return


@app.cell
def _(con, mo):
    table_name = mo.ui.dropdown(
        options=[r[0] for r in con.execute("SHOW TABLES").fetchall()],
        value="customers",
        label="테이블",
    )
    table_name
    return (table_name,)


@app.cell
def _(con, mo, table_name):
    mo.ui.table(con.table(table_name.value).df(), page_size=20)
    return


if __name__ == "__main__":
    app.run()
