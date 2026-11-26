import subprocess

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


@pytest.mark.parametrize(
    ("part", "slug"),
    [(None, "uplift-exp-002"), ("s_learner", "uplift-exp-002-s-learner")],
    ids=["no_part", "with_part"],
)
def test_slug_for_formats(part, slug):
    assert slug_for("EXP-002-method-compare", part) == slug


@pytest.mark.parametrize(
    ("text", "version"),
    [
        ("Kernel version 3 successfully pushed.  Please check", 3),
        ("Kernel push error: Maximum batch CPU session count of 5 reached.", None),
    ],
)
def test_parse_version(text, version):
    assert parse_version(text) == version


def test_slot_limited_batch_session_error():
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
def test_parse_status_maps(raw, status):
    assert parse_status(f'buzziru/x has status "KernelWorkerStatus.{raw}"') == status


def test_parse_status_missing_is_none():
    assert parse_status("404 Not Found") is None


def test_parse_status_rejects_unknown():
    with pytest.raises(ValueError, match="NEW_STATE"):
        parse_status('buzziru/x has status "KernelWorkerStatus.NEW_STATE"')


def test_update_status_unknown_after_max_misses():
    job = Job(slug="a", exp="E", sha="s", status="running")
    for _ in range(3):
        update_status(job, None)
    assert job.status == "unknown"


def test_update_status_success_resets_misses():
    job = Job(slug="a", exp="E", sha="s", status="running", misses=2)
    update_status(job, "complete")
    assert (job.status, job.misses) == ("complete", 0)


@pytest.fixture
def failing_cli(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="out", stderr="err")

    monkeypatch.setattr(kaggle_jobs.subprocess, "run", fake_run)


def test_kaggle_raises_on_nonzero_exit(failing_cli):
    with pytest.raises(RuntimeError, match="exit 1"):
        kaggle_jobs.kaggle("kernels", "output")


def test_kaggle_unchecked_returns_output(failing_cli):
    assert kaggle_jobs.kaggle("kernels", "status", check=False) == "outerr"


@pytest.mark.parametrize(("limit", "free"), [(5, 3), (1, 0)])
def test_free_slots_counts_active(limit, free):
    statuses: list[Status] = ["pushed", "running", "complete", "queued", "error"]
    jobs = [Job(slug="a", exp="E", sha="s", status=s) for s in statuses]
    assert free_slots(jobs, limit=limit) == free


@pytest.mark.parametrize(
    ("job", "pulled"),
    [
        (Job(slug="j", exp="E", sha="s", args="--part s_learner", status="complete"), True),
        (Job(slug="j", exp="E", sha="s", args="--smoke", status="complete"), False),
        (Job(slug="j", exp="E", sha="s", status="complete", run_ids=["r1"]), False),
        (Job(slug="j", exp="E", sha="s", status="running"), False),
        (Job(slug="j", exp="E", sha="s", status="error"), False),
    ],
    ids=["full", "smoke", "pulled", "running", "failed"],
)
def test_to_pull_selects_job(job, pulled):
    assert (to_pull([job]) == [job]) is pulled


JOB = Job(
    slug="uplift-exp-002-s-learner",
    exp="EXP-002-x",
    sha="abc123",
    args='--part s_learner --note "x"',
    manifest={"train.parquet": "h1"},
)


def test_jobs_state_round_trip(tmp_path):
    save_jobs(tmp_path / "state.json", [JOB])
    assert load_jobs(tmp_path / "state.json") == [JOB]


@pytest.fixture
def kernel(tmp_path):
    write_kernel(JOB, tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "line",
    [
        'SHA = "abc123"',
        'ARGS = "--part s_learner --note \\"x\\""',
        "EXPECTED = {'train.parquet': 'h1'}",
    ],
    ids=["sha", "args", "manifest"],
)
def test_write_kernel_embeds_job(kernel, line):
    assert line in (kernel / "entry.py").read_text(encoding="utf-8")


def test_write_kernel_entry_compiles(kernel):
    compile((kernel / "entry.py").read_text(encoding="utf-8"), "entry.py", "exec")


def test_write_kernel_metadata_private(kernel):
    assert '"is_private": "true"' in (kernel / "kernel-metadata.json").read_text(encoding="utf-8")


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
