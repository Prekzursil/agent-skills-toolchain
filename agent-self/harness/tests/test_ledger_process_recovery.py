from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness.ledger import EventLedger, _FileLock


_ORPHAN_LOCK = r"""
import os
from pathlib import Path

from harness.ledger import _FileLock

lock = _FileLock(Path(os.environ["HARNESS_TEST_LOCK_PATH"]), timeout=5.0)
lock.__enter__()
os._exit(23)
"""

_APPEND_EVENT = r"""
import os
from pathlib import Path

from harness.ledger import EventLedger

Path(os.environ["HARNESS_TEST_READY_PATH"]).write_text("ready", encoding="ascii")
event = EventLedger(
    Path(os.environ["HARNESS_TEST_STATE_ROOT"]),
    legacy_root=Path(os.environ["HARNESS_TEST_LEGACY_ROOT"]),
).append(
    os.environ["HARNESS_TEST_PROJECT"],
    "turn",
    dedupe_key="successor",
    marker="after-killed-worker",
)
assert event is not None
assert event["kind"] == "turn"
"""

_HOLD_OS_LOCK = r"""
import os
import time
from pathlib import Path

from harness.ledger import _FileLock

ready = Path(os.environ["HARNESS_TEST_READY_PATH"])
release = Path(os.environ["HARNESS_TEST_RELEASE_PATH"])
with _FileLock(Path(os.environ["HARNESS_TEST_LOCK_PATH"]), timeout=5.0):
    ready.write_text("ready", encoding="ascii")
    deadline = time.monotonic() + 5.0
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("parent did not release held-lock fixture")
        time.sleep(0.01)
"""


def _child_env(tmp_path: Path, project: Path, lock_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    agent_self = Path(__file__).resolve().parents[2]
    prior_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(agent_self), prior_pythonpath) if part
    )
    env["HARNESS_TEST_STATE_ROOT"] = str(tmp_path / "state")
    env["HARNESS_TEST_LEGACY_ROOT"] = str(tmp_path / "no-legacy")
    env["HARNESS_TEST_PROJECT"] = str(project)
    env["HARNESS_TEST_LOCK_PATH"] = str(lock_path)
    env["HARNESS_TEST_READY_PATH"] = str(tmp_path / "successor-ready")
    env["HARNESS_TEST_RELEASE_PATH"] = str(tmp_path / "release-owner")
    return env


def _wait_for_ready(
    process: subprocess.Popen[str], ready_path: Path, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready_path.is_file():
            return
        if process.poll() is not None:
            break
        time.sleep(0.01)

    if process.poll() is None:
        process.kill()
    _stdout, stderr = process.communicate(timeout=5)
    pytest.fail(
        "successor did not reach EventLedger.append "
        f"(returncode={process.returncode}, stderr={stderr!r})"
    )


def test_append_recovers_after_worker_exits_while_os_lock_exists(tmp_path):
    """A killed hook worker must not make the next ledger append miss its deadline."""
    project = tmp_path / "project"
    project.mkdir()
    ledger = EventLedger(tmp_path / "state", legacy_root=tmp_path / "no-legacy")
    lock_path = ledger._dir(str(project)) / ".lock"
    env = _child_env(tmp_path, project, lock_path)

    crashed = subprocess.run(
        [sys.executable, "-c", _ORPHAN_LOCK],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert crashed.returncode == 23
    assert lock_path.exists(), "fixture did not create the lock file"

    ready_path = Path(env["HARNESS_TEST_READY_PATH"])
    successor = subprocess.Popen(
        [sys.executable, "-c", _APPEND_EVENT],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_for_ready(successor, ready_path, timeout=5)
    try:
        _stdout, stderr = successor.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        successor.kill()
        _stdout, stderr = successor.communicate(timeout=5)
        pytest.fail("successor append remained blocked by the killed worker's lock")

    assert successor.returncode == 0, stderr
    recovered = EventLedger(tmp_path / "state", legacy_root=tmp_path / "no-legacy")
    stored = [
        event
        for event in recovered.replay(str(project), limit=20)
        if event.get("marker") == "after-killed-worker"
    ]
    assert len(stored) == 1
    assert lock_path.exists()
    follow_on = recovered.append(
        str(project),
        "turn",
        dedupe_key="follow-on",
        marker="after-recovery-follow-on",
    )
    assert follow_on is not None
    assert list((tmp_path / "state").rglob("*.tmp")) == []


def test_os_lock_excludes_a_live_process_then_releases_on_exit(tmp_path):
    lock_path = tmp_path / "live-owner.lock"
    project = tmp_path / "project"
    project.mkdir()
    env = _child_env(tmp_path, project, lock_path)
    ready_path = Path(env["HARNESS_TEST_READY_PATH"])
    release_path = Path(env["HARNESS_TEST_RELEASE_PATH"])
    owner = subprocess.Popen(
        [sys.executable, "-c", _HOLD_OS_LOCK],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_ready(owner, ready_path, timeout=5)
        with pytest.raises(TimeoutError):
            _FileLock(lock_path, timeout=0.05).__enter__()
        release_path.write_text("release", encoding="ascii")
        _stdout, stderr = owner.communicate(timeout=5)
        assert owner.returncode == 0, stderr
        with _FileLock(lock_path, timeout=0.5) as acquired:
            assert acquired.handle is not None
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.communicate(timeout=5)
