"""IMP-0029: the preflight gate refuses each precondition with a distinct code.

Runnable directly (``python3 -B tools/plugin/tests/test_preflight.py``) and under
pytest. Uses plain directories plus real flocks so it needs no privileges; the
mounted-volume paths are exercised by the unit's probes.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import preflight as P  # noqa: E402


def _tree(root: Path) -> None:
    (root / "plugin.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (root / "commands").mkdir(exist_ok=True)
    (root / "commands" / "ping.md").write_text("# ping\n", encoding="utf-8")


def test_exit_codes_are_distinct_and_named() -> None:
    codes = [P.EXIT_OK, P.EXIT_DISK, P.EXIT_PERM, P.EXIT_CLIENT_LOCK, P.EXIT_LIFECYCLE_LOCK]
    assert codes == [0, 11, 12, 13, 14] and len(set(codes)) == 5
    reasons = {P.REASON_OK, P.REASON_DISK, P.REASON_PERM, P.REASON_CLIENT_LOCK, P.REASON_LIFECYCLE_LOCK}
    assert len(reasons) == 5


def test_healthy_tree_passes_and_holds_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="preflight-t-") as td:
        root = Path(td)
        _tree(root)
        r = P.run_preflight(root, payload_bytes=1024, backup_bytes=1024, acquire=True)
        try:
            assert r.exit_code == P.EXIT_OK and r.reason == P.REASON_OK and r.lock is not None
            assert r.observation["disk"]["free_bytes"] == P.os_free_bytes(root)
            assert os.getpid() in P.write_lock_holders(root / P.LOCK_NAME) or P._locked(root / P.LOCK_NAME)
            second = P.run_preflight(root, payload_bytes=1024, backup_bytes=1024, acquire=True)
            assert second.exit_code == P.EXIT_LIFECYCLE_LOCK and second.lock is None
        finally:
            if r.lock is not None:
                r.lock.release()
        assert P.run_preflight(root, payload_bytes=1024, backup_bytes=1024).exit_code == P.EXIT_OK


def test_disk_refusal_uses_statvfs_or_capacity_mark() -> None:
    with tempfile.TemporaryDirectory(prefix="preflight-t-") as td:
        root = Path(td)
        _tree(root)
        # Twice the free space plus a margin: other tenants freeing /tmp cannot satisfy it.
        huge = P.os_free_bytes(root) * 2 + (1 << 20)
        r = P.run_preflight(root, payload_bytes=huge, backup_bytes=0)
        assert r.exit_code == P.EXIT_DISK and r.observation["disk"]["needed_bytes"] == huge
        (root / P.CAP_MARK).write_text("full\n", encoding="utf-8")
        r2 = P.run_preflight(root, payload_bytes=1, backup_bytes=1)
        assert r2.exit_code == P.EXIT_DISK and r2.observation["disk"]["capacity_mark"] is True


def test_client_write_lock_refused_then_released() -> None:
    with tempfile.TemporaryDirectory(prefix="preflight-t-") as td:
        root = Path(td)
        _tree(root)
        holder = P.spawn_lock_holder(root / "plugin.json")
        try:
            assert getattr(holder, "lock_confirmed", False) is True
            r = P.run_preflight(root, payload_bytes=1024, backup_bytes=1024, client_retries=2, backoff_s=0)
            assert r.exit_code == P.EXIT_CLIENT_LOCK and r.reason == P.REASON_CLIENT_LOCK
            assert r.observation["client_lock"]["attempts"] == 2
            assert holder.pid in r.observation["client_lock"]["holders"] or r.observation["client_lock"]["locked"]
        finally:
            P.stop_holder(holder)
        assert P.run_preflight(root, payload_bytes=1024, backup_bytes=1024).exit_code == P.EXIT_OK


def test_lifecycle_lock_held_by_other_process() -> None:
    with tempfile.TemporaryDirectory(prefix="preflight-t-") as td:
        root = Path(td)
        _tree(root)
        holder = P.spawn_lock_holder(root / P.LOCK_NAME)
        try:
            r = P.run_preflight(root, payload_bytes=1024, backup_bytes=1024, acquire=True)
            assert r.exit_code == P.EXIT_LIFECYCLE_LOCK and r.lock is None
            probe = P.run_preflight(root, payload_bytes=1024, backup_bytes=1024, acquire=False)
            assert probe.exit_code == P.EXIT_LIFECYCLE_LOCK
        finally:
            P.stop_holder(holder)


def test_proc_locks_parser_skips_waiters_and_garbage() -> None:
    rows = P.parse_proc_locks()
    for row in rows:
        assert row["kind"] != "->" and isinstance(row["pid"], int)
        assert {"mode", "major", "minor", "ino"} <= set(row)
    assert P.locks_for(Path("/definitely/not/here/x")) == []


TESTS = [
    test_exit_codes_are_distinct_and_named,
    test_healthy_tree_passes_and_holds_lock,
    test_disk_refusal_uses_statvfs_or_capacity_mark,
    test_client_write_lock_refused_then_released,
    test_lifecycle_lock_held_by_other_process,
    test_proc_locks_parser_skips_waiters_and_garbage,
]


def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
