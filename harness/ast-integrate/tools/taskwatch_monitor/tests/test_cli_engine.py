"""Tests for cli/engine.py — snapshot orchestration with injected I/O."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import PollResult, TaskStatus, TaskSpec  # noqa: E402
from probes.fep import FepDatabricksProbe  # noqa: E402
from probes.generic import GenericLogfileProbe  # noqa: E402
from cli import engine  # noqa: E402


class FakeFS:
    """Minimal FileSystem: maps a path to (exists, mtime, size, text)."""

    def __init__(self, entries: dict[str, dict[str, object]]) -> None:
        self.entries = entries

    def stat(self, path: str) -> tuple[bool, float | None, int | None]:
        entry = self.entries.get(path)
        if entry is None:
            return (False, None, None)
        return (
            bool(entry["exists"]),
            entry["mtime"],  # type: ignore[return-value]
            entry["size"],  # type: ignore[return-value]
        )

    def read_text(self, path: str) -> str:
        entry = self.entries[path]
        text = entry["text"]
        if isinstance(text, OSError):
            raise text
        return str(text)

    def glob(self, pattern: str) -> list[str]:
        return sorted(self.entries)


def _file_spec(task_id: str = "t", parser: str = "generic-logfile") -> TaskSpec:
    return TaskSpec(
        id=task_id,
        adapter="local-file-tail",
        parser=parser,
        config={"path": "/logs/run.log"},
    )


def _fs_with(text: object, *, mtime: float = 10.0, size: int = 20) -> FakeFS:
    return FakeFS(
        {"/logs/run.log": {"exists": True, "mtime": mtime, "size": size, "text": text}}
    )


# ── FakeFS helper branches ─────────────────────────────────────────────────────


def test_fakefs_missing_and_glob():
    fs = FakeFS({"a": {"exists": True, "mtime": 1.0, "size": 2, "text": "x"}})
    assert fs.stat("missing") == (False, None, None)
    assert fs.glob("*") == ["a"]


# ── resolve_probe ──────────────────────────────────────────────────────────────


def test_resolve_probe_known():
    assert isinstance(engine.resolve_probe("fep-databricks"), FepDatabricksProbe)


def test_resolve_probe_unknown_falls_back_to_generic():
    assert isinstance(engine.resolve_probe(""), GenericLogfileProbe)
    assert isinstance(engine.resolve_probe("nope"), GenericLogfileProbe)


# ── stall_flag ─────────────────────────────────────────────────────────────────


def test_stall_flag_blind_never_stalled():
    poll = PollResult(exists=True, mtime=1.0, error="boom")
    assert engine.stall_flag(poll, now=10_000.0, stall_after_s=10.0) is False


def test_stall_flag_no_mtime():
    poll = PollResult(exists=True, mtime=None)
    assert engine.stall_flag(poll, now=100.0, stall_after_s=10.0) is False


def test_stall_flag_stalled_when_old():
    poll = PollResult(exists=True, mtime=100.0)
    assert engine.stall_flag(poll, now=500.0, stall_after_s=300.0) is True


def test_stall_flag_fresh_not_stalled():
    poll = PollResult(exists=True, mtime=100.0)
    assert engine.stall_flag(poll, now=150.0, stall_after_s=300.0) is False


# ── _stall_after_for ───────────────────────────────────────────────────────────


def test_stall_after_for_override_int():
    spec = _file_spec()
    spec.config["stall_after_s"] = 60
    assert engine._stall_after_for(spec, 300.0) == 60.0


def test_stall_after_for_override_float():
    spec = _file_spec()
    spec.config["stall_after_s"] = 12.5
    assert engine._stall_after_for(spec, 300.0) == 12.5


def test_stall_after_for_bool_is_ignored():
    spec = _file_spec()
    spec.config["stall_after_s"] = True
    assert engine._stall_after_for(spec, 300.0) == 300.0


def test_stall_after_for_missing_uses_default():
    assert engine._stall_after_for(_file_spec(), 300.0) == 300.0


# ── poll_spec ──────────────────────────────────────────────────────────────────


def test_poll_spec_parses_lines():
    fs = _fs_with("step 4/8\n[gpu-util] 0: 98%")
    poll, reading = engine.poll_spec(_file_spec(), fs=fs)
    assert poll.exists is True
    assert reading.done == 4.0 and reading.total == 8.0


# ── snapshot ───────────────────────────────────────────────────────────────────


def test_snapshot_running_with_started_and_prior():
    fs = _fs_with("progress 2/8", mtime=990.0)
    views = engine.snapshot(
        [_file_spec()],
        fs=fs,
        now=1000.0,
        started={"t": 900.0},
        priors={"local-file-tail": 500.0},
        stall_after_s=300.0,
    )
    view = views[0]
    assert view.status is TaskStatus.RUNNING
    assert view.elapsed_s == 100.0
    assert view.eta.estimable  # measured from fraction+elapsed


def test_snapshot_without_started_or_prior_has_no_elapsed():
    fs = _fs_with("progress 2/8", mtime=999.0)
    views = engine.snapshot([_file_spec()], fs=fs, now=1000.0)
    assert views[0].elapsed_s is None
    assert not views[0].eta.estimable


def test_snapshot_stalled_when_source_old():
    fs = _fs_with("progress 2/8", mtime=100.0)
    views = engine.snapshot([_file_spec()], fs=fs, now=1000.0, stall_after_s=300.0)
    assert views[0].status is TaskStatus.STALLED
    assert views[0].stalled is True


def test_snapshot_terminal_never_stalled():
    fs = _fs_with("Receiving objects: 100% done", mtime=1.0)
    views = engine.snapshot([_file_spec()], fs=fs, now=10_000.0, stall_after_s=10.0)
    assert views[0].status is TaskStatus.DONE
    assert views[0].stalled is False


def test_snapshot_blind_on_read_error():
    fs = _fs_with(OSError("locked"))
    views = engine.snapshot([_file_spec()], fs=fs, now=1000.0)
    assert views[0].status is TaskStatus.BLIND
    assert views[0].blind is True


def test_snapshot_http_failed_status():
    spec = TaskSpec(id="ci", adapter="http-json", config={"url": "http://x"})
    views = engine.snapshot(
        [spec], http_get=lambda _url: '{"status": "failed"}', now=1000.0
    )
    assert views[0].status is TaskStatus.FAILED


def test_snapshot_now_defaults_to_clock():
    fs = _fs_with("progress 2/8", mtime=100.0)
    views = engine.snapshot(
        [_file_spec()], fs=fs, clock=lambda: 100.0, stall_after_s=300.0
    )
    # clock() == mtime ⇒ fresh, not stalled
    assert views[0].stalled is False
