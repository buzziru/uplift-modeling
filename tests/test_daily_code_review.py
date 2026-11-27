import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

SPEC = importlib.util.spec_from_file_location(
    "daily_code_review",
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "daily_code_review.py",
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("daily_code_review.py를 불러오지 못했다")
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)

DIFF = (
    "diff --git a/src/uplift/a.py b/src/uplift/a.py\n+x = 1\n"
    "diff --git a/docs/A.md b/docs/A.md\n+문장\n"
    "diff --git a/tests/test_a.py b/tests/test_a.py\n+def test_a(): ...\n"
)


def test_code_diffs_keeps_python_code_paths():
    assert [d["path"] for d in review.code_diffs(7, DIFF)] == ["src/uplift/a.py", "tests/test_a.py"]


def test_fill_puts_earlier_groups_first():
    first, second = {"path": "x", "t": "1234"}, {"path": "y", "t": "12"}
    kept, omitted = review.fill([("a", [first]), ("b", [second])], review.size(first))
    assert (kept, omitted) == ({"a": [first], "b": []}, ["b y"])


@pytest.fixture
def repo(tmp_path):
    for path, text in {
        ".claude/rules/code-review.md": "# 기준",
        "src/uplift/a.py": "x = 1",
        "src/uplift/b.py": "y = 2",
    }.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")
    return tmp_path


def test_review_input_moves_changed_file_out_of_context(repo):
    diffs = [{"pr": 7, "path": "src/uplift/a.py", "diff": "+x = 1"}]
    data, _ = review.review_input([], diffs, repo, [])
    paths = {k: [f["path"] for f in data[k]] for k in ("changed_files", "context_files")}
    assert paths == {"changed_files": ["src/uplift/a.py"], "context_files": ["src/uplift/b.py"]}


@pytest.mark.parametrize(
    ("text", "omitted", "has_body"),
    [("NO_FINDINGS", [], False), ("NO_FINDINGS", ["diffs x"], True), ("- [ ] a", [], True)],
    ids=["clean", "clean_but_omitted", "findings"],
)
def test_issue_body_only_when_something_to_report(text, omitted, has_body):
    assert (review.issue_body(text, "m", None, omitted) is not None) is has_body


def test_issue_body_names_fallback_failure():
    assert "거절" in review.issue_body("- [ ] a", "fallback", "거절", [])


def test_issue_body_lists_omitted_items():
    assert "diffs src/x.py" in review.issue_body(review.NO_FINDINGS, "m", None, ["diffs src/x.py"])


class FakeAPIError(Exception):
    pass


@pytest.mark.parametrize(
    ("first", "model", "failure"),
    [
        ("end_turn", "main", None),
        ("refusal", "fallback", "거절"),
        (FakeAPIError, "fallback", "API 오류(FakeAPIError)"),
    ],
    ids=["main_ok", "refusal", "api_error"],
)
def test_ask_with_fallback_picks_model(monkeypatch, first, model, failure):
    monkeypatch.setenv("MODEL", "main")
    monkeypatch.setenv("FALLBACK_MODEL", "fallback")

    def fake_ask(client, model, content):
        if model == "main" and first is FakeAPIError:
            raise FakeAPIError
        return SimpleNamespace(stop_reason=first if model == "main" else "end_turn", model=model)

    monkeypatch.setattr(review, "ask", fake_ask)
    response, got = review.ask_with_fallback(None, "{}", FakeAPIError)
    assert (response.model, got) == (model, failure)


def test_owned_drops_other_authors():
    prs = [{"number": 1, "author": {"login": "o"}}, {"number": 2, "author": {"login": "x"}}]
    assert [p["number"] for p in review.owned(prs, "o")] == [1]


@pytest.fixture(scope="module")
def big_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("repo")
    files = {".claude/rules/code-review.md": "# 기준", "src/uplift/b.py": "y = 2"}
    files |= {f"src/uplift/m{i}.py": f"v{i} = {i}" for i in range(6)}
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    diffs = [{"pr": 7, "path": f"src/uplift/m{i}.py", "diff": f"+v{i} = {i}"} for i in range(6)]
    return root, diffs


def run_review_input(big_repo, limit: int) -> tuple[dict, list[str]]:
    root, diffs = big_repo
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(review, "MAX_CHARS", limit)
        return review.review_input([{"number": 7, "title": "t"}], diffs, root, [])


def items(data: dict) -> int:
    return sum(len(data[k]) for k in ("diffs", "changed_files", "context_files"))


@pytest.fixture(scope="module")
def full_input(big_repo):
    data, omitted = run_review_input(big_repo, 10**9)
    assert omitted == []
    return data


@settings(deadline=None, max_examples=50)
@given(gap=st.integers(0, 2000))
def test_review_input_stays_under_limit_or_rejects(big_repo, full_input, gap):
    limit = review.size(full_input) - gap
    try:
        data, omitted = run_review_input(big_repo, limit)
    except ValueError:
        return
    assert review.size(data) <= limit
    assert items(data) + len(omitted) == items(full_input)


def test_review_input_omits_when_tight(big_repo, full_input):
    _, omitted = run_review_input(big_repo, review.size(full_input) - 1)
    assert omitted != []


def test_review_input_rejects_base_over_limit(repo, monkeypatch):
    monkeypatch.setattr(review, "MAX_CHARS", 0)
    with pytest.raises(ValueError, match="기본 입력"):
        review.review_input([], [], repo, [])
