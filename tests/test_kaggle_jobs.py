from uplift.kaggle_jobs import (
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


def test_slug_uses_experiment_id_and_part():
    assert slug_for("EXP-002-method-compare", None) == "uplift-exp-002"
    assert slug_for("EXP-002-method-compare", "s_learner") == "uplift-exp-002-s-learner"


def test_parse_push_and_status_outputs():
    assert parse_version("Kernel version 3 successfully pushed.  Please check") == 3
    assert parse_version("Kernel push error: Maximum batch CPU session count of 5 reached.") is None
    assert slot_limited("Kernel push error: Maximum batch CPU session count of 5 reached.")
    assert parse_status('buzziru/x has status "KernelWorkerStatus.RUNNING"') == "running"
    assert parse_status('buzziru/x has status "KernelWorkerStatus.COMPLETE"') == "complete"
    assert parse_status('buzziru/x has status "KernelWorkerStatus.ERROR"') == "error"
    assert parse_status("404 Not Found") is None


def test_free_slots_counts_only_active_jobs():
    jobs = [
        Job("a", "E", "s", status=s) for s in ["pushed", "running", "complete", "queued", "error"]
    ]
    assert free_slots(jobs) == 3
    assert free_slots(jobs, limit=1) == 0


def test_state_round_trip_and_kernel_files(tmp_path):
    jobs = [Job("uplift-exp-002-s-learner", "EXP-002-x", "abc123", "--part s_learner")]
    save_jobs(tmp_path / "state.json", jobs)
    assert load_jobs(tmp_path / "state.json") == jobs
    write_kernel(jobs[0], tmp_path / "k")
    entry = (tmp_path / "k" / "entry.py").read_text(encoding="utf-8")
    assert 'SHA = "abc123"' in entry and "--part s_learner" in entry
    assert "/kaggle/input/uplift-hillstrom-train" in entry
    meta = (tmp_path / "k" / "kernel-metadata.json").read_text(encoding="utf-8")
    assert '"is_private": "true"' in meta
