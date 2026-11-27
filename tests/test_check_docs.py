import importlib.util
import io
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[1] / ".claude" / "harness" / "check_docs.py"
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("check_docs.py를 불러오지 못했다")
check_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_docs)


def names_each(spans: list[str], messages: list[str]) -> bool:
    return all(s in m for s, m in zip(spans, messages, strict=True))


@pytest.fixture
def no_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(check_docs, "scope_files", list)
    return tmp_path


@pytest.mark.parametrize(
    "text",
    [
        '`docs/DATA.md` "처치 x 퍼널 단계로 층화한다" 절',
        "`docs/ENGINEERING.md` DuckDB 절",
        "규칙은 docs/DATA.md 적재 절.",
        "`docs/EVALUATION.md`의 모델 선택 항목",
        "`docs/DATA.md#분할`",
        "`docs/DATA.md`에 적은 분할 항목",
        "`docs/plans/M2-PLAN.md` U3 메모",
    ],
)
def test_check_inbound_flags_citations(text):
    assert check_docs.check_inbound(text, "x.md")


@pytest.mark.parametrize(
    "text",
    [
        "| `docs/PROBLEM.md` | 비즈니스 질문, 성공 기준 | 사이트 항목의 문제 문장 |",
        '`docs/THEORY.md` "Hillstrom 데이터 구조" 절',
        "`docs/glossary.md`의 기록 문서 항목",
        "기록: `docs/DASHBOARD.md`(화면)",
        "`docs/ENGINEERING.md` 절차를 따른다",
        "`docs/DATA.md`(SPEC.md 3절)",
        "`docs/POLICY.md`에 항목을 남긴다",
        "NARRATIVE.md는 마일스톤별 성과 자료라 8절의 형식을 따른다",
        "지금 계획은 `docs/plans/`다.",
    ],
)
def test_check_inbound_allows_non_citations(text):
    assert check_docs.check_inbound(text, "x.md") == []


def test_history_ratio_counts_history_block_lines():
    text = (
        "## 2026-11-24 제목\n- 결정: a\n- 근거: b\n- 바뀐 이력:\n"
        "  - 2026-11-24: c\n  - 2026-11-25: d\n\n"
        "## 2026-11-25 다른 제목\n- 결정: e\n  - 하위 줄"
    )
    # 열 줄 가운데 바뀐 이력 블록(머리 줄과 하위 두 줄) 세 줄을 손으로 센 값
    assert check_docs.history_ratio(text) == pytest.approx(3 / 10)


@pytest.mark.parametrize("text", ["", "## 제목\n- 결정: a\n"], ids=["empty", "no_history"])
def test_history_ratio_without_history_is_zero(text):
    assert check_docs.history_ratio(text) == 0.0


@pytest.mark.parametrize(
    ("text", "warned"),
    [("## 결정\n- 바뀐 이력:\n  - a\n  - b\n", True), ("## 결정\n- 결정: a\n", False)],
)
def test_check_history_warns_on_long_history(no_scope, text, warned):
    (no_scope / "docs").mkdir()
    (no_scope / "docs" / "DATA.md").write_text(text, encoding="utf-8")
    assert [("DATA.md" in w) for w in check_docs.check_history()] == ([True] if warned else [])


