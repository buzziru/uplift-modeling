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
    ".claude/skills/kaggle-remote-runner/SKILL.md",
    "PENDING-DECISIONS.md",
    "*/CLAUDE.md",
    "experiments/TEMPLATE.md",
]
SIMILAR = 0.7
MIN_LEN = 25
RECORDS = (
    "PROBLEM",
    "DATA",
    "MODELING",
    "EVALUATION",
    "POLICY",
    "DASHBOARD",
    "ENGINEERING",
    "NARRATIVE",
)
INBOUND = [
    "SPEC.md",
    "docs/glossary.md",
    "CLAUDE.md",
    "PENDING-DECISIONS.md",
    "*/CLAUDE.md",
    "src/**/*.py",
    "scripts/**/*.py",
    "analyses/**/*.py",
    "experiments/**/*.md",
    "experiments/**/*.py",
    "artifacts/**/*.md",
    ".claude/agents/*.md",
    ".claude/rubrics/*.md",
    ".claude/skills/**/*.md",
]
RECORD_REF = re.compile(
    r"docs/(?:" + "|".join(RECORDS) + r")\.md"
    r"(?:#[^\s)`]+|`?(?!에 항목)(?:\s*\"[^\"\n]+\")?[^|\n`]{0,20}?(?<!\d)(?:절(?!차)|항목))"
)
HISTORY_LIMIT = 0.2
SPEC_PATH = re.compile(r"`([^`\s]+\.(?:md|py|yaml|json))`")
SPEC_ALLOWED = {"docs/THEORY.md", "docs/glossary.md"}
TITLE_REF = re.compile(r"`([^`]+\.md)` [\"']([^\"'\n]+)[\"'] 절")
POSITION_REF = re.compile(
    r"(?<![가-힣])(?:첫|마지막|앞|위|아래|다음) (?:절|행|문단)"
    r"(?:(?![가-힣])|(?=[은는이가을를의에와과도만로으부까처]))"
)
MERGED_ITEM = re.compile(r"\S {2,}- \S")
CLEFT = re.compile(r"[가-힣]+[한된던운은는] 것은 [^.\n]{0,60}?(?:이다|였다|이었다)\.")
NO_ALTERNATIVE = re.compile(r"^- 기각한 대안: 없음", re.MULTILINE)
CITE_GROUP = re.compile(r"\(([^()]*\d{4}[^()]*)\)")
CITE_PART = re.compile(r"^([A-Za-zÀ-ž][^\s,]*)\D*?(\d{4})(?![\d가-힣])")
CITE_INLINE = re.compile(
    r"([A-Za-zÀ-ž][\w'-]+)(?: et al\.| & [A-Za-zÀ-ž][\w'-]+)? \((\d{4})(?![\d가-힣])"
)
REFERENCE = re.compile(r"^- ([^\s,]+?)[,.] .*?\((\d{4})", re.MULTILINE)


def scope_files() -> list[Path]:
    return sorted({p for pattern in SCOPE for p in ROOT.glob(pattern)})


def inbound_files() -> list[Path]:
    return sorted({p for pattern in INBOUND for p in ROOT.glob(pattern) if p.is_file()})


def record_files() -> list[Path]:
    return sorted((ROOT / "docs").glob("*.md"))


def check_inbound(text: str, path: str) -> list[str]:
    return [f'기록 문서 인용: {path} "{m.group(0)}"' for m in RECORD_REF.finditer(text)]


def history_ratio(text: str) -> float:
    lines = text.splitlines()
    count, inside = 0, False
    for line in lines:
        if line.startswith("- 바뀐 이력:"):
            inside = True
        elif not (inside and line.startswith("  ")):
            inside = False
            continue
        count += 1
    return count / len(lines) if lines else 0.0


def check_spec(text: str) -> list[str]:
    errors, section = [], ""
    for n, line in enumerate(text.splitlines(), 1):
        if m := re.match(r"## (\d+)\.", line):
            section = m.group(1)
        if section == "10":
            continue
        if line.startswith(("정본:", "기록:")):
            errors.append(f"SPEC.md {n}줄: 위치를 가리키는 줄")
        errors += [
            f"SPEC.md {n}줄: 경로 {p}" for p in SPEC_PATH.findall(line) if p not in SPEC_ALLOWED
        ]
    return errors


