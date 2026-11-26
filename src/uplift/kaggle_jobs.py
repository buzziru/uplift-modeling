import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

USER = "buzziru"
DATASET = "uplift-hillstrom-train"
MAX_BATCH_CPU = 5
ACTIVE = ("pushed", "running")
DONE = ("complete", "error", "unknown")

ENTRY = """import hashlib
import json
import subprocess
from pathlib import Path

SHA = "{sha}"
EXP = "{exp}"
ARGS = "{args}"


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


@dataclass
class Job:
    slug: str
    exp: str
    sha: str
    args: str = ""
    manifest: dict[str, str] = field(default_factory=dict)
    status: str = "queued"
    version: int | None = None
    misses: int = 0
    run_ids: list[str] = field(default_factory=list)


def slug_for(exp: str, part: str | None) -> str:
    base = "uplift-" + "-".join(exp.split("-")[:2]).lower()
    return f"{base}-{part.replace('_', '-')}" if part else base


def parse_version(text: str) -> int | None:
    found = re.search(r"Kernel version (\d+) successfully pushed", text)
    return int(found.group(1)) if found else None


def slot_limited(text: str) -> bool:
    return "Maximum batch CPU session count" in text


def parse_status(text: str) -> str | None:
    found = re.search(r'status "(?:KernelWorkerStatus\.)?(\w+)"', text)
    if not found:
        return None
    raw = found.group(1).upper()
    if raw in ("RUNNING", "QUEUED"):
        return "running"
    if raw == "COMPLETE":
        return "complete"
    return "error"


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
        sha=job.sha, exp=job.exp, args=job.args, user=USER, manifest=repr(job.manifest)
    )
    (folder / "entry.py").write_text(entry, encoding="utf-8")


def load_jobs(path: Path) -> list[Job]:
    if not path.exists():
        return []
    return [Job(**j) for j in json.loads(path.read_text(encoding="utf-8"))]


def save_jobs(path: Path, jobs: list[Job]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(j) for j in jobs], indent=2), encoding="utf-8")


MANIFEST = "manifest.json"
DATA_FILES = ("train.parquet", "folds.parquet")


def file_hashes(folder: Path) -> dict[str, str]:
    return {n: hashlib.sha256((folder / n).read_bytes()).hexdigest() for n in DATA_FILES}


def write_manifest(folder: Path) -> dict[str, str]:
    hashes = file_hashes(folder)
    (folder / MANIFEST).write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return hashes
