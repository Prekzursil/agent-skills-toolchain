#!/usr/bin/env python3
"""Probe 2: supersession edges read back; delete refused; deferred items have triggers."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import resume as R  # noqa: E402
import schema_local as S  # noqa: E402
from store import DeleteForbidden, NoteStore, StoreError, atomic_write, run_self_check  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0048.handoff-package.json"
VAULT = REPO / "command-center/memory/vault"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0048-probe2 {msg}")
    return 1


def main() -> int:
    isolated = run_self_check()
    if not isolated.get("delete_refused") or not isolated.get("resolve_control_fired"):
        return fail(f"isolated store battery {isolated}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errors = S.error_list(doc)
    if errors:
        return fail(f"schema {errors[0]}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    garbage = {"unit_id": "SYN-0048", "state": "SUCCESS"}
    g_err = S.error_list(garbage)
    if not g_err:
        return fail("schema accepted a nearly-empty document")

    missing_trigger = json.loads(json.dumps(doc))
    planted_deferred = [{"id": "D-BAD", "reason": "deferred without a reopen trigger field"}]
    missing_trigger["deferred_items"] = planted_deferred
    if isinstance(missing_trigger.get("report"), dict):
        missing_trigger["report"]["deferred_items"] = planted_deferred
    t_err = S.error_list(missing_trigger)
    if not t_err:
        return fail("schema accepted deferred item without reopen_trigger")

    store = NoteStore(VAULT)
    live_edges = store.audit_edges()
    body = R.payload(doc)
    pkg_edges = body.get("supersession_edges") or doc.get("supersession_edges") or []
    if len(pkg_edges) < 1:
        return fail("package has no supersession_edges")
    live_pairs = {(e["old_id"], e["new_id"]) for e in live_edges}
    pkg_pairs = {(e["old_id"], e["new_id"]) for e in pkg_edges}
    if pkg_pairs != live_pairs:
        return fail(f"edge mismatch pkg={sorted(pkg_pairs)} live={sorted(live_pairs)}")
    for edge in live_edges:
        if edge.get("read_back") is not True:
            return fail(f"live edge not read_back {edge}")
        old = store.read(edge["old_id"])
        new = store.read(edge["new_id"])
        if old.get("superseded_by") != edge["new_id"]:
            return fail("old superseded_by mismatch on live read-back")
        if not new.get("valid_as_of"):
            return fail("successor missing valid_as_of on live read-back")
        if not store.path_for(edge["old_id"]).is_file():
            return fail("superseded note was deleted")

    try:
        store.delete(live_edges[0]["old_id"])
        return fail("live delete() did not refuse")
    except DeleteForbidden:
        pass
    if not store.path_for(live_edges[0]["old_id"]).is_file():
        return fail("live delete attempt removed a note")

    for item in body.get("deferred_items") or doc.get("deferred_items") or []:
        trig = item.get("reopen_trigger")
        if not isinstance(trig, dict) or not trig.get("predicate"):
            return fail(f"deferred {item.get('id')} missing reopen_trigger")

    tmp = Path(tempfile.mkdtemp(prefix="syn0048-cycle-"))
    cyc = NoteStore(tmp)
    cyc.write_new({"permalink": "a", "title": "A", "body": "a"})
    cyc.write_new({"permalink": "b", "title": "B", "body": "b"})
    a = cyc.read("a")
    b = cyc.read("b")
    a["superseded_by"] = "b"
    b["superseded_by"] = "a"
    b["valid_as_of"] = "2099-01-01T00:00:00+00:00"
    atomic_write(cyc.path_for("a"), a)
    atomic_write(cyc.path_for("b"), b)
    cycle_fired = False
    try:
        cyc.audit_edges()
    except StoreError as exc:
        cycle_fired = "ACYCLIC" in str(exc) or "cycle" in str(exc).lower()
    if not cycle_fired:
        return fail("planted cycle did not fire")

    print(
        json.dumps(
            {
                "deferred_n": len(body.get("deferred_items") or doc.get("deferred_items") or []),
                "delete_refused": True,
                "garbage_schema_errors": len(g_err),
                "live_edges": sorted(live_pairs),
                "missing_trigger_schema_errors": len(t_err),
                "planted_cycle_fired": True,
                "resolve_control_fired": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0048-probe2 supersession read-back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