@pytest.mark.parametrize(
    ("text", "spans"),
    [
        ("`a.md` '있는 제목' 절", ["`a.md` '있는 제목' 절"]),
        ("고른 정책(`docs/glossary.md`)은", ["(`docs/glossary.md`)"]),
        ("SPEC.md 승인 지점 절의 항목", ["SPEC.md 승인 지점 절"]),
        ("SPEC.md 13절 2번", ["SPEC.md 13절"]),
        ("SPEC 9절", ["SPEC 9절"]),
        ("SPEC.md 5.2절", ["SPEC.md 5.2절"]),
        ("용어는 `docs/glossary.md`다. `a.md`에 있다.", []),
        ("시작 명세는 `SPEC.md`다.", []),
    ],
    ids=[
        "title_quote",
        "glossary_pointer",
        "spec_title",
        "spec_number",
        "spec_short",
        "spec_dotted",
        "plain_path",
        "plain_spec",
    ],
)
def test_check_refs_flags_pointer(text, spans):
    assert names_each(spans, check_docs.check_refs(text))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("근거는 첫 절의 기각한 대안이다", 1),
        ("마지막 행의 분산은 크다", 1),
        ("모델 선택(위 행)으로 고른다", 1),
        ("아래 금액 모델 행", 0),
        ("위 행동을 고른다", 0),
        ("다음 절차를 따른다", 0),
        ("다음 절에서 다룬다", 1),
        ("마지막 행에는 합계가 있다", 1),
        ("위 행렬을 곱한다", 0),
        ("아래 절반을 쓴다", 0),
        ("위 행위를 막는다", 0),
        ("다음 행사를 연다", 0),
        ("범위는 위 절을 따른다", 1),
        ("앞 절의 정의", 1),
        ("고정했으므로(위 절) 행 순서", 1),
        ("위 문단으로 돌아간다", 1),
    ],
)
def test_check_style_flags_position_refs(text, expected):
    found = [w for w in check_docs.check_style(text, "x.md") if w.startswith("위치 참조")]
    assert len(found) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("출발점으로 삼는다.  - class transformation", 1),
        ("IPW 배정 확률은 설계값 1/3.- 병행: 쉬운 판", 1),
        ("끝난다. - 다음 항목", 1),
        ("- 첫 항목\n- 둘째 항목", 0),
        ("범위는 0.1 - 0.3이다", 0),
        ("S-learner와 T-learner", 0),
        ("코드 `a.- b`와 블록", 0),
        ("```\nx = a.- b\n```", 0),
    ],
)
def test_check_merged_flags_items_on_one_line(text, expected):
    assert len(check_docs.check_merged(text, "x.md")) == expected


def test_run_blocks_merged_items():
    errors, _ = check_docs.run("", "끝난다.- 다음 항목", "docs/plans/M2-PLAN.md")
    assert any(e.startswith("목록 두 항목이 한 줄에 붙음") for e in errors)


def _style_kinds(text, path="docs/MODELING.md"):
    return [w.split(":")[0] for w in check_docs.check_style(text, path)]


def test_check_style_flags_cleft():
    assert _style_kinds("넣은 것은 고친 것이다.") == ["분열문"]


def test_check_style_flags_missing_alternative():
    assert _style_kinds("- 기각한 대안: 없음(사용자 지시)") == ["기각한 대안이 없음"]


def test_check_style_alternative_docs_only():
    assert _style_kinds("- 기각한 대안: 없음", "CLAUDE.md") == []


def test_check_style_passes_plain_geoseun():
    assert _style_kinds("메인이 정한 것은 정본에 반영한다.", "x.md") == []


@pytest.mark.parametrize(
    ("text", "flagged"),
    [("a\n\n\nb", True), ("a\n\n```\nx\n\n\ny\n```\nb", False)],
    ids=["prose", "code_block"],
)
def test_check_blank_runs_ignores_code_blocks(text, flagged):
    assert bool(check_docs.check_blank_runs(text, "x.md")) is flagged


CITED = (
    "방법 (Künzel et al., 2019; Jaśkowski & Jaroszewicz, 2012). Kennedy (2023)는 쓴다. "
    "(causalml, 2026). Radcliffe (2007)도.\n"
    "## 참고문헌\n\n"
    "- causalml. (2026). Doc.\n"
    "- Jaśkowski, M., & Jaroszewicz, S. (2012). Title.\n"
    "- Künzel, S. R. (2019). Title.\n"
    "- Radcliffe, N. J. (2007). Title.\n"
)


def test_check_citations_flags_missing_reference():
    assert [("2023" in e) for e in check_docs.check_citations(CITED)] == [True]


def test_check_citations_ignores_non_citation_parens():
    text = "(표본 10000명) 고객 (2000명) (2026-11-24)\n## 참고문헌\n"
    assert check_docs.check_citations(text) == []


@pytest.mark.parametrize(("path", "errors"), [("docs/THEORY.md", 1), ("docs/DATA.md", 0)])
def test_check_file_checks_citations_in_theory_only(no_scope, path, errors):
    (no_scope / "docs").mkdir()
    (no_scope / path).write_text(CITED, encoding="utf-8")
    assert len(check_docs.check_file(path)[0]) == errors


COPY = "분할은 고객 단위로 층화해 학습, 검증, 시험 세트로 나눈다."
GLOSSARY_LINE = "용어집에 적은 다른 문장이 여기에 꽤 길게 하나 있다고 하자."


@pytest.fixture
def record_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DATA.md").write_text(f"{COPY}\n", encoding="utf-8")
    (tmp_path / "docs" / "glossary.md").write_text(f"{GLOSSARY_LINE}\n", encoding="utf-8")
    monkeypatch.setattr(
        check_docs,
        "scope_files",
        lambda: [tmp_path / "docs" / "DATA.md", tmp_path / "docs" / "glossary.md"],
    )


