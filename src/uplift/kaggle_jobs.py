import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

USER = "buzziru"
DATASET = "uplift-hillstrom-train"
MAX_BATCH_CPU = 5
Status = Literal["queued", "pushed", "running", "complete", "error", "unknown"]
ACTIVE: tuple[Status, ...] = ("pushed", "running")
DONE: tuple[Status, ...] = ("complete", "error", "unknown")
MAX_MISSES = 3
KAGGLE = [
    "doppler",
    "run",
    "-p",
    "uplift-modeling",
    "-c",
    "dev",
    "--",
    "uvx",
    "--with",
    "six",
    "kaggle",
]
KERNEL_STATUS: dict[str, Status] = {
    "NEW_SCRIPT": "running",
    "QUEUED": "running",
    "RUNNING": "running",
    "COMPLETE": "complete",
    "ERROR": "error",
    "CANCEL_REQUESTED": "error",
    "CANCEL_ACKNOWLEDGED": "error",
}

ENTRY = """import hashlib
import json
import subprocess
from pathlib import Path

SHA = {sha}
EXP = {exp}
ARGS = {args}


def sh(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


EXPECTED = {manifest}
found = list(Path("/kaggle/input").rglob("manifest.json"))
if len(found) != 1:
    raise SystemExit(f"dataset manifest.json을 하나 찾지 못했다: {{found}}")
DATA = found[0].parent
got = {{n: hashlib.sha256((DATA / n).read_bytes()).hexdigest() for n in EXPECTED}}
if got != EXPECTED:
    raise SystemExit(f"dataset 버전이 push 때와 다르다: {{got}} != {{EXPECTED}}")
print("data", DATA, "matches manifest")
sh("pip install -q uv")
sh(f"git clone -q https://github.com/{user}/uplift-modeling.git /tmp/repo && git -C /tmp/repo checkout -q {{SHA}}")
sh(
    f"cd /tmp/repo && uv run --frozen python experiments/{{EXP}}/run.py compute"
    f" --data {{DATA}} --db /kaggle/working/run.duckdb {{ARGS}}"
)
"""


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    exp: str
    sha: str
    args: str = ""
    manifest: dict[str, str] = Field(default_factory=dict)
    status: Status = "queued"
    version: int | None = None
    misses: int = 0
    run_ids: list[str] = Field(default_factory=list)


JOBS = TypeAdapter(list[Job])
HASHES = TypeAdapter(dict[str, str])


def kaggle(*args: str, check: bool = True) -> str:
    done = subprocess.run([*KAGGLE, *args], check=False, capture_output=True, text=True)
    out = done.stdout + done.stderr
    if check and done.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} 실패(exit {done.returncode}): {out}")
    return out


def slug_for(exp: str, part: str | None) -> str:
    base = "uplift-" + "-".join(exp.split("-")[:2]).lower()
    return f"{base}-{part.replace('_', '-')}" if part else base


def parse_version(text: str) -> int | None:
    found = re.search(r"Kernel version (\d+) successfully pushed", text)
    return int(found.group(1)) if found else None


def slot_limited(text: str) -> bool:
    return "Maximum batch CPU session count" in text


def parse_status(text: str) -> Status | None:
    found = re.search(r'status "(?:KernelWorkerStatus\.)?(\w+)"', text)
    if not found:
        return None
    raw = found.group(1).upper()
    if raw not in KERNEL_STATUS:
        raise ValueError(f"모르는 kernel 상태: {raw}")
    return KERNEL_STATUS[raw]


def update_status(job: Job, parsed: Status | None) -> None:
    if parsed is None:
        job.misses += 1
        if job.misses >= MAX_MISSES:
            job.status = "unknown"
        return
    job.misses = 0
    job.status = parsed


def to_pull(jobs: list[Job]) -> list[Job]:
    return [
        j
        for j in jobs
        if j.status == "complete" and not j.run_ids and "--smoke" not in j.args.split()
    ]


def free_slots(jobs: list[Job], limit: int = MAX_BATCH_CPU) -> int:
    return max(0, limit - sum(j.status in ACTIVE for j in jobs))


def write_kernel(job: Job, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": f"{USER}/{job.slug}",
        "title": job.slug,
        "code_file": "entry.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "false",
        "enable_internet": "true",
        "dataset_sources": [f"{USER}/{DATASET}"],
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    entry = ENTRY.format(
        sha=repr(job.sha),
        exp=repr(job.exp),
        args=repr(job.args),
        user=USER,
        manifest=repr(job.manifest),
    )
    (folder / "entry.py").write_text(entry, encoding="utf-8")


def load_jobs(path: Path) -> list[Job]:
    return JOBS.validate_json(path.read_text(encoding="utf-8"))


def save_jobs(path: Path, jobs: list[Job]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(JOBS.dump_json(jobs, indent=2).decode(), encoding="utf-8")


MANIFEST = "manifest.json"
DATA_FILES = ("train.parquet", "folds.parquet")


def file_hashes(folder: Path) -> dict[str, str]:
    return {n: hashlib.sha256((folder / n).read_bytes()).hexdigest() for n in DATA_FILES}


def write_manifest(folder: Path) -> dict[str, str]:
    hashes = file_hashes(folder)
    (folder / MANIFEST).write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return hashes


def read_manifest(path: Path) -> dict[str, str]:
    hashes = HASHES.validate_json(path.read_text(encoding="utf-8"))
    if set(hashes) != set(DATA_FILES):
        raise ValueError(f"{path}의 파일 목록이 {DATA_FILES}와 다르다: {sorted(hashes)}")
    return hashes
