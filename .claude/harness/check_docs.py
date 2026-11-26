import csv
import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE = [
    "SPEC.md",
    "docs/history/*",
    "artifacts/*",
    "_workspace/*",
    ".claude/skills/*",
    ".claude/harness/CHANGELOG.md",
    "tests/*.py",
]
CANON = [
    "CLAUDE.md",
    "*/CLAUDE.md",
    ".claude/*",
    "experiments/*",
    "src/*",
    "scripts/*",
    "analyses/*",
]
INCLUDE = [
    ".claude/skills/run-evaluation/*",
    ".claude/skills/kaggle-remote-runner/*",
    ".claude/skills/run-analysis/*",
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
RECORD_REF = re.compile(
    r"docs/(?:" + "|".join(RECORDS) + r")\.md"
    r"(?:#[^\s)`]+|`?(?!에 항목)(?:\s*\"[^\"\n]+\")?[^|\n`]{0,20}?(?<!\d)(?:절(?!차)|항목))"
)
PLAN_REF = re.compile(r"docs/plans/[\w.-]+\.md")
HISTORY_LIMIT = 0.2
TITLE_REF = re.compile(r"`[^`]+\.md` [\"'][^\"'\n]+[\"'] 절")
GLOSSARY_POINTER = re.compile(r"\(`docs/glossary\.md`[,)]")
PENDING_FILE = "PENDING-DECISIONS.md"
SPEC_REF = re.compile(r"SPEC(?:\.md)? (?:\d+(?:\.\d+)?절|[가-힣]+(?: [가-힣]+){0,3} 절)")
POSITION_REF = re.compile(
    r"(?<![가-힣])(?:첫|마지막|앞|위|아래|다음) (?:절|행|문단)"
    r"(?:(?![가-힣])|(?=[은는이가을를의에와과도만로으부까처]))"
)
MERGED_ITEM = re.compile(r"(?:\S {2,}|[.!?] ?)- \S")
CODE_DIRS = ("src/", "scripts/", "experiments/", "analyses/")
PENDING_LINE = "- 정본: 아직 없음"
NO_CANON = "정본 칸: 반영 없음"
CLEFT = re.compile(r"[가-힣]+[한된던운은는] 것은 [^.\n]{0,60}?(?:이다|였다|이었다)\.")
NO_ALTERNATIVE = re.compile(r"^- 기각한 대안: 없음", re.MULTILINE)
CITE_GROUP = re.compile(r"\(([^()]*\d{4}[^()]*)\)")
CITE_PART = re.compile(r"^([A-Za-zÀ-ž][^\s,]*)\D*?(\d{4})(?![\d가-힣])")
CITE_INLINE = re.compile(
    r"([A-Za-zÀ-ž][\w'-]+)(?: et al\.| & [A-Za-zÀ-ž][\w'-]+)? \((\d{4})(?![\d가-힣])"
)
REFERENCE = re.compile(r"^- ([^\s,]+?)[,.] .*?\((\d{4})", re.MULTILINE)
TABLE_REF = re.compile(r"tables/([\w.-]+\.(?:csv|json))")
SUMMARY = re.compile(r"artifacts/[^/]+/summary\.md")
NOT_VALUE = re.compile(
    r"`[^`\n]*`|\(https?://[^)]*\)|\d{4}-\d{2}-\d{2}|\b[A-Z]+-?\d+\b"
    r"|95% (?:신뢰)?구간|검정력 \d+%|[<>≤≥] ?-?[\d.]+|기준 -?[\d.]+|(?<![\d.,])1(?=회|명당)"
)
NUMBER = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.])-?\d+(?:\.\d+)?%?")


def excluded(path: str) -> bool:
    if any(fnmatch(path, p) for p in INCLUDE):
        return False
    return any(fnmatch(path, p) for p in EXCLUDE)


def in_scope(path: str) -> bool:
    return path.endswith(".md") and not excluded(path)


def is_inbound(path: str) -> bool:
    skip = ("docs/", "_workspace/", "tests/")
    return path.endswith((".md", ".py")) and not path.startswith(skip) and path != "SPEC.md"


def tracked(*patterns: str) -> list[str]:
    out = git_text("ls-files", "--", *patterns)
    return [p for p in out.splitlines() if (ROOT / p).is_file()]


def scope_files() -> list[Path]:
    return [ROOT / p for p in tracked("*.md") if in_scope(p)]


def inbound_files() -> list[Path]:
    return [ROOT / p for p in tracked("*.md", "*.py") if is_inbound(p)]


def is_canon(path: str) -> bool:
    return any(fnmatch(path, p) for p in CANON)


def is_record(path: str) -> bool:
    return path in {f"docs/{name}.md" for name in RECORDS}


def record_files() -> list[Path]:
    return [
        ROOT / "docs" / f"{name}.md" for name in RECORDS if (ROOT / "docs" / f"{name}.md").exists()
    ]


