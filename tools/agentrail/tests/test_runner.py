"""The impure shell, measured HERMETICALLY: no network, no real process, no wall-clock waits.

The real filesystem adapter runs against a pytest ``tmp_path``; the real spawn adapter takes its
:func:`subprocess.run` as a constructor seam and is driven with a fake that raises each failure
class on demand. That is what buys 100% line+branch coverage here with zero pragmas.
"""

from __future__ import annotations

import errno
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from agentspec.clock import FixedClock

from agentrail.ports import CollectingWarnings, SpawnOutcome
from agentrail.plan import build_plan
from agentrail.rails import RailRow
from agentrail.resolve import Resolution, resolve
from agentrail.runner import (
    WIN_ERROR_FILENAME_EXCED_RANGE,
    LocalFileSystem,
    MonotonicClock,
    Ports,
    SubprocessSpawn,
    default_ports,
    dispatch,
    run_plan,
)
from fakes import FakeFileSystem, FakeSpawn, completed

EXE = "/bin/demo"


def row(**kwargs: object) -> RailRow:
    base: dict[str, object] = {
        "name": "demo",
        "exe_globs": (EXE,),
        "receipt_format": "text",
        "receipt_forbidden_markers": ("still in progress",),
        "verified": True,
    }
    base.update(kwargs)
    return RailRow(**base)  # pyright: ignore[reportArgumentType]


def stepping_clock() -> FixedClock:
    class Stepping(FixedClock):
        def now_ms(self) -> int:
            reading = super().now_ms()
            self.advance(25)
            return reading

    return Stepping()


# --------------------------------------------------------------------------------------------
# LocalFileSystem -- real disk, but only inside tmp_path.
# --------------------------------------------------------------------------------------------


def test_local_filesystem_round_trips_a_real_file(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    target = tmp_path / "nested" / "deeper" / "receipt.txt"
    fs.write_text(str(target), "hello")
    assert fs.is_file(str(target)) is True
    assert fs.read_bytes(str(target)) == b"hello"
    assert fs.glob(str(tmp_path / "nested" / "deeper" / "*.txt")) == (str(target),)


def test_local_filesystem_is_total_on_absence(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    missing = str(tmp_path / "nope.txt")
    assert fs.is_file(missing) is False
    assert fs.read_bytes(missing) is None
    assert fs.glob(str(tmp_path / "*.nothing")) == ()


def test_local_filesystem_does_not_read_a_directory_as_a_file(tmp_path: Path) -> None:
    assert LocalFileSystem().read_bytes(str(tmp_path)) is None


# --------------------------------------------------------------------------------------------
# MonotonicClock
# --------------------------------------------------------------------------------------------


def test_the_real_clock_is_non_negative_and_monotonic() -> None:
    clock = MonotonicClock()
    first = clock.now_ms()
    assert first >= 0
    assert clock.now_ms() >= first


def test_default_ports_assembles_the_real_trio() -> None:
    ports = default_ports()
    assert isinstance(ports, Ports)
    assert isinstance(ports.fs, LocalFileSystem)
    assert isinstance(ports.spawn, SubprocessSpawn)
    assert isinstance(ports.clock, MonotonicClock)


# --------------------------------------------------------------------------------------------
# SubprocessSpawn -- every arm driven through the injected `run` seam.
# --------------------------------------------------------------------------------------------


def test_the_spawn_adapter_encodes_stdin_and_returns_the_streams() -> None:
    seen: dict[str, object] = {}

    def fake_run(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        seen.update({"argv": tuple(argv), **kwargs})
        return completed(returncode=0, stdout=b"out", stderr=b"err")

    outcome = SubprocessSpawn(run=fake_run)(  # pyright: ignore[reportArgumentType]
        argv=("exe", "--flag"), stdin_payload="hi", timeout_s=30, cwd="/work"
    )
    assert outcome == SpawnOutcome(exit_code=0, stdout=b"out", stderr=b"err")
    assert seen["input"] == b"hi"
    assert seen["timeout"] == 30
    assert seen["cwd"] == "/work"
    assert seen["capture_output"] is True
    assert seen["check"] is False


def test_the_spawn_adapter_passes_none_when_there_is_no_stdin() -> None:
    captured: dict[str, object] = {}

    def fake_run(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        captured.update(kwargs)
        return completed()

    SubprocessSpawn(run=fake_run)(  # pyright: ignore[reportArgumentType]
        argv=("exe",), stdin_payload=None, timeout_s=1, cwd=None
    )
    assert captured["input"] is None


def test_a_timeout_becomes_a_closed_taxonomy_reason() -> None:
    def fake_run(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=list(argv), timeout=9)

    outcome = SubprocessSpawn(run=fake_run)(  # pyright: ignore[reportArgumentType]
        argv=("exe",), stdin_payload=None, timeout_s=9, cwd=None
    )
    assert outcome.error_reason == "timeout-9s"
    assert outcome.exit_code == -1
    assert "9s" in outcome.detail


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OSError(errno.E2BIG, "argument list too long"), "win-arg-limit"),
        (FileNotFoundError(errno.ENOENT, "no such file"), "spawn-failed"),
        (PermissionError(errno.EACCES, "denied"), "spawn-failed"),
    ],
)
def test_an_os_error_maps_onto_the_closed_taxonomy(exc: OSError, expected: str) -> None:
    def fake_run(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        raise exc

    outcome = SubprocessSpawn(run=fake_run)(  # pyright: ignore[reportArgumentType]
        argv=("exe",), stdin_payload=None, timeout_s=1, cwd=None
    )
    assert outcome.error_reason == expected


def test_windows_error_206_is_recognised_as_the_measured_argv_failure() -> None:
    """`os error 206` at payload_len=34472 is the failure this whole package exists for.

    The winerror below is the LITERAL 206, not ``WIN_ERROR_FILENAME_EXCED_RANGE``. Feeding the
    constant back into the test that names it made the test incapable of failing: measured,
    setting the constant to ``999999`` left both this test (``1 passed``) and the whole gated
    suite (``241 passed``) green, while a REAL winerror=206 then classified as ``spawn-failed``.
    That misclassification silently disables the recovery this package exists to provide --
    ``agentspec.retry.RETRYABLE_ONCE`` is exactly ``("win-arg-limit",)``, so a 206 landing
    anywhere else is never retried.
    """
    assert WIN_ERROR_FILENAME_EXCED_RANGE == 206, (
        "206 is a MEASURED Windows error code (ERROR_FILENAME_EXCED_RANGE), not a tunable"
    )
    exc = OSError("filename exceeds range")
    exc.winerror = 206  # pyright: ignore[reportAttributeAccessIssue]

    def fake_run(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        raise exc

    outcome = SubprocessSpawn(run=fake_run)(  # pyright: ignore[reportArgumentType]
        argv=("exe",), stdin_payload=None, timeout_s=1, cwd=None
    )
    assert outcome.error_reason == "win-arg-limit"


def test_the_spawn_adapter_defaults_to_the_real_subprocess_run() -> None:
    """Asserted, never CALLED -- calling it would spawn a process in the gated suite."""
    assert SubprocessSpawn().run is subprocess.run


# --------------------------------------------------------------------------------------------
# dispatch / run_plan -- the orchestration, entirely against fakes.
# --------------------------------------------------------------------------------------------


def test_a_clean_dispatch_judges_the_receipt_and_reports_success() -> None:
    fs = FakeFileSystem({EXE: b""})
    spawn = FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"3 files changed")])
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="do it",
        spill_dir="/spill",
        fs=fs,
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.ok is True
    assert report.terminal == "SUCCESS:u1"
    assert report.verdict is not None
    assert report.verdict.wall_ms == 25
    assert spawn.calls[0]["stdin_payload"] == "do it"
    assert spawn.calls[0]["timeout_s"] == 900
    assert f"exe={EXE}" in report.observation.artifacts