@pytest.mark.parametrize(
    ("text", "path", "counts"),
    [
        (COPY, "docs/plans/M2-PLAN.md", (1, 0)),
        (COPY, "docs/MODELING.md", (0, 0)),
        (GLOSSARY_LINE, "docs/plans/M3-PLAN.md", (0, 1)),
    ],
    ids=["record_copy_in_plan", "record_copy_in_record", "glossary_copy"],
)
def test_check_copies_counts(record_docs, text, path, counts):
    errors, warnings = check_docs.check_copies(text, path)
    assert (len(errors), len(warnings)) == counts


SCOPE_PATHS = [
    ("SPEC.md", False, False),
    ("CLAUDE.md", True, True),
    ("docs/plans/M2-PLAN.md", True, False),
    ("docs/history/DATA.md", False, False),
    ("artifacts/ANA-003/summary.md", False, True),
    (".claude/skills/marimo-notebook/SKILL.md", False, True),
    (".claude/skills/run-evaluation/SKILL.md", True, True),
    (".claude/skills/run-analysis/SKILL.md", True, True),
    ("src/uplift/eda.py", False, True),
    (".claude/harness/CHANGELOG.md", False, True),
    ("tests/test_check_docs.py", False, False),
    ("new-folder/notes.md", True, True),
]


@pytest.mark.parametrize(("path", "scope"), [(p, s) for p, s, _ in SCOPE_PATHS])
def test_in_scope_is_everything_except_the_exclusions(path, scope):
    assert check_docs.in_scope(path) is scope


@pytest.mark.parametrize(("path", "inbound"), [(p, i) for p, _, i in SCOPE_PATHS])
def test_is_inbound_skips_docs_and_tests(path, inbound):
    assert check_docs.is_inbound(path) is inbound


def test_check_copies_ignores_matches_in_the_same_file(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    line = "mens 지난 1년 남성 상품 구매 여부를 나타내는 이진 열이다."
    (tmp_path / "THEORY.md").write_text(f"{line}\n{line}\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "THEORY.md"])
    assert check_docs.check_copies(line, "THEORY.md") == ([], [])


PENDING = "docs/X.md | 가 결정 | 함수에 반영"


@pytest.fixture
def one_pending(monkeypatch):
    monkeypatch.setattr(check_docs, "pending_items", lambda: [PENDING])


@pytest.mark.parametrize(
    ("changed", "record_diff", "messages", "blocked"),
    [
        (["src/uplift/value.py"], "+- 정본: 아직 없음. 새 항목", "기능 추가", True),
        (["src/uplift/value.py"], "-- 정본: 아직 없음. 함수에 반영\n+- 정본: `a.py`", "", False),
        (["src/uplift/value.py"], "", "기능 추가\n\n정본 칸: 반영 없음", False),
        (["docs/PROBLEM.md", ".claude/harness/check_docs.py"], "", "", False),
        (["analyses/ANA-004-x.py"], "", "", True),
        (["analyses/CLAUDE.md", "experiments/TEMPLATE.md"], "", "", False),
    ],
)
def test_check_canon_requires_canon_edit_when_code_changes(
    one_pending, changed, record_diff, messages, blocked
):
    assert bool(check_docs.check_canon(changed, record_diff, messages)) is blocked


def test_check_canon_lists_pending_item(one_pending):
    errors = check_docs.check_canon(["src/uplift/value.py"], "", "")
    assert any(PENDING in e for e in errors)


def test_check_canon_passes_no_pending(monkeypatch):
    monkeypatch.setattr(check_docs, "pending_items", list)
    assert check_docs.check_canon(["src/uplift/value.py"], "", "") == []


def test_run_blocks_pending_file():
    errors, _ = check_docs.run("", "| 결정 | 반영할 곳 |", check_docs.PENDING_FILE)
    assert any("--pending" in e for e in errors)


def test_pending_lists_unresolved_entries(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MODELING.md").write_text(
        "## 2026-11-25 가 결정\n\n- 정본: 아직 없음. 정책 함수에 반영한다.\n\n"
        "## 2026-11-24 나 결정\n\n- 정본: `src/uplift/eda.py`\n",
        encoding="utf-8",
    )
    check_docs.pending()
    assert capsys.readouterr().out.splitlines() == [
        "docs/MODELING.md | 2026-11-25 가 결정 | 정책 함수에 반영한다"
    ]


@pytest.mark.parametrize(
    ("path", "errors"),
    [("docs/MODELING.md", 0), ("docs/plans/M2-PLAN.md", 2)],
    ids=["record", "plan"],
)
def test_run_skips_reference_checks_in_records(no_scope, path, errors):
    text = '`docs/DATA.md` "분할" 절과 고른 정책(`docs/glossary.md`)'
    assert len(check_docs.run("", text, path)[0]) == errors


@pytest.mark.parametrize("path", ["scripts/CLAUDE.md", ".claude/skills/run-evaluation/SKILL.md"])
def test_check_copies_skips_record_matches_in_canon(tmp_path, monkeypatch, path):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DATA.md").write_text(f"{COPY}\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "docs" / "DATA.md"])
    assert check_docs.check_copies(COPY, path) == ([], [])


