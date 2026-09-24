"""Tests for hygiene_launch: admission gate + job-object launch shim.

The Win32 job is behind a seam (FakeJob here); the child process is REAL (this
interpreter), so the launch/wait/exit-code/bill flow runs end to end on Linux.
"""

from __future__ import annotations

import ctypes
import json
import sys

import pytest

import hygiene_launch as launch

NOW = 1_788_324_600
GIB = 1024**3


def beat(**over):
    payload = {
        "schema": "process-hygiene-heartbeat-v1",
        "ts": NOW - 60,
        "tier": "normal",
        "apply": True,
        "pressure_modes": [],
        "commit_headroom_bytes": 20 * GIB,
        "minutes_to_commit_limit": None,
        "free_bytes": 8 * GIB,
    }
    payload.update(over)
    return payload


# ----------------------------------------------------------------- decisions


def test_calm_box_is_admitted_without_warnings():
    verdict = launch.decide(beat(), now=NOW)
    assert verdict.admit is True
    assert verdict.warnings == []
    assert verdict.reason == "tier normal"


def test_critical_tier_is_refused_with_the_mode_named():
    verdict = launch.decide(
        beat(tier="critical", pressure_modes=["commit-exhaustion"]), now=NOW
    )
    assert verdict.admit is False
    assert "critical" in verdict.reason and "commit-exhaustion" in verdict.reason
    assert "hygiene.py explain" in verdict.hint


def test_imminent_exhaustion_is_refused_even_at_elevated():
    verdict = launch.decide(
        beat(tier="elevated", minutes_to_commit_limit=12.0), now=NOW
    )
    assert verdict.admit is False
    assert "12 min" in verdict.reason


def test_elevated_tier_is_admitted_with_a_warning():
    verdict = launch.decide(
        beat(tier="elevated", pressure_modes=["working-set"]), now=NOW
    )
    assert verdict.admit is True
    assert any("elevated" in w for w in verdict.warnings)


def test_force_overrides_a_refusal_but_keeps_the_warning():
    verdict = launch.decide(beat(tier="critical"), now=NOW, force=True)
    assert verdict.admit is True
    assert any("forced" in w for w in verdict.warnings)


@pytest.mark.parametrize("heartbeat", [None, {"garbage": True}, beat(ts=NOW - 3600)])
def test_missing_stale_or_malformed_heartbeat_fails_open(heartbeat):
    # a gate that blocks work because the watchdog died is worse than no gate
    verdict = launch.decide(heartbeat, now=NOW)
    assert verdict.admit is True
    assert any("heartbeat" in w for w in verdict.warnings)


def test_read_heartbeat_tolerates_missing_and_corrupt_files(tmp_path):
    assert launch.read_heartbeat(tmp_path / "none.json") is None
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    assert launch.read_heartbeat(tmp_path / "bad.json") is None
    (tmp_path / "ok.json").write_text(json.dumps(beat()), encoding="utf-8")
    assert launch.read_heartbeat(tmp_path / "ok.json")["tier"] == "normal"


# ------------------------------------------------------------------ job seam


class FakeJob:
    instances: list["FakeJob"] = []

    def __init__(self, limit_bytes: int | None, *, fail_assign=False):
        self.limit_bytes = limit_bytes
        self.assigned = False
        self.closed = False
        self.fail_assign = fail_assign
        self.peaks = iter([100 * 2**20, 300 * 2**20, 900 * 2**20])
        self.last_peak = 0
        FakeJob.instances.append(self)

    def assign_current(self) -> bool:
        self.assigned = not self.fail_assign
        return self.assigned

    def peak_bytes(self) -> int:
        self.last_peak = next(self.peaks, self.last_peak)
        return self.last_peak

    def close(self) -> None:
        self.closed = True


def child(code=0, sleep=0.0):
    return [
        sys.executable,
        "-c",
        f"import sys, time; time.sleep({sleep}); sys.exit({code})",
    ]


def run(tmp_path, *extra, job_factory=None, heartbeat=None, command=None, capsys=None):
    hb = tmp_path / "heartbeat.json"
    if heartbeat is not None:
        hb.write_text(json.dumps(heartbeat), encoding="utf-8")
    bill = tmp_path / "sessions.jsonl"
    argv = [
        "--heartbeat",
        str(hb),
        "--bill",
        str(bill),
        "--poll-seconds",
        "0.05",
        *extra,
        "--",
        *(command or child()),
    ]
    return launch.main(argv, now=lambda: NOW, job_factory=job_factory or FakeJob), bill


