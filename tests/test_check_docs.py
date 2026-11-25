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


def test_check_spec_skips_only_the_document_system_section():
    text = (
        "## 3. 데이터\n\n기록: `docs/DATA.md`\n"
        "- 분할: `scripts/splits.yaml`, `src/uplift/split.py`.\n"
        "## 10. 문서 체계\n\n실험 양식은 `experiments/TEMPLATE.md`가 정본이다.\n"
        "## 14. 미결 사항\n\n(`docs/THEORY.md` 절)\n정본: `src/uplift/policy.py`\n"
    )
    assert check_docs.check_spec(text) == [
        "SPEC.md 3줄: 위치를 가리키는 줄",
        "SPEC.md 3줄: 경로 docs/DATA.md",
        "SPEC.md 4줄: 경로 scripts/splits.yaml",
        "SPEC.md 4줄: 경로 src/uplift/split.py",
        "SPEC.md 11줄: 위치를 가리키는 줄",
        "SPEC.md 11줄: 경로 src/uplift/policy.py",
    ]


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


def test_check_style_flags_merged_items_cleft_and_missing_alternative():
    text = "출발점으로 삼는다.  - class transformation\n넣은 것은 고친 것이다.\n- 기각한 대안: 없음(사용자 지시)"
    kinds = [w.split(":")[0] for w in check_docs.check_style(text, "docs/MODELING.md")]
    assert kinds == ["목록 두 항목이 한 줄에 붙음", "분열문", "기각한 대안이 없음"]
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


def test_spec_renumbers_maps_shifted_sections_by_title():
    old = "## 1. 목적\n## 2. 데이터\n## 3. 문서 체계\n"
    new = "## 1. 목적\n## 2. 문제\n## 3. 데이터\n## 4. 문서 체계\n"
    assert check_docs.spec_renumbers(old, new) == {"2": "3", "3": "4"}


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
        ("SPEC.md", True, True),
        ("docs/plans/M2-PLAN.md", True, False),
        ("docs/history/DATA.md", False, False),
        ("artifacts/ANA-003/summary.md", False, True),
        (".claude/skills/marimo-notebook/SKILL.md", False, True),
        (".claude/skills/run-evaluation/SKILL.md", True, True),
        ("src/uplift/eda.py", False, True),
        (".claude/harness/CHANGELOG.md", False, True),
        ("tests/test_check_docs.py", False, False),
        ("new-folder/notes.md", True, True),
    ],
)
def test_scope_is_everything_except_the_exclusions(path, scope, inbound):
    assert check_docs.in_scope(path) is scope
    assert check_docs.is_inbound(path) is inbound


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


def test_check_copies_skips_canon_files(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    copy = "분할은 고객 단위로 층화해 학습, 검증, 시험 세트로 나눈다."
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DATA.md").write_text(f"{copy}\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "scope_files", lambda: [tmp_path / "docs" / "DATA.md"])
    assert check_docs.check_copies(copy, "scripts/CLAUDE.md") == ([], [])
    assert check_docs.check_copies(copy, ".claude/skills/run-evaluation/SKILL.md") == ([], [])
    assert len(check_docs.check_copies(copy, "docs/glossary.md")[0]) == 1


def test_check_refs_checks_spec_section_names(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "SPEC.md").write_text("## 5. 승인 지점\n## 7. 완료 기준\n", encoding="utf-8")
    assert check_docs.check_refs("SPEC.md 승인 지점 절의 항목") == []
    assert check_docs.check_refs("SPEC.md 모델 선택 절") == ["없는 절: SPEC.md 모델 선택 절"]
