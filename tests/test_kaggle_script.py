import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from uplift import kaggle_jobs
from uplift.kaggle_jobs import MANIFEST, MAX_BATCH_CPU, Job, Status, load_jobs, save_jobs, slug_for

SPEC = importlib.util.spec_from_file_location(
    "kaggle_script", Path(__file__).resolve().parents[1] / "scripts" / "kaggle.py"
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("scripts/kaggle.py를 불러오지 못했다")
script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(script)

EXP = "EXP-002-x"
SHA = "abc123"
HASHES = {"train.parquet": "h1", "folds.parquet": "h2"}
PUSHED = "Kernel version 7 successfully pushed.  Please check"
SLOT_LIMITED = "Kernel push error: Maximum batch CPU session count of 5 reached."
COMPLETE = 'uplift-exp-002 has status "KernelWorkerStatus.COMPLETE"'


def job(status: Status, slug: str = "uplift-exp-002", version: int | None = 1) -> Job:
    return Job(slug=slug, exp=EXP, sha=SHA, status=status, version=version)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "DATA", tmp_path / "data")
    monkeypatch.setattr(script, "STATE", tmp_path / "data" / "kaggle" / "state.json")
    return tmp_path / "data"


def cli(
    monkeypatch, replies: dict[str, str], code: int = 0, remote: dict[str, str] | None = None
) -> None:
    def fake_run(cmd, **kwargs):
        words = cmd[cmd.index("kaggle") + 1 :]
        if words[:2] == ["datasets", "download"] and remote is not None:
            folder = Path(words[words.index("-p") + 1])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / MANIFEST).write_text(json.dumps(remote), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, code, stdout=replies.get(words[1], ""), stderr="")

    monkeypatch.setattr(kaggle_jobs.subprocess, "run", fake_run)


def statuses(jobs: list[Job]) -> list[str]:
    return [j.status for j in jobs]


def test_watch_fails_when_status_stays_unreadable(data, monkeypatch):
    save_jobs(script.STATE, [job("running")])
    cli(monkeypatch, {"status": "no status line"})
    with pytest.raises(SystemExit) as exited:
        script.watch(0)
    assert exited.value.code != 0


def test_watch_fails_when_any_job_ends_unknown(data, monkeypatch):
    save_jobs(script.STATE, [job("complete", slug="done"), job("running")])
    cli(monkeypatch, {"status": "no status line"})
    with pytest.raises(SystemExit) as exited:
        script.watch(0)
    assert exited.value.code != 0


def test_watch_raises_when_status_command_fails(data, monkeypatch):
    save_jobs(script.STATE, [job("running")])
    cli(monkeypatch, {"status": "401 Unauthorized"}, code=1)
    with pytest.raises(RuntimeError, match="exit 1"):
        script.watch(0)


def test_watch_ends_normally_when_job_completes(data, monkeypatch):
    save_jobs(script.STATE, [job("running")])
    cli(monkeypatch, {"status": COMPLETE})
    script.watch(0)
    assert statuses(load_jobs(script.STATE)) == ["complete"]


@pytest.mark.parametrize(
    "command", [lambda: script.watch(0), lambda: script.pull(Path("unused.duckdb"))]
)
def test_command_fails_without_state_file(data, command):
    with pytest.raises(FileNotFoundError):
        command()


def test_fill_marks_pushed_job_with_version(data, monkeypatch):
    jobs = [job("queued", version=None)]
    cli(monkeypatch, {"push": PUSHED})
    script.fill(jobs)
    assert [(j.status, j.version) for j in jobs] == [("pushed", 7)]


def test_fill_stops_and_keeps_queue_when_slots_are_taken(data, monkeypatch):
    jobs = [job("queued", slug="a"), job("queued", slug="b")]
    cli(monkeypatch, {"push": SLOT_LIMITED})
    script.fill(jobs)
    assert statuses(jobs) == ["queued", "queued"]