@pytest.fixture
def canon_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    for folder, name in [("docs", "DATA.md"), ("scripts", "CLAUDE.md")]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / name).write_text(f"{COPY}\n", encoding="utf-8")
    monkeypatch.setattr(
        check_docs,
        "scope_files",
        lambda: [tmp_path / "docs" / "DATA.md", tmp_path / "scripts" / "CLAUDE.md"],
    )


def test_check_copies_canon_copy_warns_in_harness(canon_copy):
    errors, warnings = check_docs.check_copies(COPY, "CLAUDE.md")
    assert (len(errors), len(warnings)) == (0, 1)


def test_check_copies_record_copy_errors_in_glossary(canon_copy):
    errors, _ = check_docs.check_copies(COPY, "docs/glossary.md")
    assert len(errors) == 1


def test_run_allows_spec_refs_in_glossary_first_use_column(no_scope):
    errors, _ = check_docs.run("", "| 정책 가치 | 뜻 | SPEC.md 5절 |", "docs/glossary.md")
    assert errors == []


def test_run_flags_spec_refs_in_glossary_definition(no_scope):
    errors, _ = check_docs.run(
        "", "| 통계적 성공 | 완료 기준(SPEC.md 13절 2번)의 판정. | x |", "docs/glossary.md"
    )
    assert names_each(["SPEC.md 13절"], errors)


def _named(phrases: list[str], warnings: list[str]) -> set[str]:
    return {p for p in phrases if any(f'"{p}"' in w for w in warnings)}


