#!/usr/bin/env python3
"""TST-0227 probe 1: both-states control for cross-session write containment.

Deny   : a brokered write from one session into ANOTHER session's worktree is
         denied with SESS_CROSS_SESSION_WRITE and the alert names BOTH session
         ids; the victim tree hash is unchanged after the denial.
Control: a write inside the actor's OWN session root succeeds in the same run.
Vacuity: an UNMEDIATED write to the same victim path DOES change the tree
         hash, proving the denied-write test is not passing because the target
         is unwritable.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))

from workspace import Codes, SessionBroker, SessionDenied, independent_tree_hash  # noqa: E402

ROOTS = HERE / "fixtures" / "p1"


def main() -> int:
    if ROOTS.exists():
        shutil.rmtree(ROOTS)
    broker = SessionBroker()
    victim = broker.register(
        "sess-victim",
        worktree_root=ROOTS / "victim" / "wt",
        artifact_root=ROOTS / "victim" / "art",
        runtime_dir=ROOTS / "victim" / "run",
    )
    actor = broker.register(
        "sess-actor",
        worktree_root=ROOTS / "actor" / "wt",
        artifact_root=ROOTS / "actor" / "art",
        runtime_dir=ROOTS / "actor" / "run",
    )
    (victim.worktree_root / "existing.txt").write_bytes(b"victim baseline bytes\n")

    hash_before = independent_tree_hash(victim.worktree_root)

    denied = False
    code = None
    alert_names = {}
    try:
        broker.write_file("sess-actor", victim.worktree_root / "intrusion.txt", b"hostile payload")
    except SessionDenied as exc:
        denied = True
        code = exc.code
        alert_names = exc.alert.as_dict()

    hash_after_denial = independent_tree_hash(victim.worktree_root)

    own_ok = False
    try:
        broker.write_file("sess-actor", actor.artifact_root / "own.txt", b"own-session payload")
        own_ok = (actor.artifact_root / "own.txt").read_bytes() == b"own-session payload"
    except SessionDenied:
        own_ok = False

    unmediated = victim.worktree_root / "intrusion.txt"
    unmediated.write_bytes(b"hostile payload (unmediated)")
    hash_after_unmediated = independent_tree_hash(victim.worktree_root)

    checks = {
        "cross_session_write_denied": denied is True and code == Codes.CROSS_SESSION_WRITE,
        "alert_names_both_session_ids": alert_names.get("actor") == "sess-actor"
        and alert_names.get("victim") == "sess-victim"
        and alert_names.get("actor") != alert_names.get("victim"),
        "victim_tree_unchanged_after_denial": hash_after_denial == hash_before,
        "own_session_write_succeeds": own_ok is True,
        "unmediated_write_changes_hash": hash_after_unmediated != hash_before,
    }
    out = {
        "probe": "probe1_both_states",
        "unit": "TST-0227",
        "denial_code": code,
        "alert": alert_names,
        "hash_before": hash_before,
        "hash_after_denial": hash_after_denial,
        "hash_after_unmediated": hash_after_unmediated,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_both_states.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(ROOTS, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
