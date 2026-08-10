"""The OS-lock liveness signal, proven in BOTH states across a real process boundary."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from coordination.oslock import LivenessLock, LockOutcome, lock_supported, probe_lock

CHILD = Path(__file__).resolve().parent / "lock_probe_child.py"


def _wait_for(path: Path, timeout: float = 30.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return path.read_text(encoding="utf-8")
        time.sleep(0.05)
    raise AssertionError(f"child never signalled readiness at {path}")


def test_locking_primitive_is_available() -> None:
    assert lock_supported() is True


def test_absent_file_is_not_computable_never_free(tmp_path: Path) -> None:
    """The single most important negative: a missing lock must NOT read as 'holder is gone'.

    ``probe_lock`` opens without ``O_CREAT`` precisely so a never-registered session cannot be
    classified DEAD and reaped.
    """
    probe = probe_lock(tmp_path / "nope.lock")
    assert probe.outcome is LockOutcome.NOT_COMPUTABLE
    assert not (tmp_path / "nope.lock").exists(), (
        "the probe must not create the lock file"
    )
    assert probe.says_dead is False


def test_probe_discriminates_alive_from_dead(tmp_path: Path) -> None:
    """BOTH-STATES control (single-signal-verification rule 3b) across a real process boundary.

    A probe that reported the same thing whether or not a holder was running would measure
    nothing, and the whole recovery design rests on this one signal.
    """
    lock = tmp_path / "live.lock"
    ready = tmp_path / "ready.txt"
    proc = subprocess.Popen([sys.executable, str(CHILD), str(lock), str(ready), "25"])  # noqa: S603
    try:
        assert "LOCK-HELD" in _wait_for(ready)
        held = probe_lock(lock)
        assert held.outcome is LockOutcome.HELD_BY_OTHER, held.to_dict()
        assert held.says_alive and not held.says_dead
    finally:
        proc.terminate()
        proc.wait(timeout=30)

    # The child was TERMINATED, so nothing ran its release path. The OS released the lock.
    freed = probe_lock(lock)
    assert freed.outcome is LockOutcome.FREE, freed.to_dict()
    assert freed.says_dead and not freed.says_alive


def test_killed_holder_still_releases(tmp_path: Path) -> None:
    """PID-reuse and cooperative-cleanup immunity: a killed process cannot leave a stuck lock."""
    lock = tmp_path / "killed.lock"
    ready = tmp_path / "ready.txt"
    proc = subprocess.Popen([sys.executable, str(CHILD), str(lock), str(ready), "60"])  # noqa: S603
    _wait_for(ready)
    proc.kill()
    proc.wait(timeout=30)
    assert probe_lock(lock).outcome is LockOutcome.FREE


def test_liveness_lock_release_is_idempotent(tmp_path: Path) -> None:
    lock = LivenessLock(tmp_path / "a" / "b.lock")
    assert lock.acquire() is True
    assert lock.acquire() is True, (
        "re-acquire by the same holder is a no-op, not a failure"
    )
    lock.release()
    lock.release()
    assert lock.acquired is False


def test_second_process_cannot_take_a_held_lock(tmp_path: Path) -> None:
    """Re-registering a still-live session id is detected rather than double-claimed."""
    lock_path = tmp_path / "contended.lock"
    ready = tmp_path / "ready.txt"
    proc = subprocess.Popen(
        [sys.executable, str(CHILD), str(lock_path), str(ready), "25"]
    )  # noqa: S603
    try:
        _wait_for(ready)
        contender = LivenessLock(lock_path)
        assert contender.acquire() is False
        assert contender.acquired is False
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def test_context_manager_releases_on_exception(tmp_path: Path) -> None:
    lock_path = tmp_path / "ctx.lock"
    with pytest.raises(RuntimeError):
        with LivenessLock(lock_path) as lock:
            assert lock.acquired
            raise RuntimeError("boom")
    assert probe_lock(lock_path).outcome is LockOutcome.FREE