def test_a_file_transport_spills_the_prompt_to_disk_before_spawning() -> None:
    fs = FakeFileSystem({EXE: b""})
    spawn = FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")])
    report = dispatch(
        row(native_transport="file", prompt_flag="--pf"),
        unit_id="u1",
        prompt="the whole prompt",
        spill_dir="/spill",
        fs=fs,
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert fs.files["/spill/u1.prompt.txt"] == b"the whole prompt"
    assert spawn.calls[0]["stdin_payload"] is None
    assert "--pf" in spawn.calls[0]["argv"]  # pyright: ignore[reportOperatorIssue]
    assert "prompt=/spill/u1.prompt.txt" in report.observation.artifacts


def test_a_declared_receipt_file_is_read_instead_of_stdout() -> None:
    fs = FakeFileSystem({EXE: b"", "/out/r.txt": b"the real answer"})
    spawn = FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"chatter and noise")])
    report = dispatch(
        row(receipt_flag="-o"),
        unit_id="u1",
        prompt="p",
        spill_dir="/spill",
        receipt_path="/out/r.txt",
        fs=fs,
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.verdict is not None
    assert report.verdict.text == "the real answer"
    assert "receipt=/out/r.txt" in report.observation.artifacts


def test_a_declared_but_absent_receipt_never_falls_back_to_stdout() -> None:
    """Reading the chatter instead is how a progress stream gets reported as an answer."""
    fs = FakeFileSystem({EXE: b""})
    spawn = FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"still in progress")])
    report = dispatch(
        row(receipt_flag="-o"),
        unit_id="u1",
        prompt="p",
        spill_dir="/spill",
        receipt_path="/out/missing.txt",
        fs=fs,
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.verdict is not None
    assert report.verdict.reason == "receipt-missing"
    assert report.verdict.severed is True


def test_stderr_travels_as_diagnostics_only() -> None:
    fs = FakeFileSystem({EXE: b""})
    spawn = FakeSpawn(
        [SpawnOutcome(exit_code=0, stdout=b"answer", stderr=b"[codex] working\xff")]
    )
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=fs,
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.ok is True


def test_an_unresolvable_rail_is_reported_as_env_missing_and_never_spawned() -> None:
    spawn = FakeSpawn()
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem(),
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.terminal == "FAILED:u1 env-missing"
    assert report.observation.error is not None
    assert report.observation.error.code == "env-missing-demo"
    assert spawn.calls == []


def test_an_illegal_dispatch_shape_is_refused_and_never_spawned() -> None:
    spawn = FakeSpawn()
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem({EXE: b""}),
        spawn=spawn,
        clock=stepping_clock(),
        background=True,
        awaited=True,
    )
    assert report.terminal == "FAILED:u1 policy-violation"
    assert spawn.calls == []


