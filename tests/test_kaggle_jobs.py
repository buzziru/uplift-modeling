import subprocess

import pydantic
import pytest

from uplift import kaggle_jobs
from uplift.kaggle_jobs import (
    Job,
    Status,
    free_slots,
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


def test_slug_uses_experiment_id_and_part():
    assert slug_for("EXP-002-method-compare", None) == "uplift-exp-002"
    assert slug_for("EXP-002-method-compare", "s_learner") == "uplift-exp-002-s-learner"


@pytest.mark.parametrize(
    ("text", "version"),
    [
        ("Kernel version 3 successfully pushed.  Please check", 3),
        ("Kernel push error: Maximum batch CPU session count of 5 reached.", None),
    ],
)
def test_parse_version(text, version):
    assert parse_version(text) == version


def test_slot_limited_reads_batch_session_error():
    assert slot_limited("Kernel push error: Maximum batch CPU session count of 5 reached.")


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        ("QUEUED", "running"),
        ("RUNNING", "running"),
        ("COMPLETE", "complete"),
        ("ERROR", "error"),
        ("CANCEL_ACKNOWLEDGED", "error"),
    ],
)
def test_parse_status_maps_kernel_status(raw, status):
    assert parse_status(f'buzziru/x has status "KernelWorkerStatus.{raw}"') == status


def test_parse_status_none_when_output_has_no_status():
    assert parse_status("404 Not Found") is None


def test_parse_status_rejects_unknown_kernel_status():
    with pytest.raises(ValueError, match="NEW_STATE"):
        parse_status('buzziru/x has status "KernelWorkerStatus.NEW_STATE"')


def test_update_status_counts_misses_until_unknown_and_resets_on_success():
    job = Job(slug="a", exp="E", sha="s", status="running")
    update_status(job, None)
    update_status(job, None)
    update_status(job, "running")
    update_status(job, None)
    update_status(job, None)
    assert (job.status, job.misses) == ("running", 2)
    update_status(job, None)
    assert job.status == "unknown"


def test_kaggle_raises_on_nonzero_exit_unless_unchecked(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="out", stderr="err")

    monkeypatch.setattr(kaggle_jobs.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="exit 1"):
        kaggle_jobs.kaggle("kernels", "output")
    assert kaggle_jobs.kaggle("kernels", "status", check=False) == "outerr"


def test_load_jobs_rejects_unknown_status(tmp_path):
    (tmp_path / "state.json").write_text(
        '[{"slug": "a", "exp": "E", "sha": "s", "status": "done"}]', encoding="utf-8"
    )
    with pytest.raises(pydantic.ValidationError):
        load_jobs(tmp_path / "state.json")


def test_free_slots_counts_only_active_jobs():
    statuses: list[Status] = ["pushed", "running", "complete", "queued", "error"]
    jobs = [Job(slug="a", exp="E", sha="s", status=s) for s in statuses]
    assert free_slots(jobs) == 3
    assert free_slots(jobs, limit=1) == 0


def test_to_pull_skips_smoke_pulled_and_unfinished_jobs():
    jobs = [
        Job(slug="full", exp="E", sha="s", args="--part s_learner", status="complete"),
        Job(slug="smoke", exp="E", sha="s", args="--smoke", status="complete"),
        Job(slug="pulled", exp="E", sha="s", status="complete", run_ids=["r1"]),
        Job(slug="running", exp="E", sha="s", status="running"),
        Job(slug="failed", exp="E", sha="s", status="error"),
    ]
    assert [j.slug for j in to_pull(jobs)] == ["full"]


def test_state_round_trip_and_kernel_files(tmp_path):
    jobs = [
        Job(
            slug="uplift-exp-002-s-learner",
            exp="EXP-002-x",
            sha="abc123",
            args='--part s_learner --note "x"',
            manifest={"train.parquet": "h1"},
        )
    ]
    save_jobs(tmp_path / "state.json", jobs)
    assert load_jobs(tmp_path / "state.json") == jobs
    write_kernel(jobs[0], tmp_path / "k")
    entry = (tmp_path / "k" / "entry.py").read_text(encoding="utf-8")
    assert 'SHA = "abc123"' in entry and 'ARGS = "--part s_learner --note \\"x\\""' in entry
    assert "EXPECTED = {'train.parquet': 'h1'}" in entry
    compile(entry, "entry.py", "exec")
    meta = (tmp_path / "k" / "kernel-metadata.json").read_text(encoding="utf-8")
    assert '"is_private": "true"' in meta


def test_manifest_hashes_both_data_files(tmp_path):
    (tmp_path / "train.parquet").write_bytes(b"a")
    (tmp_path / "folds.parquet").write_bytes(b"b")
    hashes = write_manifest(tmp_path)
    assert set(hashes) == {"train.parquet", "folds.parquet"}
    assert (tmp_path / "manifest.json").exists()


def test_read_manifest_requires_both_data_files(tmp_path):
    (tmp_path / "manifest.json").write_text('{"train.parquet": "h1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="folds.parquet"):
        read_manifest(tmp_path / "manifest.json")
