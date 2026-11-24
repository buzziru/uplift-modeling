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
        '`docs/DATA.md` "처치 x 깔때기 단계로 층화한다" 절',
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


def test_check_spec_flags_location_lines_outside_section_10():
    text = (
        "## 3. 데이터\n\n기록: `docs/DATA.md`\n"
        "- 분할: `scripts/splits.yaml`, `src/uplift/split.py`.\n"
        "## 10. 문서 체계\n\n실험 양식은 `experiments/TEMPLATE.md`가 정본이다.\n"
        "## 14. 미결 사항\n\n(`docs/THEORY.md` 절)\n"
    )
    assert check_docs.check_spec(text) == [
        "SPEC.md 3줄: 위치를 가리키는 줄",
        "SPEC.md 3줄: 경로 docs/DATA.md",
        "SPEC.md 4줄: 경로 scripts/splits.yaml",
        "SPEC.md 4줄: 경로 src/uplift/split.py",
    ]