def check_history() -> list[str]:
    warnings = []
    for f in record_files():
        ratio = history_ratio(f.read_text(encoding="utf-8"))
        if ratio > HISTORY_LIMIT:
            warnings.append(f"바뀐 이력 비율 {ratio:.0%}: {rel(f)}를 docs/history/로 나눈다")
    return warnings


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
    for path, title in TITLE_REF.findall(text):
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
    warnings = []
    for f in scope_files():
        same_file = rel(f) == path
        olds = sentences(f.read_text(encoding="utf-8"))
        for s in sentences(new_text):
            matches = [o for o in olds if similarity(s, o) >= SIMILAR]
            if len(matches) > (1 if same_file else 0):
                other = s if same_file else matches[0]
                warnings.append(f'사본 의심: {path} "{s[:40]}…" ≈ {rel(f)} "{other[:40]}…"')
    return warnings


def check_removed(old_text: str, new_text: str) -> list[str]:
    phrases = set(re.findall(r"`([^`\n]{4,})`|\"([^\"\n]{4,})\"", old_text))
    removed = {p for pair in phrases for p in pair if p and p not in new_text}
    warnings = []
    for f in scope_files():
        body = f.read_text(encoding="utf-8")
        warnings += [f'지운 표현이 남음: "{p}" in {rel(f)}' for p in removed if p in body]
    return warnings


def check_redefine(new_text: str, path: str) -> list[str]:
    warnings = []
    others = "\n".join(f.read_text(encoding="utf-8") for f in scope_files() if rel(f) != path)
    for term in re.findall(
        r"^\s*(?:- )?([가-힣A-Za-z ]{2,12}?)(?:은|는) [^\n]*?이다[.:]",
        new_text,
        re.MULTILINE,
    ):
        if others.count(term.strip()) >= 2:
            warnings.append(f'이미 쓰는 낱말을 새로 정의함: "{term.strip()}" ({path})')
    return warnings


def check_style(new_text: str, path: str) -> list[str]:
    warnings = [f'위치 참조: {path} "{m.group(0)}"' for m in POSITION_REF.finditer(new_text)]
    warnings += [
        f'목록 두 항목이 한 줄에 붙음: {path} "{m.group(0)}"'
        for m in MERGED_ITEM.finditer(new_text)
    ]
    warnings += [f'분열문: {path} "{m.group(0)}"' for m in CLEFT.finditer(new_text)]
    if path.startswith("docs/"):
        warnings += [f"기각한 대안이 없음: {path}" for _ in NO_ALTERNATIVE.finditer(new_text)]
    return warnings


def check_blank_runs(text: str, path: str) -> list[str]:
    outside = re.sub(r"```.*?```", "```", text, flags=re.DOTALL)
    return [f"빈 줄이 둘 이상 이어짐: {path}"] if re.search(r"\n[ \t]*\n[ \t]*\n", outside) else []


def check_citations(text: str) -> list[str]:
    body, _, refs = text.partition("## 참고문헌")
    known = {(name.lower(), year) for name, year in REFERENCE.findall(refs)}
    cited = set()
    for group in CITE_GROUP.findall(body):
        for part in group.split(";"):
            if m := CITE_PART.match(part.strip()):
                cited.add((m.group(1).lower(), m.group(2)))
    cited |= {(name.lower(), year) for name, year in CITE_INLINE.findall(body)}
    return [f"참고문헌에 없는 인용: {name} {year}" for name, year in sorted(cited - known)]


def run(old_text: str, new_text: str, path: str) -> tuple[list[str], list[str]]:
    errors = check_refs(new_text)
    warnings = check_copies(new_text, path) + check_removed(old_text, new_text)
    warnings += check_redefine(new_text, path) + check_style(new_text, path)
    return errors, warnings


def check_file(path: str) -> tuple[list[str], list[str]]:
    target = ROOT / path
    if not path.endswith(".md") or not target.exists():
        return [], []
    text = target.read_text(encoding="utf-8")
    errors = check_citations(text) if path == "docs/THEORY.md" else []
    return errors, check_blank_runs(text, path)


def in_scope(path: str) -> bool:
    return path in {rel(f) for f in scope_files()}


