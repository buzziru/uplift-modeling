import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[1] / ".claude" / "harness" / "check_docs.py"
)
assert SPEC and SPEC.loader
check_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_docs)


@pytest.mark.parametrize(
    "text",
    [
        '`docs/DATA.md` "처치 x 퍼널 단계로 층화한다" 절',
        "`docs/ENGINEERING.md` DuckDB 절",
        "규칙은 docs/DATA.md 적재 절.",
        "`docs/EVALUATION.md`의 모델 선택 항목",
        "`docs/DATA.md#분할`",
        "`docs/DATA.md`에 적은 분할 항목",
    ],
)
def test_check_inbound_flags_record_citations(text):
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
    assert check_docs.history_ratio(text) == pytest.approx(3 / 10)


def test_history_ratio_is_zero_without_history():
    assert check_docs.history_ratio("## 제목\n- 결정: a\n") == 0.0


def test_check_refs_flags_title_refs_and_glossary_pointers(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "SPEC.md").write_text("## 1. 목적\n", encoding="utf-8")
    assert check_docs.check_refs("`a.md` '있는 제목' 절") == [
        "절 제목 인용: \"`a.md` '있는 제목' 절\""
    ]
    assert check_docs.check_refs("고른 정책(`docs/glossary.md`)은") == [
        '용어집 가리키기: "(`docs/glossary.md`)"'
    ]
    assert check_docs.check_refs("용어는 `docs/glossary.md`다. `a.md`에 있다.") == []


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


def test_check_style_flags_cleft_and_missing_alternative():
    text = "넣은 것은 고친 것이다.\n- 기각한 대안: 없음(사용자 지시)"
    kinds = [w.split(":")[0] for w in check_docs.check_style(text, "docs/MODELING.md")]
    assert kinds == ["분열문", "기각한 대안이 없음"]
    assert check_docs.check_style("- 기각한 대안: 없음", "CLAUDE.md") == []
    assert check_docs.check_style("메인이 정한 것은 정본에 반영한다.", "x.md") == []


def test_check_blank_runs_ignores_code_blocks():
    assert check_docs.check_blank_runs("a\n\n\nb", "x.md")
    assert check_docs.check_blank_runs("a\n\n```\nx\n\n\ny\n```\nb", "x.md") == []


def test_check_citations_matches_parenthetical_and_inline_cites():
    text = (
        "방법 (Künzel et al., 2019; Jaśkowski & Jaroszewicz, 2012). Kennedy (2023)는 쓴다. "
        "(causalml, 2026). Radcliffe (2007)도.\n"
        "## 참고문헌\n\n"
        "- causalml. (2026). Doc.\n"
        "- Jaśkowski, M., & Jaroszewicz, S. (2012). Title.\n"
        "- Künzel, S. R. (2019). Title.\n"
        "- Radcliffe, N. J. (2007). Title.\n"
    )
    assert check_docs.check_citations(text) == ["참고문헌에 없는 인용: kennedy 2023"]
    negative = "(표본 10000명) 고객 (2000명) (2026-11-24)\n## 참고문헌\n"
    assert check_docs.check_citations(negative) == []