def check_inbound(text: str, path: str) -> list[str]:
    errors = [f'기록 문서 인용: {path} "{m.group(0)}"' for m in RECORD_REF.finditer(text)]
    errors += [f'단계 계획 인용: {path} "{m.group(0)}"' for m in PLAN_REF.finditer(text)]
    return errors


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


def check_history() -> list[str]:
    warnings = []
    for f in record_files():
        ratio = history_ratio(f.read_text(encoding="utf-8"))
        if ratio > HISTORY_LIMIT:
            warnings.append(f"바뀐 이력 비율 {ratio:.0%}: {rel(f)}를 docs/history/로 나눈다")
    return warnings


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


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
    errors = [f'절 제목 인용: "{m.group(0)}"' for m in TITLE_REF.finditer(text)]
    errors += [f'용어집 가리키기: "{m.group(0)}"' for m in GLOSSARY_POINTER.finditer(text)]
    errors += [f'시작 명세 가리키기: "{m.group(0)}"' for m in SPEC_REF.finditer(text)]
    return errors


def check_copies(new_text: str, path: str) -> tuple[list[str], list[str]]:
    if is_record(path):
        return [], []
    errors, warnings = [], []
    for f in scope_files():
        if rel(f) == path:
            continue
        olds = sentences(f.read_text(encoding="utf-8"))
        for s in sentences(new_text):
            matches = [o for o in olds if similarity(s, o) >= SIMILAR]
            if not matches:
                continue
            other = matches[0]
            if is_record(rel(f)) and is_canon(path):
                continue
            if is_record(rel(f)):
                errors.append(
                    f'기록 문서 결정의 사본: {path} "{s[:40]}…" ≈ {rel(f)} "{other[:40]}…"'
                )
            else:
                warnings.append(f'사본 의심: {path} "{s[:40]}…" ≈ {rel(f)} "{other[:40]}…"')
    return errors, warnings


@cache
def all_files() -> tuple[str, ...]:
    return tuple(tracked())


def existing_path(phrase: str) -> bool:
    if re.search(r"\s", phrase) or not re.search(r"/|\.\w+$", phrase):
        return False
    pattern = re.sub(r"<[^>]+>", "*", phrase.rstrip("/"))
    return any(
        fnmatch(f, p) for f in all_files() for p in (pattern, pattern + "/*", "*/" + pattern)
    )


def check_removed(old_text: str, new_text: str) -> list[str]:
    phrases = set(re.findall(r"`([^`\n]{10,})`|\"([^\"\n]{10,})\"", old_text))
    removed = {
        p for pair in phrases for p in pair if p and p not in new_text and not existing_path(p)
    }
    warnings = []
    for f in scope_files():
        body = f.read_text(encoding="utf-8")
        warnings += [f'지운 표현이 남음: "{p}" in {rel(f)}' for p in removed if p in body]
    return warnings


def check_style(new_text: str, path: str) -> list[str]:
    warnings = [f'위치 참조: {path} "{m.group(0)}"' for m in POSITION_REF.finditer(new_text)]
    warnings += [f'분열문: {path} "{m.group(0)}"' for m in CLEFT.finditer(new_text)]
    if path.startswith("docs/"):
        warnings += [f"기각한 대안이 없음: {path}" for _ in NO_ALTERNATIVE.finditer(new_text)]
    return warnings


def check_merged(new_text: str, path: str) -> list[str]:
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", new_text, flags=re.DOTALL)
    return [
        f'목록 두 항목이 한 줄에 붙음: {path} "{m.group(0)}"' for m in MERGED_ITEM.finditer(prose)
    ]


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
    checked = new_text
    if path == "docs/glossary.md":
        checked = "\n".join(line.rsplit("|", 2)[0] for line in new_text.splitlines())
    errors = [] if is_record(path) else check_refs(checked)
    if path == PENDING_FILE and new_text.strip():
        errors.append(f"{PENDING_FILE}: 반영 대기 목록은 check_docs.py --pending으로 뽑는다")
    errors += check_merged(new_text, path)
    copy_errors, warnings = check_copies(new_text, path)
    errors += copy_errors
    warnings += check_removed(old_text, new_text)
    warnings += check_style(new_text, path)
    return errors, warnings


def check_file(path: str) -> tuple[list[str], list[str]]:
    target = ROOT / path
    if not path.endswith(".md") or not target.exists():
        return [], []
    text = target.read_text(encoding="utf-8")
    errors = check_citations(text) if path == "docs/THEORY.md" else []
    return errors, check_blank_runs(text, path)


def table_values(folder: Path, name: str = "*") -> list[float]:
    values = []
    for f in sorted((folder / "tables").glob(name)):
        if f.suffix == ".csv":
            with f.open(encoding="utf-8", newline="") as fh:
                cells = [c for row in csv.reader(fh) for c in row]
        elif f.suffix == ".json":
            cells = json_leaves(json.loads(f.read_text(encoding="utf-8")))
        else:
            continue
        for c in cells:
            try:
                values.append(abs(float(str(c).rpartition("=")[2])))
            except (TypeError, ValueError):
                pass
    return values


