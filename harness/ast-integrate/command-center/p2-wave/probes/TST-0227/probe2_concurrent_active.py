#!/usr/bin/env python3
"""Probe 2: concurrent live victim session plus reviewer bypasses.

Catalog concurrency: run the cross-session write while a second session is
genuinely active (live pid under /proc, heartbeat file). Reviewer bypasses:
relative traversal and a symlink hop into the victim worktree. Both must
deny with an alert naming both session ids; victim tree hash unchanged.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from lib.workspace import (  # noqa: E402
    Codes,
    SessionBroker,
    SessionDenied,
    independent_tree_hash,
    oob_path_exists,
    oob_pid_alive,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0227-probe2 {msg}")
    return 1


def _cross(broker: SessionBroker, actor: str, dest: Path) -> SessionDenied | None:
    try:
        broker.write_file(actor, dest, b"PROBE2-MUST-NOT-LAND")
        return None
    except SessionDenied as exc:
        return exc


def main() -> int:
    report: dict = {
        "probe": "probe2-concurrent-active",
        "unit_id": "TST-0227",
        "reviewer_id": "TST-0227-probe2-concurrent-review",
    }
    with tempfile.TemporaryDirectory(prefix="tst0227-p2-") as td:
        base = Path(td)
        broker = SessionBroker()
        actor = broker.register(
            "sess-A",
            worktree_root=base / "A" / "worktree",
            artifact_root=base / "A" / "artifacts",
            runtime_dir=base / "A" / "runtime",
        )
        victim = broker.register(
            "sess-B",
            worktree_root=base / "B" / "worktree",
            artifact_root=base / "B" / "artifacts",
            runtime_dir=base / "B" / "runtime",
        )
        (victim.worktree_root / "canary.txt").write_bytes(b"victim-canary-v1")
        (victim.artifact_root / "keep.json").write_bytes(b'{"keep":true}')

        rec = broker.start_heartbeat("sess-B")
        alive_before = broker.session_is_alive("sess-B") and oob_pid_alive(rec.pid)
        if not alive_before:
            broker.stop_all()
            return fail(f"victim session not genuinely active pid={rec.pid}")

        pre_wt = independent_tree_hash(victim.worktree_root)
        pre_ar = independent_tree_hash(victim.artifact_root)

        dest = victim.worktree_root / "cross-session-write.txt"
        denied = _cross(broker, "sess-A", dest)
        alive_during = broker.session_is_alive("sess-B")
        if denied is None:
            broker.stop_all()
            return fail("cross-session write succeeded while victim was alive")
        if denied.code != Codes.CROSS_SESSION_WRITE or denied.alert is None:
            broker.stop_all()
            return fail(f"missing cross-session alert code={denied.code}")
        if not denied.alert.names_both():
            broker.stop_all()
            return fail("alert did not name both session ids")
        if oob_path_exists(dest):
            broker.stop_all()
            return fail("payload leaked into live victim worktree")
        post_wt = independent_tree_hash(victim.worktree_root)
        report["concurrency"] = {
            "victim_pid": rec.pid,
            "alive_before": alive_before,
            "alive_during_attempt": alive_during,
            "denied": True,
            "code": denied.code,
            "alert": denied.alert.as_dict(),
            "oob_file_exists": False,
            "pre_worktree_sha256": pre_wt,
            "post_worktree_sha256": post_wt,
            "worktree_unchanged": pre_wt == post_wt,
            "heartbeat_path_outside_hashed_tree": not str(victim.heartbeat_path).startswith(
                str(victim.worktree_root)
            ),
        }
        if pre_wt != post_wt:
            broker.stop_all()
            return fail("victim worktree hash changed during concurrent deny")
        if not alive_during:
            broker.stop_all()
            return fail("victim session died during the probe")

        trav = actor.worktree_root / ".." / ".." / "B" / "worktree" / "via-trav.txt"
        trav_exc = _cross(broker, "sess-A", trav)
        trav_leaked = oob_path_exists(victim.worktree_root / "via-trav.txt")
        report["bypass_relative_traversal"] = {
            "refused": trav_exc is not None,
            "code": getattr(trav_exc, "code", None),
            "alert_names_both": bool(trav_exc and trav_exc.alert and trav_exc.alert.names_both()),
            "oob_leaked": trav_leaked,
        }
        if trav_exc is None or trav_exc.code != Codes.CROSS_SESSION_WRITE or trav_leaked:
            broker.stop_all()
            return fail("relative traversal into victim was not contained")

        hop = actor.worktree_root / "hop-to-victim"
        os.symlink(victim.worktree_root, hop)
        link_exc = _cross(broker, "sess-A", hop / "via-link.txt")
        link_leaked = oob_path_exists(victim.worktree_root / "via-link.txt")
        report["bypass_symlink"] = {
            "refused": link_exc is not None,
            "code": getattr(link_exc, "code", None),
            "alert_names_both": bool(link_exc and link_exc.alert and link_exc.alert.names_both()),
            "oob_leaked": link_leaked,
        }
        if link_exc is None or link_exc.code != Codes.CROSS_SESSION_WRITE or link_leaked:
            broker.stop_all()
            return fail("symlink hop into victim was not contained")

        if independent_tree_hash(victim.worktree_root) != pre_wt:
            broker.stop_all()
            return fail("victim hash changed after reviewer bypasses")
        if independent_tree_hash(victim.artifact_root) != pre_ar:
            broker.stop_all()
            return fail("victim artifact hash changed")

        still_alive = broker.session_is_alive("sess-B")
        report["concurrency"]["alive_after"] = still_alive
        broker.stop_all()
        dead_after_stop = not oob_pid_alive(rec.pid)
        report["concurrency"]["dead_after_stop"] = dead_after_stop
        if not still_alive:
            return fail("victim session was not alive through reviewer bypasses")
        if not dead_after_stop:
            return fail("heartbeat pid still alive after stop")

        report["pass"] = True
        print(json.dumps(report, sort_keys=True))
        print(
            f"victim_pid={rec.pid} alive_during=True deny=True "
            "traversal=True symlink=True hash_unchanged=True"
        )
        print("SUCCESS:TST-0227-probe2 concurrent live victim plus reviewer bypasses")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
