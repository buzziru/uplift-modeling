import json
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / ".claude" / "harness" / "config.json"


def run(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        shlex.split(command),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main(config: Path = CONFIG) -> int:
    commands: list[str] = json.loads(config.read_text(encoding="utf-8"))["check"]
    with ThreadPoolExecutor(len(commands)) as pool:
        results = list(pool.map(run, commands))
    failed = [(c, r) for c, r in zip(commands, results, strict=True) if r.returncode != 0]
    for command, result in failed:
        print(f"$ {command} (exit {result.returncode})")
        print((result.stdout + result.stderr).rstrip())
    print(f"{len(commands) - len(failed)}/{len(commands)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