def test_an_unshortenable_over_cap_argv_is_reported_not_dispatched() -> None:
    spawn = FakeSpawn()
    report = dispatch(
        row(base_flags=("--pad", "y" * 400), cap=100),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem({EXE: b""}),
        spawn=spawn,
        clock=stepping_clock(),
    )
    assert report.terminal == "FAILED:u1 win-arg-limit"
    assert spawn.calls == []
    assert report.observation.error is not None
    assert "never reaches argv" in report.observation.error.root_cause


def test_a_transport_failure_is_enveloped_with_the_spawns_reason() -> None:
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem({EXE: b""}),
        spawn=FakeSpawn(
            [SpawnOutcome(exit_code=-1, error_reason="timeout-30s", detail="killed")]
        ),
        clock=stepping_clock(),
    )
    assert report.terminal == "FAILED:u1 timeout"
    assert report.observation.error is not None
    assert report.observation.error.code == "timeout-30s"
    assert report.observation.error.root_cause == "killed"


def test_run_plan_can_be_driven_with_a_pre_built_plan() -> None:
    """The split exists so a caller can inspect the plan before committing to a dispatch."""
    fs = FakeFileSystem({EXE: b""})
    demo = row()
    plan = build_plan(demo, EXE, unit_id="u1", prompt="p", spill_dir="/s")
    resolution = resolve(demo, fs)
    report = run_plan(
        plan,
        row=demo,
        resolution=resolution,
        fs=fs,
        spawn=FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")]),
        clock=stepping_clock(),
    )
    assert report.ok is True
    assert resolution.source == "glob"
    assert isinstance(resolution, Resolution)


def test_the_fallback_warning_reaches_the_result_artifacts() -> None:
    fs = FakeFileSystem({"/shim/demo.cmd": b""})
    sink = CollectingWarnings()
    report = dispatch(
        row(exe_globs=("/vendor/*/demo",), exe_fallbacks=("/shim/demo.cmd",)),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=fs,
        spawn=FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")]),
        clock=stepping_clock(),
        sink=sink,
    )
    assert "resolved-by=fallback" in report.observation.artifacts
    assert any("npm shim" in item for item in report.observation.artifacts)
    assert len(sink.messages) == 1


def test_a_spilled_and_retried_plan_records_both_in_the_artifacts() -> None:
    fat = row(
        native_transport="argv",
        prompt_flag="--prompt-file",
        base_flags=("--pad", "y" * 200),
        cap=270,
    )
    fs = FakeFileSystem({EXE: b""})
    report = dispatch(
        fat,
        unit_id="u1",
        prompt="p",
        spill_dir="/a/very/long/spill/directory",
        fs=fs,
        spawn=FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")]),
        clock=stepping_clock(),
    )
    joined = " | ".join(report.observation.artifacts)
    assert "spilled-from=argv->stdin" in joined
    assert "retry=" in joined


def test_dispatch_creates_its_own_warning_sink_when_none_is_given() -> None:
    report = dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem({EXE: b""}),
        spawn=FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")]),
        clock=stepping_clock(),
        sink=None,
    )
    assert report.ok is True


def test_the_cwd_is_forwarded_to_the_spawn() -> None:
    spawn = FakeSpawn([SpawnOutcome(exit_code=0, stdout=b"done")])
    dispatch(
        row(),
        unit_id="u1",
        prompt="p",
        spill_dir="/s",
        fs=FakeFileSystem({EXE: b""}),
        spawn=spawn,
        clock=stepping_clock(),
        cwd="/work",
    )
    assert spawn.calls[0]["cwd"] == "/work"


def test_the_fake_spawn_has_a_default_outcome() -> None:
    assert (
        FakeSpawn()(argv=("x",), stdin_payload=None, timeout_s=1, cwd=None).stdout
        == b"ok"
    )