def test_check_removed_ignores_phrases_under_ten_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "a.md").write_text("`docs/a.md`와 `docs/abcde.md`가 남았다.\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "a.md"])
    monkeypatch.setattr(check_docs, "all_files", lambda: ())
    warnings = check_docs.check_removed("`docs/a.md`와 `docs/abcde.md`", "")
    assert _named(["docs/a.md", "docs/abcde.md"], warnings) == {"docs/abcde.md"}


def test_check_removed_skips_paths_that_still_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "a.md").write_text(
        "`docs/THEORY.md`, `artifacts/<ID>/summary.md`, `docs/plans/`, `summary.md`, "
        '`docs/gone-file.md`, "지운 문장이 여기 남았다"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "a.md"])
    monkeypatch.setattr(
        check_docs,
        "all_files",
        lambda: ("docs/THEORY.md", "artifacts/ANA-001/summary.md", "docs/plans/ROADMAP.md"),
    )
    old = (
        "`docs/THEORY.md` `artifacts/<ID>/summary.md` `docs/plans/` `summary.md` "
        '`docs/gone-file.md` "지운 문장이 여기 남았다"'
    )
    phrases = [
        "docs/THEORY.md",
        "artifacts/<ID>/summary.md",
        "docs/plans/",
        "summary.md",
        "docs/gone-file.md",
        "지운 문장이 여기 남았다",
    ]
    warnings = check_docs.check_removed(old, "")
    assert _named(phrases, warnings) == {"docs/gone-file.md", "지운 문장이 여기 남았다"}


NUMBERS = [0.0766, 0.124, 21306.0, 2.1]


@pytest.mark.parametrize(
    "text",
    ["효과 0.077", "비율 12.4%", "21,306명", "차이 -2.1"],
    ids=["rounding", "percent", "thousands", "negative"],
)
def test_unmatched_numbers_matches_table_value(text):
    assert check_docs.unmatched_numbers(text, NUMBERS) == []


@pytest.mark.parametrize(
    "text",
    [
        "ANA-001",
        "2026-11-26",
        "`ate.csv`",
        "95% 구간",
        "검정력 80%",
        "p < 0.001",
        "기준 0.1",
        "방문 1회",
        "학습 세트 44,800명, 18개, 100% 발송, 200 이상, 30%",
    ],
    ids=[
        "exp_id",
        "date",
        "filename",
        "ci_level",
        "power",
        "p_value",
        "threshold",
        "count",
        "integers",
    ],
)
def test_unmatched_numbers_skips_non_values(text):
    assert check_docs.unmatched_numbers(text, NUMBERS) == []


@pytest.mark.parametrize(
    ("text", "values", "missing"),
    [
        ("효과 0.078, 1.2배, 30%", NUMBERS, ["0.078", "1.2"]),
        ("비율 12.5%, 효과 0.25", [0.5], ["12.5%", "0.25"]),
    ],
)
def test_unmatched_numbers_flags_mismatch(text, values, missing):
    assert check_docs.unmatched_numbers(text, values) == missing


@given(
    value=st.floats(-1e5, 1e5, allow_nan=False),
    digits=st.integers(1, 4),
    percent=st.booleans(),
)
def test_unmatched_numbers_accepts_rounded_table_value(value, digits, percent):
    text = f"값 {value * 100:.{digits}f}%" if percent else f"값 {value:.{digits}f}"
    assert check_docs.unmatched_numbers(text, [abs(value)]) == []


def _summary(root: Path, folder: str, body: str, tables: dict[str, str]) -> str:
    path = root / "artifacts" / folder
    (path / "tables").mkdir(parents=True, exist_ok=True)
    for name, content in tables.items():
        (path / "tables" / name).write_text(content, encoding="utf-8")
    (path / "summary.md").write_text(body, encoding="utf-8")
    return f"artifacts/{folder}/summary.md"


def test_check_summary_matches_numbers_against_cited_tables_only(no_scope):
    path = _summary(
        no_scope,
        "ANA-009",
        "## 결론 0.5\n\n값 0.5와 3(`tables/a.csv`).\n\n값 0.25(`tables/a.csv`).\n",
        {"a.csv": "x,y\n0.5,3\n", "b.json": '{"v": [0.25]}'},
    )
    assert [("0.25" in e) for e in check_docs.check_summary(path)] == [True]


def test_check_summary_skips_folder_without_tables(no_scope):
    (no_scope / "artifacts" / "EXP-009").mkdir(parents=True)
    (no_scope / "artifacts" / "EXP-009" / "summary.md").write_text("0.7", encoding="utf-8")
    assert check_docs.check_summary("artifacts/EXP-009/summary.md") == []


@pytest.fixture
def summary_cli(no_scope, monkeypatch):
    def write(body: str) -> None:
        _summary(no_scope, "EXP-009", body, {"a.csv": "x\n0.5\n"})

    monkeypatch.setattr(check_docs.sys, "argv", ["x", "--summary", "artifacts/EXP-009/summary.md"])
    return write


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("학습 세트 44,800명.\n\n## 결론 0.5\n\n값 0.5, 100% 발송.\n", 0),
        ("## 결론 0.5\n\n값 0.7.\n", 1),
    ],
    ids=["matching", "mismatch"],
)
def test_summaries_exit_code(summary_cli, body, code):
    summary_cli(body)
    assert check_docs.summaries() == code


def test_summaries_prints_unmatched_number(summary_cli, capsys):
    summary_cli("## 결론 0.5\n\n값 0.7.\n")
    check_docs.summaries()
    assert "0.7" in capsys.readouterr().out


def test_table_values_reads_numbers_in_column_labels(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "a.csv").write_text("newbie,recency=9\n0,0.1\n", encoding="utf-8")
    assert sorted(check_docs.table_values(tmp_path)) == [0.0, 0.1, 9.0]


def run_hook(monkeypatch, capsys, file_path: Path, content: str) -> str:
    payload = {"tool_input": {"file_path": str(file_path), "content": content}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    check_docs.hook()
    return capsys.readouterr().out


def test_hook_ignores_files_outside_repo(no_scope, monkeypatch, capsys):
    outside = no_scope.parent / "other" / "x.md"
    assert run_hook(monkeypatch, capsys, outside, "SPEC.md 13절과 위 절") == ""


def test_hook_blocks_on_error(no_scope, monkeypatch, capsys):
    out = run_hook(monkeypatch, capsys, no_scope / "docs" / "plans" / "M2.md", "SPEC.md 13절")
    assert json.loads(out)["decision"] == "block"


def test_hook_passes_warnings_as_context(no_scope, monkeypatch, capsys):
    out = run_hook(monkeypatch, capsys, no_scope / "x.md", "범위는 위 절을 따른다")
    assert "additionalContext" in json.loads(out)["hookSpecificOutput"]