def test_fill_raises_when_version_is_unreadable(data, monkeypatch):
    cli(monkeypatch, {"push": "unexpected output"})
    with pytest.raises(RuntimeError, match="uplift-exp-002"):
        script.fill([job("queued")])


def test_fill_pushes_only_into_free_slots(data, monkeypatch):
    running = [job("running", slug=f"r{i}") for i in range(MAX_BATCH_CPU - 1)]
    queued = [job("queued", slug="a"), job("queued", slug="b")]
    cli(monkeypatch, {"push": PUSHED})
    script.fill(running + queued)
    assert statuses(queued) == ["pushed", "queued"]


@pytest.fixture
def local_manifest(data):
    folder = data / "kaggle" / "dataset"
    folder.mkdir(parents=True)
    (folder / MANIFEST).write_text(json.dumps(HASHES), encoding="utf-8")


def test_check_dataset_returns_matching_manifest(local_manifest, monkeypatch):
    cli(monkeypatch, {"status": "ready"}, remote=HASHES)
    assert script.check_dataset() == HASHES


def test_check_dataset_rejects_dataset_not_ready(local_manifest, monkeypatch):
    cli(monkeypatch, {"status": "pending"}, remote=HASHES)
    with pytest.raises(RuntimeError, match="pending"):
        script.check_dataset()


def test_check_dataset_requires_local_manifest(data, monkeypatch):
    cli(monkeypatch, {"status": "ready"}, remote=HASHES)
    with pytest.raises(RuntimeError):
        script.check_dataset()


def test_check_dataset_rejects_remote_manifest_mismatch(local_manifest, monkeypatch):
    cli(monkeypatch, {"status": "ready"}, remote=HASHES | {"train.parquet": "other"})
    with pytest.raises(RuntimeError):
        script.check_dataset()


@pytest.fixture
def git(monkeypatch):
    replies = {"branch": "  origin/main", "show": "## 질문\n\n## 설계\n"}
    monkeypatch.setattr(script.runs, "require_clean", lambda paths: None)
    monkeypatch.setattr(script.runs, "git_commit", lambda: SHA)
    monkeypatch.setattr(script, "git", lambda *args: replies[args[0]])
    return replies


def test_check_pushable_returns_commit(git):
    assert script.check_pushable(EXP) == SHA


def test_check_pushable_requires_commit_on_origin(git):
    git["branch"] = ""
    with pytest.raises(RuntimeError, match=SHA):
        script.check_pushable(EXP)


def test_check_pushable_requires_question_and_design(git):
    git["show"] = "## 질문\n"
    with pytest.raises(RuntimeError):
        script.check_pushable(EXP)


def test_push_requires_run_script(data):
    with pytest.raises(ValueError, match=EXP):
        script.push(EXP, [], "")


def test_push_adds_job_per_part(data, monkeypatch):
    (data.parent / "experiments" / EXP).mkdir(parents=True)
    (data.parent / "experiments" / EXP / "run.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(script, "check_pushable", lambda exp: SHA)
    monkeypatch.setattr(script, "check_dataset", lambda: HASHES)
    cli(monkeypatch, {"push": PUSHED})
    script.push(EXP, ["s_learner", "t_learner"], "--n 1")
    got = [(j.slug, j.args.split()) for j in load_jobs(script.STATE)]
    assert got == [
        (slug_for(EXP, part), ["--part", part, "--n", "1"]) for part in ["s_learner", "t_learner"]
    ]


def test_pull_records_run_ids_of_completed_jobs_only(data, monkeypatch):
    save_jobs(script.STATE, [job("complete", slug="done"), job("running", slug="busy")])
    cli(monkeypatch, {})
    monkeypatch.setattr(script.runs, "merge_records", lambda con, path: ["r1"])
    script.pull(data / "uplift.duckdb")
    assert {j.slug: j.run_ids for j in load_jobs(script.STATE)} == {"done": ["r1"], "busy": []}