def json_leaves(data: object) -> list[object]:
    if isinstance(data, dict):
        return [x for v in data.values() for x in json_leaves(v)]
    if isinstance(data, list):
        return [x for v in data for x in json_leaves(v)]
    return [data]


def unmatched_numbers(text: str, values: list[float]) -> list[str]:
    missing = []
    for token in NUMBER.findall(NOT_VALUE.sub(" ", text)):
        if "." not in token:
            continue
        digits = token.rstrip("%").replace(",", "")
        x = abs(float(digits))
        tol = 0.5 * 10 ** -len(digits.partition(".")[2]) + 1e-9
        scales = (1, 100) if token.endswith("%") else (1,)
        if not any(abs(v * s - x) <= tol for v in values for s in scales):
            missing.append(token)
    return missing


def check_summary(path: str) -> list[str]:
    folder = (ROOT / path).parent
    if not (folder / "tables").is_dir():
        return []
    every = table_values(folder)
    missing = []
    for block in re.split(r"\n\s*\n|\n(?=- )", (ROOT / path).read_text(encoding="utf-8")):
        cited = sorted(set(TABLE_REF.findall(block)))
        values = [v for name in cited for v in table_values(folder, name)] if cited else every
        missing += unmatched_numbers(block, values)
    if not missing:
        return []
    return [f"tables/에 없는 수치 {len(missing)}건: {path} ({', '.join(missing)})"]


def summaries() -> int:
    paths = [a for a in sys.argv[2:]] or tracked("artifacts/*/summary.md")
    errors = [e for p in paths for e in check_summary(Path(p).as_posix())]
    for e in errors:
        print(f"오류: {e}")
    return 1 if errors else 0


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
    if is_inbound(path):
        errors += check_inbound(new, path)
        if path.endswith(".py"):
            errors += check_refs(new)
    if file_path in record_files():
        warnings += check_history()
    if SUMMARY.fullmatch(path):
        errors += check_summary(path)
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
        ["git", "-c", "core.quotepath=false", "diff", "-U0", "origin/main...HEAD", "--", "*.md"],
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
        if not in_scope(path):
            continue
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
        errors += check_inbound(f.read_text(encoding="utf-8"), rel(f))
    py_diff = git_text("diff", "-U0", "origin/main...HEAD", "--", "*.py")
    for chunk in re.split(r"^diff --git ", py_diff, flags=re.MULTILINE)[1:]:
        m = re.search(r"^\+\+\+ b/(.+)$", chunk, re.MULTILINE)
        if m and is_inbound(m.group(1)):
            added = "\n".join(
                line[1:]
                for line in chunk.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            errors += [f"{m.group(1)}: {e}" for e in check_refs(added)]
    warnings += check_history()
    for p in git_text(
        "diff", "--name-only", "--diff-filter=d", "origin/main...HEAD", "--", "artifacts/*/summary.md"
    ).split():
        errors += check_summary(p)
    if "+++ b/SPEC.md" in diff:
        warnings.append("SPEC.md는 시작 명세로 고정한 문서다. 바꾼 이유를 보고에 적는다")
    errors += check_canon(
        git_text("diff", "--name-only", "--diff-filter=d", "origin/main...HEAD").splitlines(),
        git_text("diff", "-U0", "origin/main...HEAD", "--", *map(rel, record_files())),
        git_text("log", "--format=%B", "origin/main..HEAD"),
    )
    for e in errors:
        print(f"오류: {e}")
    for w in warnings:
        print(f"알림: {w}")
    return 1 if errors else 0


def check_canon(changed: list[str], record_diff: str, messages: str) -> list[str]:
    if not any(p.startswith(CODE_DIRS) and not p.endswith(".md") for p in changed):
        return []
    if any(line.startswith("-" + PENDING_LINE) for line in record_diff.splitlines()):
        return []
    if any(line.strip().startswith(NO_CANON) for line in messages.splitlines()):
        return []
    items = pending_items()
    if not items:
        return []
    head = (
        "코드를 바꿨는데 기록 문서의 정본 칸을 하나도 고치지 않았다. 아래 항목 가운데 "
        f'반영한 것의 정본 칸을 고치고, 반영한 것이 없으면 커밋 메시지에 "{NO_CANON}" 줄을 둔다'
    )
    return [head] + [f"반영 대기: {item}" for item in items]


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


def pending_items() -> list[str]:
    items = []
    for f in record_files():
        title = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                title = line[3:].strip()
            elif line.startswith(PENDING_LINE):
                items.append(
                    f"{rel(f)} | {title} | {line.removeprefix(PENDING_LINE).strip(' .')}"
                )
    return items


def pending() -> int:
    for item in pending_items():
        print(item)
    return 0


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook()
    elif "--pending" in sys.argv:
        sys.exit(pending())
    elif "--summary" in sys.argv:
        sys.exit(summaries())
    else:
        sys.exit(branch())
