#!/usr/bin/env python3
"""Probe 1: both-states own-write vs cross-session deny + victim tree hash.

Signal (a): denial plus an alert naming both session ids.
Signal (b): independent pre/post sha256 of the victim session tree.
Both-states: a write inside the actor's OWN session root succeeds in the
same run. Mutation control: an unmediated write would change the hash.
"""
from __future__ import annotations

import json
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
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0227-probe1 {msg}")
    return 1


def main() -> int:
    report: dict = {"probe": "probe1-both-states", "unit_id": "TST-0227"}
    with tempfile.TemporaryDirectory(prefix="tst0227-p1-") as td:
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
        canary = victim.worktree_root / "canary.txt"
        canary.write_bytes(b"victim-canary-v1")
        (victim.artifact_root / "keep.json").write_bytes(b'{"keep":true}')

        pre_wt = independent_tree_hash(victim.worktree_root)
        pre_ar = independent_tree_hash(victim.artifact_root)
        broker_pre = broker.tree_hash("sess-B")
        if broker_pre["worktree"] != pre_wt or broker_pre["artifact"] != pre_ar:
            return fail("broker tree_hash disagrees with independent hash")

        own = actor.worktree_root / "own-write.txt"
        broker.write_file("sess-A", own, b"OWN-SESSION-OK")
        own_ok = own.read_bytes() == b"OWN-SESSION-OK"
        own_art = actor.artifact_root / "own-art.txt"
        broker.write_file("sess-A", own_art, b"OWN-ARTIFACT-OK")
        report["own_session_write"] = {
            "worktree_ok": own_ok,
            "artifact_ok": own_art.read_bytes() == b"OWN-ARTIFACT-OK",
            "path": str(own),
        }
        if not own_ok:
            return fail("own-session worktree write did not land")

        dest = victim.worktree_root / "cross-session-write.txt"
        try:
            broker.write_file("sess-A", dest, b"MUST-NOT-LAND")
            denied = None
        except SessionDenied as exc:
            denied = exc
        if denied is None:
            return fail("cross-session worktree write was not denied")
        if denied.code != Codes.CROSS_SESSION_WRITE:
            return fail(f"expected {Codes.CROSS_SESSION_WRITE} got {denied.code}")
        if denied.alert is None or not denied.alert.names_both():
            return fail("alert did not name both session ids")
        if denied.actor_session_id != "sess-A" or denied.victim_session_id != "sess-B":
            return fail("denial did not carry both session ids")
        leaked = oob_path_exists(dest)
        post_wt = independent_tree_hash(victim.worktree_root)
        post_ar = independent_tree_hash(victim.artifact_root)
        report["cross_session_write"] = {
            "denied": True,
            "code": denied.code,
            "alert": denied.alert.as_dict(),
            "oob_file_exists": leaked,
            "pre_worktree_sha256": pre_wt,
            "post_worktree_sha256": post_wt,
            "pre_artifact_sha256": pre_ar,
            "post_artifact_sha256": post_ar,
            "worktree_unchanged": pre_wt == post_wt,
            "artifact_unchanged": pre_ar == post_ar,
        }
        if leaked:
            return fail("cross-session payload exists on disk (OOB)")
        if pre_wt != post_wt or pre_ar != post_ar:
            return fail("victim tree hash changed after denied write")

        # Mutation: the write attempt is real; only the gate stops it.
        control = victim.worktree_root / "unmediated-control.txt"
        control.write_bytes(b"UNMEDIATED")
        mutated = independent_tree_hash(victim.worktree_root)
        control_existed = control.is_file() and mutated != pre_wt
        control.unlink()
        restored = independent_tree_hash(victim.worktree_root)
        report["mutation_unmediated_write"] = {
            "created": control_existed,
            "hash_changed": mutated != pre_wt,
            "restored": restored == pre_wt,
        }
        if not control_existed or restored != pre_wt:
            return fail("unmediated mutation control failed")

        dest_art = victim.artifact_root / "stolen.json"
        try:
            broker.write_file("sess-A", dest_art, b"nope")
            art_denied = None
        except SessionDenied as exc:
            art_denied = exc
        if art_denied is None or art_denied.code != Codes.CROSS_SESSION_WRITE:
            return fail("cross-session artifact write was not denied")
        if oob_path_exists(dest_art):
            return fail("artifact payload leaked")
        if independent_tree_hash(victim.artifact_root) != pre_ar:
            return fail("victim artifact hash changed")

        report["pass"] = True
        print(json.dumps(report, sort_keys=True))
        print(
            "own=True deny=True alert_names_both=True "
            f"wt_unchanged={pre_wt == post_wt} unmediated_mutates=True"
        )
        print("SUCCESS:TST-0227-probe1 both-states own-write vs cross-session deny")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