def test_admitted_launch_runs_the_child_inside_a_job_and_bills_the_session(
    tmp_path, capsys
):
    FakeJob.instances.clear()
    code, bill = run(
        tmp_path,
        "--runtime",
        "claude",
        "--job-memory-limit",
        str(6 * GIB),
        heartbeat=beat(),
        command=child(3, 0.15),
    )
    assert code == 3  # the child's exit code is passed through
    job = FakeJob.instances[0]
    assert job.limit_bytes == 6 * GIB and job.assigned and job.closed
    rows = [json.loads(line) for line in bill.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == "process-hygiene-session-v1"
    assert row["runtime"] == "claude" and row["exit_code"] == 3
    assert row["peak_job_bytes"] == 900 * 2**20
    assert row["job"] is True and row["job_memory_limit_bytes"] == 6 * GIB
    assert row["admitted"]["reason"] == "tier normal"
    err = capsys.readouterr().err
    assert "peak job memory" in err


def test_refused_launch_exits_75_and_runs_nothing(tmp_path, capsys):
    FakeJob.instances.clear()
    code, bill = run(
        tmp_path, heartbeat=beat(tier="critical", pressure_modes=["commit-exhaustion"])
    )
    assert code == launch.EXIT_REFUSED == 75
    assert FakeJob.instances == []
    assert not bill.exists()
    err = capsys.readouterr().err
    assert "REFUSED" in err and "--force" in err


def test_forced_launch_proceeds_and_records_the_force(tmp_path, capsys):
    code, bill = run(tmp_path, "--force", heartbeat=beat(tier="critical"))
    assert code == 0
    row = json.loads(bill.read_text(encoding="utf-8").splitlines()[0])
    assert any("forced" in w for w in row["admitted"]["warnings"])


def test_soft_limit_warns_once_when_the_peak_crosses_it(tmp_path, capsys):
    code, _ = run(
        tmp_path,
        "--notify-limit",
        str(200 * 2**20),
        heartbeat=beat(),
        command=child(0, 0.3),
    )
    assert code == 0
    err = capsys.readouterr().err
    assert err.count("soft memory limit") == 1


def test_job_assignment_failure_is_fail_open_and_recorded(tmp_path, capsys):
    def failing(limit):
        return FakeJob(limit, fail_assign=True)

    # a child that outlives one poll interval, so the no-job loop path iterates too
    code, bill = run(
        tmp_path, heartbeat=beat(), job_factory=failing, command=child(0, 0.15)
    )
    assert code == 0
    row = json.loads(bill.read_text(encoding="utf-8").splitlines()[0])
    assert row["job"] is False
    assert "without a job object" in capsys.readouterr().err


def test_job_factory_that_raises_is_fail_open(tmp_path, capsys):
    def boom(limit):
        raise OSError("no job for you")

    code, bill = run(tmp_path, heartbeat=beat(), job_factory=boom)
    assert code == 0
    assert json.loads(bill.read_text(encoding="utf-8").splitlines()[0])["job"] is False


def test_dry_run_prints_the_verdict_and_runs_nothing(tmp_path, capsys):
    FakeJob.instances.clear()
    code, bill = run(tmp_path, "--dry-run", heartbeat=beat(tier="elevated"))
    assert code == 0
    out = capsys.readouterr().out
    assert "ADMIT" in out and "elevated" in out
    assert FakeJob.instances == [] and not bill.exists()


def test_missing_command_is_a_usage_error(tmp_path, capsys):
    code = launch.main(
        ["--heartbeat", str(tmp_path / "hb.json")], now=lambda: NOW, job_factory=FakeJob
    )
    assert code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_runtime_defaults_to_the_command_basename(tmp_path):
    _, bill = run(tmp_path, heartbeat=beat(), command=[sys.executable, "-c", "pass"])
    row = json.loads(bill.read_text(encoding="utf-8").splitlines()[0])
    assert row["runtime"] == launch._basename(sys.executable)


def test_child_that_cannot_start_is_reported(tmp_path, capsys):
    code, bill = run(
        tmp_path, heartbeat=beat(), command=["definitely-not-a-real-binary-xyz"]
    )
    assert code == 127
    assert "could not start" in capsys.readouterr().err
    assert (
        json.loads(bill.read_text(encoding="utf-8").splitlines()[0])["exit_code"] == 127
    )


# ------------------------------------------------------- Win32 struct layout


def test_job_object_structs_have_the_win64_layout():
    """The ctypes structures are declared with explicit fixed-width types, so their
    sizes must match the Win64 ABI even on Linux: 64 for the basic limits, 144 for
    the extended structure. A wrong field type would silently corrupt the call."""
    assert ctypes.sizeof(launch.JOBOBJECT_BASIC_LIMIT_INFORMATION) == 64
    assert ctypes.sizeof(launch.IO_COUNTERS) == 48
    assert ctypes.sizeof(launch.JOBOBJECT_EXTENDED_LIMIT_INFORMATION) == 144
    assert launch.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE == 0x2000
    assert launch.JOB_OBJECT_LIMIT_JOB_MEMORY == 0x200
    assert launch.JobObjectExtendedLimitInformation == 9


def test_default_job_factory_is_windows_only():
    with pytest.raises(OSError, match="Windows"):
        launch._win32_job(None)
