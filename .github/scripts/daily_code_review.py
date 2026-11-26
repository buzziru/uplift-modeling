"""그날 병합된 PR의 코드를 Claude(Messages API)로 리뷰해 이슈 하나를 만든다.

입력은 바뀐 코드의 diff, 바뀐 파일 전체, 맥락용 코드 전체, 기준 문서, 열린 코드 리뷰 이슈다.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

CRITERIA = Path(".claude/rules/code-review.md")
PROMPT = Path(".github/prompts/daily-code-review.md")
LABEL = "code-review"
NO_FINDINGS = "NO_FINDINGS"
CODE_DIRS = ("src/", "scripts/", "experiments/", "analyses/", "tests/", ".github/scripts/")
CONTEXT_GLOBS = ("src/uplift/*.py", "scripts/*.py", "experiments/*/run.py")
MAX_CHARS = 300_000  # 같은 방식의 meet-rag 일일 리뷰에서 시험한 상한
MAX_TOKENS = 64000  # 첫 실행에서 사고에 약 3만 토큰을 써 32000에서 답이 잘렸다


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def owned(prs: list[dict], owner: str) -> list[dict]:
    return [p for p in prs if p["author"]["login"] == owner]


def code_diffs(number: int, diff: str) -> list[dict]:
    out = []
    for part in re.split(r"(?m)^(?=diff --git )", diff):
        m = re.match(r"diff --git a/\S+ b/(\S+)", part)
        if m and m[1].startswith(CODE_DIRS) and m[1].endswith(".py"):
            out.append({"pr": number, "path": m[1], "diff": part})
    return out


def numbered(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{i}\t{line}" for i, line in enumerate(lines, 1))


def size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False))


def fill(groups: list[tuple[str, list[dict]]], limit: int) -> tuple[dict, list[str]]:
    """앞 그룹부터, 그룹 안에서는 짧은 것부터 JSON 길이 상한까지 넣는다. 뺀 항목은 이름으로 돌려준다."""
    room, kept, omitted = limit, {}, []
    for name, items in groups:
        kept[name] = []
        for item in sorted(items, key=size):
            if size(item) <= room:
                room -= size(item)
                kept[name].append(item)
            else:
                omitted.append(f"{name} {item['path']}")
    return kept, omitted


def review_input(
    prs: list[dict], diffs: list[dict], root: Path, open_issues: list[dict]
) -> tuple[dict, list[str]]:
    changed = sorted({d["path"] for d in diffs if (root / d["path"]).is_file()})
    context = sorted(
        {str(p.relative_to(root)).replace("\\", "/") for g in CONTEXT_GLOBS for p in root.glob(g)}
        - set(changed)
    )
    base = {
        "prs": prs,
        "criteria": (root / CRITERIA).read_text(encoding="utf-8"),
        "open_review_issues": open_issues,
    }
    groups = [
        ("diffs", diffs),
        ("changed_files", [{"path": p, "text": numbered(root / p)} for p in changed]),
        ("context_files", [{"path": p, "text": numbered(root / p)} for p in context]),
    ]
    all_omitted = [f"{name} {item['path']}" for name, items in groups for item in items]
    skeleton = base | {name: [] for name, _ in groups} | {"omitted": all_omitted}
    room = MAX_CHARS - size(skeleton)
    if room < 0:
        raise ValueError(
            f"기본 입력(기준 문서, 열린 이슈, 경로 목록)만으로 {MAX_CHARS}자를 넘는다: {size(skeleton)}자"
        )
    kept, omitted = fill(groups, room)
    return base | kept | {"omitted": omitted}, omitted


def issue_body(text: str, model: str, failure: str | None, omitted: list[str]) -> str | None:
    if text == NO_FINDINGS and not omitted:
        return None
    lines = ["지적 없음." if text == NO_FINDINGS else text, "", "---", f"작성 모델: `{model}`"]
    if failure:
        lines[-1] += f" ({failure}로 기본 모델이 실패해 대체 모델로 작성)"
    if omitted:
        lines.append(f"크기 상한으로 뺀 항목: {', '.join(omitted)}")
    return "\n".join(lines) + "\n"


def ask(client, model: str, content: str):
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        output_config={"effort": "high"},
        system=PROMPT.read_text(encoding="utf-8"),
        messages=[{"role": "user", "content": content}],
    ) as stream:
        response = stream.get_final_message()
    print(f"stop={response.stop_reason} model={response.model} usage={response.usage}")
    return response


def ask_with_fallback(client, content: str, api_error: type[Exception]):
    try:
        response = ask(client, os.environ["MODEL"], content)
        if response.stop_reason != "refusal":
            return response, None
        failure = "거절"
    except api_error as e:
        print(f"{os.environ['MODEL']} 호출 실패: {type(e).__name__}: {e}")
        failure = f"API 오류({type(e).__name__})"
    return ask(client, os.environ["FALLBACK_MODEL"], content), failure


def main() -> None:
    import anthropic

    repo, owner, day = os.environ["GITHUB_REPOSITORY"], os.environ["OWNER"], os.environ["DAY"]
    views = [
        json.loads(gh("pr", "view", n, "-R", repo, "--json", "number,title,author"))
        for n in os.environ["PR_NUMBERS"].split()
    ]
    prs = [{"number": p["number"], "title": p["title"]} for p in owned(views, owner)]
    diffs = [
        d
        for p in prs
        for d in code_diffs(p["number"], gh("pr", "diff", str(p["number"]), "-R", repo))
    ]
    if not diffs:
        print("병합된 코드 변경이 없어 리뷰하지 않는다")
        return
    open_issues = json.loads(
        gh(
            "issue",
            "list",
            "-R",
            repo,
            "--label",
            LABEL,
            "--state",
            "open",
            "--json",
            "number,title,body",
        )
    )
    data, omitted = review_input(prs, diffs, Path("."), open_issues)
    content = json.dumps(data, ensure_ascii=False)
    print(f"입력 {len(content)}자, 뺀 항목 {len(omitted)}개")
    client = anthropic.Anthropic()  # ANTHROPIC_FEDERATION_* 환경 변수로 ID federation 인증
    response, failure = ask_with_fallback(client, content, anthropic.APIError)
    if response.stop_reason != "end_turn":
        raise SystemExit(f"응답이 끝나지 않았다: {response.stop_reason}")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    body = issue_body(text, response.model, failure, omitted)
    if body is None:
        print("지적이 없어 이슈를 만들지 않는다")
        return
    gh(
        "label",
        "create",
        LABEL,
        "-R",
        repo,
        "--color",
        "D4C5F9",
        "--description",
        "일일 코드 리뷰",
        "--force",
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
        f.write(body)
    print(
        gh(
            "issue",
            "create",
            "-R",
            repo,
            "--title",
            f"코드 리뷰 {day}",
            "--label",
            LABEL,
            "--body-file",
            f.name,
        )
    )


if __name__ == "__main__":
    main()
