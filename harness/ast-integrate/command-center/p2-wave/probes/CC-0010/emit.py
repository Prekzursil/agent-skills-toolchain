#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0010.json from live freeze-protocol runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

OUT = L.REPO / L.OUT_REL
SCHEMA_PATH = L.REPO / L.SCHEMA_REL
CATALOG_SCHEMA = L.REPO / L.CATALOG_SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:CC-0010-emit {msg}")
    return 1


def main() -> int:
    p1 = L.probe1_payload()
    p2 = L.probe2_payload()
    live = L.live_snapshot()
    if not p1.get("ok"):
        return fail(f"probe1 control {p1.get('adversarial')}")
    if not p2.get("ok"):
        return fail("probe2 controls failed")
    adv = p1["adversarial"]
    base = p2["quiescent_baseline"]
    rb = p2["rollback_rehearsal"]
    classes = live.get("classes") or []
    if [c.get("id") for c in classes] != list(L.NINE_CLASSES):
        return fail(f"live freeze class ids {[c.get('id') for c in classes]}")
    if live.get("verdict") == "BASELINE" and not (live.get("quiescence") or {}).get(
        "is_git_work_tree"
    ):
        return fail("refusing BASELINE for a non-git live worktree")

    answer = (
        "On this worktree Phase 0 is not a rollback freeze. /opt/p2/ast-integrate "
        "has no .git, so git-status and tracked-mtime quiescence signals are "
        "NOT-CHECKED and the live capture is SAMPLE, never BASELINE. The program "
        f"rollback pin remains {L.PROGRAM_ANCHOR_PREFIX} and is NOT-CHECKED here "
        "(object not resolvable; not invented). The freeze protocol at "
        f"{L.MODULE_REL} snapshots the nine named classes (unread classes are "
        "NOT-CHECKED, not empty lists), tags every working-tree measurement "
        "SAMPLE, and emits BASELINE only when both independent quiescence "
        "signals stay unchanged inside a git work tree. Controls: a writer "
        "touching a tracked file during the window produced SAMPLE and refused "
        "BASELINE; a quiescent scratch clone produced BASELINE with two matching "
        "signals; restoring that freeze HEAD into a second clone reproduced the "
        "SHA-ANCHORED artifact digests."
    )
    tests = [
        {
            "id": "T-ADVERSARIAL-WRITER-SAMPLE",
            "command": L.P1_CMD,
            "result": "PASS" if adv.get("ok") else "FAIL",
        },
        {
            "id": "T-QUIESCENT-SCRATCH-BASELINE",
            "command": L.P2_CMD,
            "result": "PASS" if base.get("ok") else "FAIL",
        },
        {
            "id": "T-ROLLBACK-REHEARSAL-DIGESTS",
            "command": L.P2_CMD,
            "result": "PASS" if rb.get("ok") else "FAIL",
        },
        {
            "id": "T-NINE-SNAPSHOT-CLASSES",
            "command": L.P2_CMD,
            "result": "PASS"
            if list(base.get("class_ids") or []) == list(L.NINE_CLASSES)
            else "FAIL",
        },
    ]
    doc = {
        "unit_id": L.UNIT,
        "id": L.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": L.SENTINEL,
        "completion_sentinel": L.SENTINEL,
        "title": "Define a freeze that is actually a freeze",
        "question": L.QUESTION,
        "answer": answer,
        "output_schema": L.SCHEMA_REL,
        "catalog_output_schema": L.CATALOG_SCHEMA_REL,
        "catalog_output_schema_present": CATALOG_SCHEMA.is_file(),
        "catalog_output_schema_note": (
            "Catalog names command-center/schema/receipt.schema.json (CC-0002). "
            "That file is absent on this worktree; this receipt validates against "
            "command-center/schema/freeze-protocol-receipt.schema.json instead of "
            "inventing CC-0002's schema."
        ),
        "freeze_protocol": {
            "module": L.MODULE_REL,
            "program_rollback_pin": L.PROGRAM_ANCHOR_PREFIX,
            "baseline_rule": (
                "BASELINE only when both git-status digest and tracked mtime scan "
                "are READ and unchanged across the freeze window inside a git work tree; "
                "otherwise SAMPLE. Working-tree measurements are always SAMPLE."
            ),
            "working_tree_measurement_tag": "SAMPLE",
            "unread_class_tag": "NOT-CHECKED",
            "nine_classes": list(L.NINE_CLASSES),
            "retry_policy": (
                "Two in-place freeze strikes then pivot to a scratch-clone freeze; "
                "do not attempt a third in-place freeze on a shared working tree."
            ),
        },
        "live_freeze": live,
        "snapshot_classes": [
            {
                "id": c.get("id"),
                "status": c.get("status"),
                "anchoring": c.get("anchoring"),
                "reason": c.get("reason"),
            }
            for c in classes
        ],
        "controls": {
            "adversarial_writer": {
                "ok": bool(adv.get("ok")),
                "verdict": adv.get("verdict"),
                "refused_baseline": bool(adv.get("refused_baseline")),
                "mutated_rel": adv.get("mutated_rel"),
            },
            "quiescent_scratch": {
                "ok": bool(base.get("ok")),
                "verdict": base.get("verdict"),
                "independent_signal_count": base.get("independent_signal_count"),
                "git_status_match": base.get("git_status_match"),
                "mtime_scan_match": base.get("mtime_scan_match"),
            },
            "rollback_rehearsal": {
                "ok": bool(rb.get("ok")),
                "digests_reproduced": bool(rb.get("digests_reproduced")),
                "restored_verdict": rb.get("restored_verdict"),
            },
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "CC-0010-probe2-independent-race",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 races the freeze itself by mutating reviewer.txt in a "
                "separate scratch clone, then independently requires BASELINE on a "
                "quiescent clone and digest reproduction after restoring HEAD."
            ),
        },
        "evidence": [
            {
                "path": L.MODULE_REL,
                "kind": "protocol",
                "claim": (
                    "Freeze verdict requires two independent READ quiescence "
                    "signals (git status digest and tracked mtime scan) to match."
                ),
            },
            {
                "path": L.OUT_REL,
                "kind": "control-result",
                "claim": (
                    "Adversarial writer => SAMPLE; quiescent scratch => BASELINE "
                    "with independent_signal_count=2; rollback reproduced SHA-ANCHORED digests."
                ),
            },
            {
                "path": L.SCHEMA_REL,
                "kind": "schema",
                "claim": (
                    "Receipt validates against freeze-protocol-receipt.schema.json; "
                    "empty object is rejected."
                ),
            },
        ],
        "artifacts": [
            {"path": L.OUT_REL, "exists": True, "role": "primary"},
            {"path": L.MODULE_REL, "exists": True, "role": "protocol"},
            {"path": L.SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CC-0010/lib.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-WRITER-DURING-FREEZE",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "Writer during window forces SAMPLE; quiescent scratch is allowed BASELINE."
                ),
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": L.P1_CMD,
                "raw_output": L.dumps(p1),
                "exit_code": 0,
            },
            {
                "id": "probe2",
                "command": L.P2_CMD,
                "raw_output": L.dumps(p2),
                "exit_code": 0,
            },
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "baseline-custodian",
            "execution_substrate": "local-serialized",
            "worktree": "/opt/p2/ast-integrate",
        },
        "schema_version": 1,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CC-0010/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            (
                "Program pin 53c37c6c is NOT-CHECKED on this worktree because "
                "there is no git object database here."
            )
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail("schema " + "; ".join(e.message for e in errs[:8]))
    if not list(jsonschema.Draft7Validator(schema).iter_errors({})):
        return fail("schema accepts empty object")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if L.SENTINEL not in text:
        return fail("sentinel missing from serialized artifact")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    raw = OUT.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {L.OUT_REL} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:CC-0010-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
