import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import duckdb

from uplift import runs
from uplift.kaggle_jobs import (
    DATASET,
    DONE,
    USER,
    Job,
    free_slots,
    load_jobs,
    parse_status,
    parse_version,
    save_jobs,
    slot_limited,
    slug_for,
    write_kernel,
)
from uplift.train_data import from_duckdb, to_parquet

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("UPLIFT_DATA", ROOT / "data"))
STATE = DATA / "kaggle" / "state.json"
K = ["doppler", "run", "-p", "uplift-modeling", "-c", "dev", "--", "uvx", "--with", "six", "kaggle"]


def kaggle(*args: str) -> str:
    done = subprocess.run([*K, *args], check=False, capture_output=True, text=True)
    return done.stdout + done.stderr


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def dataset(version_message: str | None) -> None:
    out = DATA / "kaggle" / "dataset"
    with duckdb.connect(str(DATA / "uplift.duckdb"), read_only=True) as con:
        data = from_duckdb(con)
    if not set(data.folds["customer_id"]) <= set(data.frame["customer_id"]):
        raise RuntimeError("folds에 학습 세트 밖 고객이 있다")
    to_parquet(data, out)
    meta = {"title": DATASET, "id": f"{USER}/{DATASET}", "licenses": [{"name": "unknown"}]}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print({"train_rows": len(data.frame), "fold_rows": len(data.folds)})
    if version_message:
        print(kaggle("datasets", "version", "-p", str(out), "-t", "-q", "-m", version_message))
    else:
        print(kaggle("datasets", "create", "-p", str(out), "-t", "-q"))


def check_pushable(exp: str) -> str:
    if git("status", "--porcelain", "--", "src", f"experiments/{exp}"):
        raise RuntimeError("커밋하지 않은 변경이 있다")
    sha = git("rev-parse", "HEAD")
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
        out = kaggle("kernels", "push", "-p", str(folder))
        if slot_limited(out):
            break
        version = parse_version(out)
        if version is None:
            raise RuntimeError(f"{job.slug} push 실패: {out}")
        job.status, job.version = "pushed", version
        print(time.strftime("%H:%M:%S"), job.slug, f"v{version} pushed", flush=True)


def push(exp: str, parts: list[str], args: str) -> None:
    sha = check_pushable(exp)
    jobs = load_jobs(STATE)
    for part in parts or [None]:
        extra = f"--part {part} {args}".strip() if part else args
        jobs.append(Job(slug=slug_for(exp, part), exp=exp, sha=sha, args=extra))
    fill(jobs)
    save_jobs(STATE, jobs)


def watch(interval: int) -> None:
    jobs = load_jobs(STATE)
    while any(j.status not in DONE for j in jobs):
        for job in [j for j in jobs if j.status in ("pushed", "running")]:
            status = parse_status(kaggle("kernels", "status", f"{USER}/{job.slug}"))
            if status is None:
                job.misses += 1
                status = "unknown" if job.misses >= 3 else job.status
            if status != job.status:
                job.status = status
                print(time.strftime("%H:%M:%S"), job.slug, status, flush=True)
        fill(jobs)
        save_jobs(STATE, jobs)
        if any(j.status not in DONE for j in jobs):
            time.sleep(interval)
    for job in jobs:
        print(job.slug, job.status, f"v{job.version}")


def pull(db: Path) -> None:
    jobs = load_jobs(STATE)
    for job in [j for j in jobs if j.status == "complete" and not j.run_ids]:
        out = DATA / "kaggle" / job.slug / "output" / f"v{job.version}"
        print(kaggle("kernels", "output", f"{USER}/{job.slug}", "-p", str(out)))
        with duckdb.connect(str(db)) as con:
            job.run_ids = runs.merge_records(con, out / "run.duckdb")
        print(job.slug, "run_ids", job.run_ids)
    save_jobs(STATE, jobs)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dataset").add_argument("--version-message")
    p = sub.add_parser("push")
    p.add_argument("exp")
    p.add_argument("--part", action="append", default=[])
    p.add_argument("--args", default="")
    sub.add_parser("watch").add_argument("--interval", type=int, default=60)
    sub.add_parser("pull").add_argument("--db", type=Path, default=DATA / "uplift.duckdb")
    args = parser.parse_args()
    if args.command == "dataset":
        dataset(args.version_message)
    elif args.command == "push":
        push(args.exp, args.part, args.args)
    elif args.command == "watch":
        watch(args.interval)
    else:
        pull(args.db)


if __name__ == "__main__":
    main()
