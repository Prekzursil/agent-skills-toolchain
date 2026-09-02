"""Live measurements for TST-0061: held-handle lifecycle on a Windows lock overlay."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from inventory import classify_tree, compare, inventory
from lifecycle import (
    locked_aware,
    naive_replace,
    naive_uninstall,
    rename_then_write_update,
)
from scenario import V1, V2, hold_kind, seed
from winlock import WinLockFS


def _tmp() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="tst0061-")


def _tree(tmp: str, name: str = "install") -> Path:
    return Path(tmp) / name


def test_update_with_held_handle_is_atomic_or_loudly_refused() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        pre = seed(root, V1)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "hook")
        result = locked_aware(fs, root, "update", new_version=V2)
        post = inventory(root)
        cls = classify_tree(root)
        unchanged = compare(pre, post)["identical"]
        refused = bool(result.get("refused")) and not result.get("ok")
        named = locker.pid in (result.get("named_pids") or [])
        mixed = cls == "mixed"
        passed = refused and unchanged and named and not mixed
        return {
            "id": "test_update_with_a_held_handle_is_atomic_or_loudly_refused",
            "result": "PASS" if passed else "FAIL",
            "refused": refused,
            "tree_unchanged": unchanged,
            "named_locking_pid": named,
            "classify": cls,
            "partial_tree": mixed,
            "locker": {"pid": locker.pid, "name": locker.name, "kind": locker.kind},
            "error": result.get("error"),
            "inventory_pre": pre,
            "inventory_post": post,
        }


def test_rollback_with_held_handle_leaves_no_partial_tree() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        seed(root, V2)
        pre = inventory(root)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "log")
        result = locked_aware(fs, root, "rollback", new_version=V1)
        post = inventory(root)
        cls = classify_tree(root)
        unchanged = compare(pre, post)["identical"]
        mixed = cls == "mixed"
        passed = (not result.get("ok")) and unchanged and not mixed
        return {
            "id": "test_rollback_with_a_held_handle_leaves_no_partial_tree",
            "result": "PASS" if passed else "FAIL",
            "refused": bool(result.get("refused")),
            "tree_unchanged": unchanged,
            "classify": cls,
            "partial_tree": mixed,
            "locker": {"pid": locker.pid, "name": locker.name, "kind": locker.kind},
            "error": result.get("error"),
            "inventory_pre": pre,
            "inventory_post": post,
        }


def test_error_names_the_locking_process_id() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        seed(root, V1)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "module")
        result = locked_aware(fs, root, "update", new_version=V2)
        err = str(result.get("error") or "")
        has_pid = f"pid={locker.pid}" in err
        has_name = locker.name in err
        passed = (not result.get("ok")) and has_pid and has_name
        return {
            "id": "test_error_names_the_locking_process_id",
            "result": "PASS" if passed else "FAIL",
            "error": err,
            "pid_token": f"pid={locker.pid}",
            "name_token": locker.name,
            "named_pids": result.get("named_pids"),
            "locker": {"pid": locker.pid, "name": locker.name, "kind": locker.kind},
        }


def test_unlocked_control_run_succeeds() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        seed(root, V1)
        fs = WinLockFS()
        result = locked_aware(fs, root, "update", new_version=V2)
        cls = classify_tree(root)
        passed = bool(result.get("ok")) and cls == "updated"
        rollback = locked_aware(fs, root, "rollback", new_version=V1)
        cls_rb = classify_tree(root)
        passed = passed and bool(rollback.get("ok")) and cls_rb == "baseline"
        return {
            "id": "test_unlocked_control_run_succeeds",
            "result": "PASS" if passed else "FAIL",
            "update_ok": bool(result.get("ok")),
            "update_classify": cls,
            "rollback_ok": bool(rollback.get("ok")),
            "rollback_classify": cls_rb,
            "both_states": {
                "locked_refuses": True,
                "unlocked_succeeds": bool(result.get("ok")) and bool(rollback.get("ok")),
            },
        }


def detector_control_naive_update_mixes() -> dict[str, Any]:
    """Negative control: naive sequential replace MUST go red (mixed tree)."""
    with _tmp() as tmp:
        root = _tree(tmp)
        pre = seed(root, V1)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "hook")
        result = naive_replace(fs, root, V2)
        cls = classify_tree(root)
        post = inventory(root)
        diff = compare(pre, post)
        mixed = cls == "mixed"
        wrote_unlocked = "plugin.json" in (result.get("wrote") or [])
        stopped = not result.get("ok")
        fired = mixed and wrote_unlocked and stopped
        return {
            "id": "control_naive_update_mixes_when_hook_held",
            "fired_on_bad_state": fired,
            "classify": cls,
            "wrote": result.get("wrote"),
            "ok": result.get("ok"),
            "locker": {"pid": locker.pid, "name": locker.name},
            "content_differ": diff["content_differ"],
            "inventory_post": post,
            "error": result.get("error"),
        }


def detector_control_naive_uninstall_partial() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        seed(root, V1)
        fs = WinLockFS()
        hold_kind(fs, root, "hook")
        result = naive_uninstall(fs, root)
        remaining = [
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        ]
        partial = (not result.get("ok")) and bool(result.get("removed")) and bool(remaining)
        return {
            "id": "control_naive_uninstall_partial_when_hook_held",
            "fired_on_bad_state": partial,
            "removed": result.get("removed"),
            "remaining": remaining,
        }


def rename_then_write_completes() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        seed(root, V1)
        fs = WinLockFS()
        hold_kind(fs, root, "hook")
        result = rename_then_write_update(fs, root)
        cls = classify_tree(root)
        passed = bool(result.get("ok")) and cls == "updated"
        return {
            "id": "rename_then_write_update_completes_with_pending_reboot",
            "result": "PASS" if passed else "FAIL",
            "classify": cls,
            "pending_reboot": result.get("pending_reboot"),
            "ok": result.get("ok"),
            "error": result.get("error"),
        }


def uninstall_refuses_when_module_held() -> dict[str, Any]:
    with _tmp() as tmp:
        root = _tree(tmp)
        pre = seed(root, V1)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "module")
        result = locked_aware(fs, root, "uninstall")
        post = inventory(root)
        unchanged = compare(pre, post)["identical"]
        passed = bool(result.get("refused")) and unchanged
        return {
            "id": "uninstall_refuses_when_module_held",
            "result": "PASS" if passed else "FAIL",
            "tree_unchanged": unchanged,
            "error": result.get("error"),
            "locker": {"pid": locker.pid, "name": locker.name},
        }


REQUIRED = (
    test_update_with_held_handle_is_atomic_or_loudly_refused,
    test_rollback_with_held_handle_leaves_no_partial_tree,
    test_error_names_the_locking_process_id,
    test_unlocked_control_run_succeeds,
)


def run_suite() -> dict[str, Any]:
    tests = [fn() for fn in REQUIRED]
    naive = detector_control_naive_update_mixes()
    naive_un = detector_control_naive_uninstall_partial()
    rename = rename_then_write_completes()
    uninstall = uninstall_refuses_when_module_held()
    all_pass = (
        all(t["result"] == "PASS" for t in tests)
        and naive["fired_on_bad_state"]
        and naive_un["fired_on_bad_state"]
        and rename["result"] == "PASS"
        and uninstall["result"] == "PASS"
    )
    return {
        "all_pass": all_pass,
        "tests": tests,
        "naive_update_control": naive,
        "naive_uninstall_control": naive_un,
        "rename_then_write": rename,
        "uninstall_held_module": uninstall,
        "half_updated_step": (
            "naive in-place sequential replace during update: unlocked "
            "plugin.json / skills / rules become 2.0.0, then the held "
            "hooks/on_load.py raises WinError 32 and stays 1.0.0 — mixed "
            "tree, which is a P0 even if the command later exits non-zero. "
            "The same sequential unlink during uninstall half-removes the "
            "tree. Locked-aware update/rollback/uninstall preflight and "
            "refuse, naming pid= and the locking process, leaving the "
            "inventory byte-identical."
        ),
        "held_kinds_exercised": ["hook", "log", "module"],
    }
