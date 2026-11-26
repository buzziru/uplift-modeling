import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import duckdb

from uplift import runs
from uplift.kaggle_jobs import (
    ACTIVE,
    DATASET,
    DONE,
    MANIFEST,
    USER,
    Job,
    free_slots,
    kaggle,
    load_jobs,
    parse_status,
    parse_version,
    read_manifest,
    save_jobs,
    slot_limited,
    slug_for,
    to_pull,
    update_status,
    write_kernel,
    write_manifest,
)
from uplift.train_data import from_duckdb, to_parquet

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("UPLIFT_DATA", ROOT / "data"))
STATE = DATA / "kaggle" / "state.json"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def dataset(version_message: str | None) -> None:
    out = DATA / "kaggle" / "dataset"
    with duckdb.connect(str(DATA / "uplift.duckdb"), read_only=True) as con:
        data = from_duckdb(con)
    to_parquet(data, out)
    write_manifest(out)
    meta = {"title": DATASET, "id": f"{USER}/{DATASET}", "licenses": [{"name": "unknown"}]}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print({"train_rows": len(data.frame), "fold_rows": len(data.folds)})
    if version_message:
        print(kaggle("datasets", "version", "-p", str(out), "-t", "-q", "-m", version_message))
    else:
        print(kaggle("datasets", "create", "-p", str(out), "-t", "-q"))


def check_pushable(exp: str) -> str:
    runs.require_clean([str(ROOT / "src"), str(ROOT / "experiments" / exp)])
    sha = runs.git_commit()
    if not git("branch", "-r", "--contains", sha):
        raise RuntimeError(f"{sha}가 origin에 없다. 먼저 push한다")
    design = git("show", f"{sha}:experiments/{exp}/experiment.md")
    if "## 질문" not in design or "## 설계" not in design:
        raise RuntimeError("push한 커밋의 experiment.md에 질문·설계 절이 없다")
    return sha


def fill(jobs: list[Job]) -> None:
    for job in [j for j in jobs if j.status == "queued"][: free_slots(jobs)]:
        folder = DATA / "kaggle" / job.slug
        write_kernel(job, folder)
        out = kaggle("kernels", "push", "-p", str(folder), check=False)
        if slot_limited(out):
            break
        version = parse_version(out)
        if version is None:
            raise RuntimeError(f"{job.slug} push 실패: {out}")
        job.status, job.version = "pushed", version
        print(time.strftime("%H:%M:%S"), job.slug, f"v{version} pushed", flush=True)


def check_dataset() -> dict[str, str]:
    status = kaggle("datasets", "status", f"{USER}/{DATASET}").strip()
    if status != "ready":
        raise RuntimeError(f"dataset이 ready가 아니다: {status}")
    local = DATA / "kaggle" / "dataset" / MANIFEST
    if not local.exists():
        raise RuntimeError("로컬 dataset manifest가 없다. scripts/kaggle.py dataset부터")
    remote_dir = DATA / "kaggle" / "dataset-remote"
    kaggle(
        "datasets",
        "download",
        f"{USER}/{DATASET}",
        "-f",
        MANIFEST,
        "-p",
        str(remote_dir),
        "--force",
    )
    expected = read_manifest(local)
    if read_manifest(remote_dir / MANIFEST) != expected:
        raise RuntimeError("Kaggle dataset 최신 버전이 로컬 dataset과 다르다")
    return expected


def push(exp: str, parts: list[str], args: str) -> None:
    if not (ROOT / "experiments" / exp / "run.py").exists():
        raise ValueError(f"experiments/{exp}/run.py가 없다")
    sha = check_pushable(exp)
    manifest = check_dataset()
    jobs = load_jobs(STATE)
    for part in parts or [None]:
        extra = f"--part {part} {args}".strip() if part else args
        jobs.append(Job(slug=slug_for(exp, part), exp=exp, sha=sha, args=extra, manifest=manifest))
    fill(jobs)
    save_jobs(STATE, jobs)


def watch(interval: int) -> None:
    jobs = load_jobs(STATE)
    while any(j.status not in DONE for j in jobs):
        for job in [j for j in jobs if j.status in ACTIVE]:
            before = job.status
            update_status(
                job, parse_status(kaggle("kernels", "status", f"{USER}/{job.slug}", check=False))
            )
            if job.status != before:
                print(time.strftime("%H:%M:%S"), job.slug, job.status, flush=True)
        fill(jobs)
        save_jobs(STATE, jobs)
        if any(j.status not in DONE for j in jobs):
            time.sleep(interval)
    for job in jobs:
        print(job.slug, job.status, f"v{job.version}")


def pull(db: Path) -> None:
    jobs = load_jobs(STATE)
    for job in to_pull(jobs):
        out = DATA / "kaggle" / job.slug / "output" / f"v{job.version}"
        print(kaggle("kernels", "output", f"{USER}/{job.slug}", "-p", str(out)))
        with duckdb.connect(str(db)) as con:
            job.run_ids = runs.merge_records(con, out / "run.duckdb")
        print(job.slug, "run_ids", job.run_ids)
    save_jobs(STATE, jobs)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("dataset")
    p.add_argument("--version-message")
    p.set_defaults(func=lambda a: dataset(a.version_message))
    p = sub.add_parser("push")
    p.add_argument("exp")
    p.add_argument("--part", action="append", default=[])
    p.add_argument("--args", default="")
    p.set_defaults(func=lambda a: push(a.exp, a.part, a.args))
    p = sub.add_parser("watch")
    p.add_argument("--interval", type=int, default=60)
    p.set_defaults(func=lambda a: watch(a.interval))
    p = sub.add_parser("pull")
    p.add_argument("--db", type=Path, default=DATA / "uplift.duckdb")
    p.set_defaults(func=lambda a: pull(a.db))
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
