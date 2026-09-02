#!/usr/bin/env python3
"""Named probe 2: error names the locking pid; unlocked control succeeds.

Both-states pair: same update command refuses when a module handle is held
and completes when the handle is released.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import classify_tree, compare, inventory  # noqa: E402
from lifecycle import locked_aware  # noqa: E402
from measure import (  # noqa: E402
    test_error_names_the_locking_process_id,
    test_unlocked_control_run_succeeds,
    uninstall_refuses_when_module_held,
)
from scenario import V1, V2, hold_kind, seed  # noqa: E402
from winlock import WinLockFS  # noqa: E402

ART = REPO / "command-center/receipts/TST-0061.json"
SENTINEL = "SUCCESS:TST-0061"


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    uid = doc.get("unit_id") or doc.get("id")
    if uid != "TST-0061":
        return f"unit_id {uid}"
    if SENTINEL not in text:
        return "sentinel absent"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    return None


def both_states_update() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0061-both-") as tmp:
        root = Path(tmp) / "install"
        pre = seed(root, V1)
        fs = WinLockFS()
        locker = hold_kind(fs, root, "module")
        locked = locked_aware(fs, root, "update", new_version=V2)
        after_lock = inventory(root)
        locked_unchanged = compare(pre, after_lock)["identical"]
        fs.release(root / "lib/runtime.py")
        unlocked = locked_aware(fs, root, "update", new_version=V2)
        cls = classify_tree(root)
        ok = (
            bool(locked.get("refused"))
            and locked_unchanged
            and locker.pid in (locked.get("named_pids") or [])
            and bool(unlocked.get("ok"))
            and cls == "updated"
        )
        return {
            "ok": ok,
            "locked_refused": bool(locked.get("refused")),
            "locked_tree_unchanged": locked_unchanged,
            "unlocked_ok": bool(unlocked.get("ok")),
            "unlocked_classify": cls,
            "pid": locker.pid,
            "error": locked.get("error"),
        }


def main() -> int:
    err = _check_receipt()
    if err:
        print(f"FAILED:TST-0061-probe2 {err}")
        return 1

    named = test_error_names_the_locking_process_id()
    unlocked = test_unlocked_control_run_succeeds()
    uninstall = uninstall_refuses_when_module_held()
    pair = both_states_update()

    if named["result"] != "PASS":
        print("FAILED:TST-0061-probe2 error did not name pid")
        print(json.dumps(named, indent=2, default=str)[:4000])
        return 1
    if unlocked["result"] != "PASS":
        print("FAILED:TST-0061-probe2 unlocked control")
        print(json.dumps(unlocked, indent=2, default=str)[:4000])
        return 1
    if uninstall["result"] != "PASS":
        print("FAILED:TST-0061-probe2 uninstall held module")
        print(json.dumps(uninstall, indent=2, default=str)[:4000])
        return 1
    if not pair.get("ok"):
        print("FAILED:TST-0061-probe2 both-states pair")
        print(json.dumps(pair, indent=2, default=str)[:4000])
        return 1

    summary = {
        "probe": "probe2-pid-unlocked",
        "unit_id": "TST-0061",
        "pass": True,
        "error_names_pid": True,
        "pid_token": named["pid_token"],
        "unlocked_control_succeeds": True,
        "uninstall_refuses_held_module": True,
        "both_states": pair,
        "held_kind": "module",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:TST-0061-probe2 error names pid=; unlocked control succeeds; "
        "both-states pair discriminated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
