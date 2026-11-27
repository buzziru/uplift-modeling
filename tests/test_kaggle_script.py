import importlib.util
import subprocess
from pathlib import Path

import pytest

from uplift import kaggle_jobs
from uplift.kaggle_jobs import Job, load_jobs, save_jobs

SPEC = importlib.util.spec_from_file_location(
    "kaggle_script", Path(__file__).resolve().parents[1] / "scripts" / "kaggle.py"
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("scripts/kaggle.py를 불러오지 못했다")
script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(script)

RUNNING = Job(
    slug="uplift-exp-002",
    exp="EXP-002-x",
    sha="abc123",
    args="",
    manifest={"train.parquet": "h1"},
    status="running",
    version=1,
)


@pytest.fixture
def state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    save_jobs(path, [RUNNING])
    monkeypatch.setattr(script, "STATE", path)
    return path


def cli(monkeypatch, code: int, stdout: str) -> None:
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")

    monkeypatch.setattr(kaggle_jobs.subprocess, "run", fake_run)


def test_watch_fails_when_status_stays_unreadable(state, monkeypatch):
    cli(monkeypatch, 0, "no status line")
    with pytest.raises(SystemExit) as exited:
        script.watch(0)
    assert exited.value.code != 0


def test_watch_raises_when_status_command_fails(state, monkeypatch):
    cli(monkeypatch, 1, "401 Unauthorized")
    with pytest.raises(RuntimeError, match="exit 1"):
        script.watch(0)


def test_watch_ends_normally_when_job_completes(state, monkeypatch):
    cli(monkeypatch, 0, 'uplift-exp-002 has status "KernelWorkerStatus.COMPLETE"')
    script.watch(0)
    assert load_jobs(state)[0].status == "complete"
