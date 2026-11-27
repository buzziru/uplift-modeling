import ast
import json
import subprocess
import tempfile
from pathlib import Path
from typing import get_args

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift import kaggle_jobs
from uplift.kaggle_jobs import (
    DATA_FILES,
    DATASET,
    KERNEL_STATUS,
    MAX_MISSES,
    USER,
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

SLOT_LIMITED = "Kernel push error: Maximum batch CPU session count of 5 reached."
PUSHED = "Kernel version 3 successfully pushed.  Please check"


# 기대 slug는 Kaggle에 이미 올라간 kernel id 꼴이다(data/kaggle/state.json의 slug)
@pytest.mark.parametrize(
    ("part", "slug"),
    [(None, "uplift-exp-002"), ("s_learner", "uplift-exp-002-s-learner")],
    ids=["no_part", "with_part"],
)
def test_slug_for_formats(part, slug):
    assert slug_for("EXP-002-method-compare", part) == slug


@settings(max_examples=30)
@given(
    exp=st.from_regex(r"EXP-[0-9]{3}(-[a-z]+)*", fullmatch=True),
    part=st.from_regex(r"[a-z]+(_[a-z]+)*", fullmatch=True),
)
def test_slug_for_part_extends_base_slug(exp, part):
    assert slug_for(exp, part).startswith(slug_for(exp, None) + "-")


@settings(max_examples=30)
@given(
    exp=st.from_regex(r"EXP-[0-9]{3}(-[a-z]+)*", fullmatch=True),
    part=st.from_regex(r"[a-z]+(_[a-z]+)*", fullmatch=True),
)
def test_slug_for_part_has_no_underscores(exp, part):
    assert "_" not in slug_for(exp, part)


# PUSHED, SLOT_LIMITED는 kaggle kernels push가 버전과 슬롯 제한을 알리는 출력 꼴이다
@pytest.mark.parametrize(("text", "version"), [(PUSHED, 3), (SLOT_LIMITED, None)])
def test_parse_version(text, version):
    assert parse_version(text) == version


@pytest.mark.parametrize(("text", "limited"), [(SLOT_LIMITED, True), (PUSHED, False)])
def test_slot_limited(text, limited):
    assert slot_limited(text) is limited


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        (form, status)
        for raw, status in KERNEL_STATUS.items()
        for form in (f"KernelWorkerStatus.{raw}", raw, raw.lower())
    ],
)
def test_parse_status_maps(raw, status):
    assert parse_status(f'buzziru/x has status "{raw}"') == status


def test_parse_status_missing_is_none():
    assert parse_status("404 Not Found") is None


def test_parse_status_rejects_unknown():
    with pytest.raises(ValueError, match="NEW_STATE"):
        parse_status('buzziru/x has status "KernelWorkerStatus.NEW_STATE"')


@pytest.mark.parametrize(
    ("misses", "status"), [(MAX_MISSES - 1, "running"), (MAX_MISSES, "unknown")]
)
def test_update_status_unknown_after_max_misses(misses, status):
    job = Job(slug="a", exp="E", sha="s", status="running")
    for _ in range(misses):
        update_status(job, None)
    assert job.status == status


def test_update_status_success_resets_misses():
    job = Job(slug="a", exp="E", sha="s", status="running", misses=MAX_MISSES - 1)
    update_status(job, "complete")
    assert (job.status, job.misses) == ("complete", 0)


@pytest.fixture
def failing_cli(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="from-stdout", stderr="from-stderr")

    monkeypatch.setattr(kaggle_jobs.subprocess, "run", fake_run)


def test_kaggle_raises_on_nonzero_exit(failing_cli):
    with pytest.raises(RuntimeError, match="exit 1"):
        kaggle_jobs.kaggle("kernels", "output")


def test_kaggle_unchecked_returns_both_streams(failing_cli):
    out = kaggle_jobs.kaggle("kernels", "status", check=False)
    assert "from-stdout" in out
    assert "from-stderr" in out


# 활성 작업 둘(pushed, running)을 손으로 센 값: 5 - 2, 1 - 2를 0에서 자른 값
@pytest.mark.parametrize(("limit", "free"), [(5, 3), (1, 0)])
def test_free_slots_counts_active(limit, free):
    statuses: list[Status] = ["pushed", "running", "complete", "queued", "error"]
    jobs = [Job(slug="a", exp="E", sha="s", status=s) for s in statuses]
    assert free_slots(jobs, limit=limit) == free


@given(statuses=st.lists(st.sampled_from(get_args(Status))), limit=st.integers(0, 10))
def test_free_slots_stays_within_limit(statuses, limit):
    jobs = [Job(slug="a", exp="E", sha="s", status=s) for s in statuses]
    assert 0 <= free_slots(jobs, limit=limit) <= limit


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


def _entry_values(entry: Path) -> dict[str, object]:
    names = {"SHA", "EXP", "ARGS", "EXPECTED"}
    return {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(entry.read_text(encoding="utf-8")).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in names
    }


@settings(deadline=None, max_examples=50)
@given(
    sha=st.text(),
    exp=st.text(),
    args=st.text(),
    manifest=st.dictionaries(st.text(), st.text(), max_size=3),
)
def test_write_kernel_entry_carries_job_fields(sha, exp, args, manifest):
    job = Job(slug="s", exp=exp, sha=sha, args=args, manifest=manifest)
    with tempfile.TemporaryDirectory() as folder:
        write_kernel(job, Path(folder))
        values = _entry_values(Path(folder) / "entry.py")
    assert values == {"SHA": sha, "EXP": exp, "ARGS": args, "EXPECTED": manifest}


def test_write_kernel_metadata_is_private_kernel_on_dataset(tmp_path):
    write_kernel(JOB, tmp_path)
    meta = json.loads((tmp_path / "kernel-metadata.json").read_text(encoding="utf-8"))
    picked = {k: meta[k] for k in ("id", "is_private", "dataset_sources")}
    assert picked == {
        "id": f"{USER}/{JOB.slug}",
        "is_private": "true",
        "dataset_sources": [f"{USER}/{DATASET}"],
    }


@settings(deadline=None, max_examples=30)
@given(contents=st.tuples(*(st.binary() for _ in DATA_FILES)))
def test_manifest_round_trip(contents):
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        for file, content in zip(DATA_FILES, contents, strict=True):
            (folder / file).write_bytes(content)
        written = write_manifest(folder)
        assert read_manifest(folder / kaggle_jobs.MANIFEST) == written


@pytest.mark.parametrize(
    ("hashes", "named"),
    [
        ({"train.parquet": "h1"}, "folds.parquet"),
        ({"train.parquet": "h1", "folds.parquet": "h2", "extra.parquet": "h3"}, "extra.parquet"),
    ],
    ids=["missing", "extra"],
)
def test_read_manifest_requires_exactly_data_files(tmp_path, hashes, named):
    (tmp_path / "manifest.json").write_text(json.dumps(hashes), encoding="utf-8")
    with pytest.raises(ValueError, match=named):
        read_manifest(tmp_path / "manifest.json")