def test_check_copies_errors_on_record_copies_outside_records(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    copy = "분할은 고객 단위로 층화해 학습, 검증, 시험 세트로 나눈다."
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DATA.md").write_text(f"{copy}\n", encoding="utf-8")
    (tmp_path / "docs" / "glossary.md").write_text(
        "용어집에 적은 다른 문장이 여기에 꽤 길게 하나 있다고 하자.\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        check_docs,
        "scope_files",
        lambda: [tmp_path / "docs" / "DATA.md", tmp_path / "docs" / "glossary.md"],
    )
    errors, warnings = check_docs.check_copies(copy, "docs/plans/M2-PLAN.md")
    assert len(errors) == 1 and warnings == []
    assert check_docs.check_copies(copy, "docs/MODELING.md") == ([], [])
    errors, warnings = check_docs.check_copies(
        "용어집에 적은 다른 문장이 여기에 꽤 길게 하나 있다고 하자.", "docs/plans/M3-PLAN.md"
    )
    assert errors == [] and len(warnings) == 1


@pytest.mark.parametrize(
    ("path", "scope", "inbound"),
    [
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
    ],
)
def test_scope_is_everything_except_the_exclusions(path, scope, inbound):
    assert check_docs.in_scope(path) is scope
    assert check_docs.is_inbound(path) is inbound


def test_check_inbound_flags_plan_files_only():
    assert check_docs.check_inbound("`docs/plans/M2-PLAN.md` U3 메모", "src/uplift/value.py")
    assert check_docs.check_inbound("지금 계획은 `docs/plans/`다.", "CLAUDE.md") == []


def test_check_copies_ignores_matches_in_the_same_file(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    line = "mens 지난 1년 남성 상품 구매 여부를 나타내는 이진 열이다."
    (tmp_path / "THEORY.md").write_text(f"{line}\n{line}\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "THEORY.md"])
    assert check_docs.check_copies(line, "THEORY.md") == ([], [])


@pytest.fixture
def one_pending(monkeypatch):
    monkeypatch.setattr(check_docs, "pending_items", lambda: ["docs/X.md | 가 결정 | 함수에 반영"])


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
    errors = check_docs.check_canon(changed, record_diff, messages)
    assert bool(errors) is blocked
    if blocked:
        assert errors[-1] == "반영 대기: docs/X.md | 가 결정 | 함수에 반영"


def test_check_canon_passes_without_pending_items(monkeypatch):
    monkeypatch.setattr(check_docs, "pending_items", list)
    assert check_docs.check_canon(["src/uplift/value.py"], "", "") == []


def test_run_blocks_pending_file():
    errors, _ = check_docs.run("", "| 결정 | 반영할 곳 |", check_docs.PENDING_FILE)
    assert any("--pending" in e for e in errors)


def test_pending_lists_record_entries_without_canon(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MODELING.md").write_text(
        "## 2026-11-25 가 결정\n\n- 정본: 아직 없음. 정책 함수에 반영한다.\n\n"
        "## 2026-11-24 나 결정\n\n- 정본: `src/uplift/eda.py`\n",
        encoding="utf-8",
    )
    assert check_docs.pending() == 0
    assert capsys.readouterr().out.splitlines() == [
        "docs/MODELING.md | 2026-11-25 가 결정 | 정책 함수에 반영한다"
    ]


def test_run_skips_reference_checks_in_records():
    text = '`docs/DATA.md` "분할" 절과 고른 정책(`docs/glossary.md`)'
    assert check_docs.run("", text, "docs/MODELING.md")[0] == []
    assert len(check_docs.run("", text, "docs/plans/M2-PLAN.md")[0]) == 2


def test_check_copies_skips_record_matches_in_canon(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    copy = "분할은 고객 단위로 층화해 학습, 검증, 시험 세트로 나눈다."
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DATA.md").write_text(f"{copy}\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "docs" / "DATA.md"])
    assert check_docs.check_copies(copy, "scripts/CLAUDE.md") == ([], [])
    assert check_docs.check_copies(copy, ".claude/skills/run-evaluation/SKILL.md") == ([], [])
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "CLAUDE.md").write_text(f"{copy}\n", encoding="utf-8")
    monkeypatch.setattr(
        check_docs,
        "scope_files",
        lambda: [tmp_path / "docs" / "DATA.md", tmp_path / "scripts" / "CLAUDE.md"],
    )
    errors, warnings = check_docs.check_copies(copy, "CLAUDE.md")
    assert errors == [] and len(warnings) == 1
    assert len(check_docs.check_copies(copy, "docs/glossary.md")[0]) == 1


def test_check_refs_flags_spec_section_refs():
    assert check_docs.check_refs("SPEC.md 승인 지점 절의 항목") == [
        '시작 명세 가리키기: "SPEC.md 승인 지점 절"'
    ]
    assert check_docs.check_refs("SPEC.md 13절 2번") == ['시작 명세 가리키기: "SPEC.md 13절"']
    assert check_docs.check_refs("시작 명세는 `SPEC.md`다.") == []


def test_run_allows_spec_refs_only_in_glossary_first_use_column():
    errors, _ = check_docs.run("", "| 정책 가치 | 뜻 | SPEC.md 5절 |", "docs/glossary.md")
    assert errors == []
    errors, _ = check_docs.run(
        "", "| 통계적 성공 | 완료 기준(SPEC.md 13절 2번)의 판정. | x |", "docs/glossary.md"
    )
    assert errors == ['시작 명세 가리키기: "SPEC.md 13절"']


def test_spec_ref_catches_short_and_dotted_forms():
    assert check_docs.check_refs("SPEC 9절과 SPEC.md 5.2절") == [
        '시작 명세 가리키기: "SPEC 9절"',
        '시작 명세 가리키기: "SPEC.md 5.2절"',
    ]


def test_check_removed_ignores_phrases_under_ten_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "a.md").write_text("`docs/a.md`와 `docs/abcde.md`가 남았다.\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "a.md"])
    monkeypatch.setattr(check_docs, "all_files", lambda: ())
    old = "`docs/a.md`와 `docs/abcde.md`"
    assert check_docs.check_removed(old, "") == ['지운 표현이 남음: "docs/abcde.md" in a.md']


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
    assert sorted(check_docs.check_removed(old, "")) == [
        '지운 표현이 남음: "docs/gone-file.md" in a.md',
        '지운 표현이 남음: "지운 문장이 여기 남았다" in a.md',
    ]


def test_unmatched_numbers_rounds_scales_percent_and_skips_non_values():
    values = [0.0766, 0.124, 21306.0, 2.1]
    text = (
        "효과 0.077, 비율 12.4%, 21,306명, 차이 -2.1. "
        "ANA-001, 2026-11-26, `ate.csv`, 95% 구간, 검정력 80%, p < 0.001, 기준 0.1, 방문 1회"
    )
    assert check_docs.unmatched_numbers(text, values) == []
    assert check_docs.unmatched_numbers("효과 0.078, 1.2배, 30%", values) == ["0.078", "1.2"]


def test_unmatched_numbers_skips_integers():
    text = "학습 세트 44,800명, 18개, 100% 발송, 200 이상, 30%"
    assert check_docs.unmatched_numbers(text, [0.5]) == []
    assert check_docs.unmatched_numbers("비율 12.5%, 효과 0.25", [0.5]) == ["12.5%", "0.25"]


def test_check_summary_matches_numbers_against_cited_tables_only(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    folder = tmp_path / "artifacts" / "ANA-009"
    (folder / "tables").mkdir(parents=True)
    (folder / "tables" / "a.csv").write_text("x,y\n0.5,3\n", encoding="utf-8")
    (folder / "tables" / "b.json").write_text('{"v": [0.25]}', encoding="utf-8")
    (folder / "summary.md").write_text(
        "## 결론 0.5\n\n값 0.5와 3(`tables/a.csv`).\n\n값 0.25(`tables/a.csv`).\n", encoding="utf-8"
    )
    assert check_docs.check_summary("artifacts/ANA-009/summary.md") == [
        "tables/에 없는 수치 1건: artifacts/ANA-009/summary.md (0.25)"
    ]
    (tmp_path / "artifacts" / "EXP-009").mkdir()
    (tmp_path / "artifacts" / "EXP-009" / "summary.md").write_text("0.7", encoding="utf-8")
    assert check_docs.check_summary("artifacts/EXP-009/summary.md") == []


def test_summaries_fail_on_decimal_mismatch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    folder = tmp_path / "artifacts" / "EXP-009"
    (folder / "tables").mkdir(parents=True)
    (folder / "tables" / "a.csv").write_text("x\n0.5\n", encoding="utf-8")
    summary = folder / "summary.md"
    summary.write_text(
        "학습 세트 44,800명.\n\n## 결론 0.5\n\n값 0.5, 100% 발송.\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_docs.sys, "argv", ["x", "--summary", "artifacts/EXP-009/summary.md"])
    assert check_docs.summaries() == 0
    summary.write_text("## 결론 0.5\n\n값 0.7.\n", encoding="utf-8")
    assert check_docs.summaries() == 1
    assert (
        "오류: tables/에 없는 수치 1건: artifacts/EXP-009/summary.md (0.7)"
        in capsys.readouterr().out
    )


def test_table_values_reads_numbers_in_column_labels(tmp_path):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "a.csv").write_text("newbie,recency=9\n0,0.1\n", encoding="utf-8")
    assert sorted(check_docs.table_values(tmp_path)) == [0.0, 0.1, 9.0]
