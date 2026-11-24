"""문서와 하네스 파일의 정합 검사.

- 없는 절 가리키기(오류): `경로` "제목" 절, SPEC.md N절이 실제 제목을 가리키는지 본다.
- 사본 문장(알림): 새로 쓴 문장이 다른 문장과 거의 같은지 본다.
- 지운 표현이 남은 곳(알림): 지운 따옴표·백틱 표현이 다른 파일에 남았는지 본다.
- 이미 쓰는 낱말의 새 정의(알림): "X은/는 ...이다" 꼴의 X가 이미 다른 곳에 쓰이는지 본다.

실행:
  uv run python .claude/harness/check_docs.py           브랜치 변경(origin/main...HEAD) 검사, 오류면 exit 1
  uv run python .claude/harness/check_docs.py --hook    PostToolUse hook. stdin의 Edit/Write 입력만 검사
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = [
    "SPEC.md",
    "CLAUDE.md",
    "docs/*.md",
    ".claude/agents/*.md",
    ".claude/rubrics/*.md",
    ".claude/skills/run-evaluation/SKILL.md",
]
SIMILAR = 0.7
MIN_LEN = 25


def scope_files() -> list[Path]:
    return sorted({p for pattern in SCOPE for p in ROOT.glob(pattern)})


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def headings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [m.group(1).strip() for m in re.finditer(r"^#+\s+(.+)$", text, re.MULTILINE)]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=다\.)\s+|\n+", text)
    return [s.strip(" -|*") for s in parts if len(s.strip(" -|*")) >= MIN_LEN]


def grams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s)
    return {s[i : i + 3] for i in range(len(s) - 2)}


def similarity(a: str, b: str) -> float:
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb) if ga and gb else 0.0


def check_refs(text: str) -> list[str]:
    errors = []
    for path, title in re.findall(r"`([^`]+\.md)` \"([^\"]+)\" 절", text):
        target = ROOT / path
        if not target.exists():
            errors.append(f"없는 파일: `{path}`")
        elif not any(title in h for h in headings(target)):
            errors.append(f'없는 절: `{path}` "{title}"')
    spec_numbers = {
        m.group(1) for h in headings(ROOT / "SPEC.md") if (m := re.match(r"(\d+)\.", h))
    }
    for n in re.findall(r"SPEC\.md (\d+)절", text):
        if n not in spec_numbers:
            errors.append(f"없는 절: SPEC.md {n}절")
    return errors


def check_copies(new_text: str, path: str) -> list[str]:
    """새 문장이 다른 파일의 문장과 거의 같거나, 같은 파일 안에 두 번 이상 있으면 알린다."""
    warnings = []
    for f in scope_files():
        same_file = rel(f) == path
        olds = sentences(f.read_text(encoding="utf-8"))
        for s in sentences(new_text):
            matches = [o for o in olds if similarity(s, o) >= SIMILAR]
            if len(matches) > (1 if same_file else 0):
                other = s if same_file else matches[0]
                warnings.append(
                    f'사본 의심: {path} "{s[:40]}…" ≈ {rel(f)} "{other[:40]}…"'
                )
    return warnings


def check_removed(old_text: str, new_text: str) -> list[str]:
    phrases = set(re.findall(r"`([^`\n]{4,})`|\"([^\"\n]{4,})\"", old_text))
    removed = {p for pair in phrases for p in pair if p and p not in new_text}
    warnings = []
    for f in scope_files():
        body = f.read_text(encoding="utf-8")
        warnings += [
            f'지운 표현이 남음: "{p}" in {rel(f)}' for p in removed if p in body
        ]
    return warnings


def check_redefine(new_text: str, path: str) -> list[str]:
    warnings = []
    others = "\n".join(
        f.read_text(encoding="utf-8") for f in scope_files() if rel(f) != path
    )
    for term in re.findall(
        r"^\s*(?:- )?([가-힣A-Za-z ]{2,12}?)(?:은|는) [^\n]*?이다[.:]",
        new_text,
        re.MULTILINE,
    ):
        if others.count(term.strip()) >= 2:
            warnings.append(f'이미 쓰는 낱말을 새로 정의함: "{term.strip()}" ({path})')
    return warnings


def run(old_text: str, new_text: str, path: str) -> tuple[list[str], list[str]]:
    errors = check_refs(new_text)
    warnings = check_copies(new_text, path) + check_removed(old_text, new_text)
    warnings += check_redefine(new_text, path)
    return errors, warnings


def in_scope(path: str) -> bool:
    return path in {rel(f) for f in scope_files()}


def hook() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = Path(tool_input.get("file_path", ""))
    if not file_path.is_absolute() or ROOT not in file_path.parents:
        return
    path = rel(file_path)
    if not in_scope(path):
        return
    edits = tool_input.get("edits") or [tool_input]
    old = "\n".join(e.get("old_string", "") for e in edits)
    new = "\n".join(e.get("new_string") or e.get("content", "") for e in edits)
    errors, warnings = run(old, new, path)
    lines = [f"오류: {e}" for e in errors] + [f"알림: {w}" for w in warnings]
    if not lines:
        return
    message = "문서 정합 검사(.claude/harness/check_docs.py)\n" + "\n".join(lines)
    if errors:
        print(json.dumps({"decision": "block", "reason": message}, ensure_ascii=False))
    else:
        out = {"hookEventName": "PostToolUse", "additionalContext": message}
        print(json.dumps({"hookSpecificOutput": out}, ensure_ascii=False))


def branch() -> int:
    base = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if base.returncode != 0:
        print("origin/main이 없어 문서 정합 검사를 건너뛴다(git fetch 뒤 다시 돌린다).")
        return 0
    diff = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "-U0", "origin/main...HEAD", "--"]
        + [rel(f) for f in scope_files()],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    errors, warnings = [], []
    for chunk in re.split(r"^diff --git ", diff, flags=re.MULTILINE)[1:]:
        m = re.search(r"^\+\+\+ b/(.+)$", chunk, re.MULTILINE)
        if not m:
            continue
        path = m.group(1)
        added = "\n".join(
            line[1:]
            for line in chunk.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = "\n".join(
            line[1:]
            for line in chunk.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )
        e, w = run(removed, added, path)
        errors += e
        warnings += w
    for w in warnings:
        print(f"알림: {w}")
    for e in errors:
        print(f"오류: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--hook" in sys.argv:
        hook()
    else:
        sys.exit(branch())