def hook() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = Path(tool_input.get("file_path", ""))
    if not file_path.is_absolute() or ROOT not in file_path.parents:
        return
    path = rel(file_path)
    edits = tool_input.get("edits") or [tool_input]
    old = "\n".join(e.get("old_string", "") for e in edits)
    new = "\n".join(e.get("new_string") or e.get("content", "") for e in edits)
    errors, warnings = run(old, new, path) if in_scope(path) else ([], [])
    if in_scope(path):
        e, w = check_file(path)
        errors += e
        warnings += w
    if file_path in inbound_files():
        errors += check_inbound(new, path)
    if file_path in record_files():
        warnings += check_history()
    if path == "SPEC.md":
        errors += check_spec(file_path.read_text(encoding="utf-8"))
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
        + [f":(glob){p}" for p in SCOPE],
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
        e, w = check_file(path)
        errors += e
        warnings += w
    for f in inbound_files():
        text = f.read_text(encoding="utf-8")
        errors += check_inbound(text, rel(f))
        if f.suffix == ".py":
            errors += [f"{rel(f)}: {e}" for e in check_refs(text)]
    warnings += check_history()
    errors += check_spec((ROOT / "SPEC.md").read_text(encoding="utf-8"))
    old_spec = git_text("show", "origin/main:SPEC.md")
    numbers = spec_renumbers(old_spec, (ROOT / "SPEC.md").read_text(encoding="utf-8"))
    warnings += [
        f"SPEC.md 절 번호가 바뀜: {old}절 -> {new}절. SPEC.md {old}절 참조를 확인한다"
        for old, new in numbers.items()
    ]
    if "+++ b/SPEC.md" in diff:
        warnings.append("SPEC.md가 바뀌었다. 이 작업의 승인 요청이나 보고에 바꾼 줄을 함께 적는다")
    for w in warnings:
        print(f"알림: {w}")
    for e in errors:
        print(f"오류: {e}")
    return 1 if errors else 0


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


def heading_renames(diff: str) -> list[tuple[str, str, str]]:
    renames = []
    for chunk in re.split(r"^diff --git ", diff, flags=re.MULTILINE)[1:]:
        m = re.search(r"^\+\+\+ b/(.+)$", chunk, re.MULTILINE)
        if not m:
            continue
        for hunk in re.split(r"^@@.*$", chunk, flags=re.MULTILINE)[1:]:
            lines = [
                x
                for x in hunk.splitlines()
                if x.startswith(("-", "+")) and not x.startswith(("---", "+++"))
            ]
            if len(lines) != 2:
                continue
            old = re.match(r"^-#+\s+(.+)$", lines[0])
            new = re.match(r"^\+#+\s+(.+)$", lines[1])
            if old and new and old.group(1).strip() != new.group(1).strip():
                renames.append((m.group(1), old.group(1).strip(), new.group(1).strip()))
    return renames


def spec_renumbers(old_spec: str, new_spec: str) -> dict[str, str]:
    def numbers(text: str) -> dict[str, str]:
        found = re.finditer(r"^## (\d+)\.\s+(.+)$", text, re.MULTILINE)
        return {m.group(2).strip(): m.group(1) for m in found}

    old, new = numbers(old_spec), numbers(new_spec)
    return {old[t]: new[t] for t in old if t in new and old[t] != new[t]}


def replace_refs(text: str, renames: list[tuple[str, str, str]]) -> str:
    for path, old, new in renames:
        for q in "\"'":
            text = text.replace(f"`{path}` {q}{old}{q} 절", f"`{path}` {q}{new}{q} 절")
    return text


def fix() -> int:
    renames = heading_renames(git_text("diff", "-U0", "origin/main...HEAD", "--", "*.md"))
    changed = []
    for f in sorted(set(scope_files()) | set(inbound_files())):
        text = f.read_bytes().decode("utf-8")
        new = replace_refs(text, renames)
        if new != text:
            f.write_bytes(new.encode("utf-8"))
            changed.append(rel(f))
    for path, old, new in renames:
        print(f'제목: {path} "{old}" -> "{new}"')
    for path in changed:
        print(f"고침: {path}")
    return 0


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook()
    elif "--fix" in sys.argv:
        sys.exit(fix())
    else:
        sys.exit(branch())
