"""Containment tests for lib.workspace (TST-0227).

Run standalone (``python -B tools/lib/tests/test_workspace_containment.py``)
or under pytest. Mirrors the receipt's two required controls: the denied
cross-session write plus a successful own-session write, and the unmediated
write that changes the victim tree hash.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))

from workspace import Codes, SessionBroker, SessionDenied, independent_tree_hash  # noqa: E402


def _broker(base: Path) -> tuple[SessionBroker, Path, Path]:
    broker = SessionBroker()
    victim = base / "victim"
    actor = base / "actor"
    broker.register("v", worktree_root=victim / "wt", artifact_root=victim / "art", runtime_dir=victim / "run")
    broker.register("a", worktree_root=actor / "wt", artifact_root=actor / "art", runtime_dir=actor / "run")
    (victim / "wt").mkdir(parents=True, exist_ok=True)
    (victim / "wt" / "base.txt").write_bytes(b"baseline\n")
    return broker, victim / "wt", actor / "wt"


def test_cross_session_write_denied_and_alert_names_both() -> None:
    base = Path(tempfile.mkdtemp(prefix="tst0227-"))
    try:
        broker, victim_wt, _actor_wt = _broker(base)
        denied = False
        alert = {}
        try:
            broker.write_file("a", victim_wt / "x.txt", b"hostile")
        except SessionDenied as exc:
            denied = True
            alert = exc.alert.as_dict()
        assert denied is True, "cross-session write must be denied"
        assert alert.get("actor") == "a" and alert.get("victim") == "v"
        assert (victim_wt / "x.txt").exists() is False
        assert broker.tree_hash("v")["worktree"] == independent_tree_hash(victim_wt)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_own_session_write_succeeds() -> None:
    base = Path(tempfile.mkdtemp(prefix="tst0227-"))
    try:
        broker, _victim_wt, actor_wt = _broker(base)
        broker.write_file("a", actor_wt / "own.txt", b"mine")
        assert (actor_wt / "own.txt").read_bytes() == b"mine"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_unmediated_write_changes_hash() -> None:
    base = Path(tempfile.mkdtemp(prefix="tst0227-"))
    try:
        broker, victim_wt, _actor_wt = _broker(base)
        before = independent_tree_hash(victim_wt)
        (victim_wt / "unmediated.txt").write_bytes(b"no broker")
        after = independent_tree_hash(victim_wt)
        assert before != after, "unmediated write must change the tree hash"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_denial_code_is_cross_session_write() -> None:
    base = Path(tempfile.mkdtemp(prefix="tst0227-"))
    try:
        broker, victim_wt, _actor_wt = _broker(base)
        try:
            broker.write_file("a", victim_wt / "y.txt", b"z")
            raise AssertionError("expected SessionDenied")
        except SessionDenied as exc:
            assert exc.code == Codes.CROSS_SESSION_WRITE
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    test_cross_session_write_denied_and_alert_names_both()
    test_own_session_write_succeeds()
    test_unmediated_write_changes_hash()
    test_denial_code_is_cross_session_write()
    print("SUCCESS:TST-0227 containment tests 4/4 green")
    raise SystemExit(0)
