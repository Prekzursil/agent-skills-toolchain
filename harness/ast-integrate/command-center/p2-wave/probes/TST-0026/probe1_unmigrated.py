#!/usr/bin/env python3
"""Probe 1: an unmigrated schema edit is rejected.

Catalog test: test_unmigrated_schema_change_is_rejected.

Also proves the both-states controls the gate would otherwise fake:
  * identity (no edit) is green
  * a non-frozen file edit is silent
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
from scenario import copy_tree  # noqa: E402

UNIT = "TST-0026"
ART = REPO / "command-center/receipts/TST-0026.json"
TARGET = "schemas/unit.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_receipt(freeze_hash: str) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if doc.get("unit_id") != UNIT:
        return f"unit_id={doc.get('unit_id')}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:TST-0026" not in text:
        return "sentinel-absent"
    live = G.live_snapshot(REPO)
    recorded = str((doc.get("frozen_set") or {}).get("hash") or "")
    if recorded != live["freeze_set_hash"]:
        return (
            f"receipt frozen_set.hash {recorded} != live {live['freeze_set_hash']}"
        )
    if recorded != freeze_hash and freeze_hash == live["freeze_set_hash"]:
        pass
    if recorded != live["freeze_set_hash"]:
        return "receipt hash drifted from live inventory"
    checks = {c.get("id"): c.get("verdict") for c in (doc.get("checks") or []) if isinstance(c, dict)}
    if checks.get("test_unmigrated_schema_change_is_rejected") != "PASS":
        return f"receipt check unmigrated={checks.get('test_unmigrated_schema_change_is_rejected')}"
    return None


def main() -> int:
    live = G.live_snapshot(REPO)
    if live["file_count"] < 2:
        return fail(f"live freeze set too small: {live['file_count']}")
    identity = G.evaluate(live, REPO, [])
    if not identity["ok"]:
        return fail(f"live identity rejected {identity['rejections']}")

    tmp = Path(tempfile.mkdtemp(prefix="tst0026-p1-"))
    try:
        tree = copy_tree(tmp / "tree")
        freeze = G.snapshot_paths(tree, G.FIXTURE_FROZEN)
        if freeze["missing"]:
            return fail(f"fixture missing {freeze['missing']}")
        if freeze["file_count"] != len(G.FIXTURE_FROZEN):
            return fail(f"fixture count {freeze['file_count']}")

        clean = G.evaluate(freeze, tree, [])
        if not clean["ok"]:
            return fail(f"clean fixture rejected {clean['rejections']}")

        notes = tree / "not-frozen" / "notes.txt"
        notes.write_text(notes.read_text(encoding="utf-8") + "mutated\n", encoding="utf-8")
        silent = G.evaluate(freeze, tree, [])
        if not silent["ok"]:
            return fail(f"non-frozen edit tripped the gate {silent['rejections']}")

        G.mutate_json_add_property(tree / TARGET, "x_unmigrated")
        after = G.snapshot_paths(tree, [TARGET])["files"][0]
        if after["sha256"] == next(f["sha256"] for f in freeze["files"] if f["path"] == TARGET):
            return fail("mutation did not change the schema hash (vacuous reject)")
        if after["schema_version"] != 1:
            return fail(f"unmigrated edit bumped version to {after['schema_version']}")

        bad = G.evaluate(freeze, tree, [])
        if bad["ok"]:
            return fail("unmigrated schema edit was accepted")
        reasons = [r.get("reason") for r in bad["rejections"]]
        paths = [r.get("path") for r in bad["rejections"]]
        if TARGET not in paths:
            return fail(f"rejection did not name {TARGET}: {bad['rejections']}")
        if "unmigrated-no-version-bump" not in reasons:
            return fail(f"unexpected reasons {reasons}")
        if len(bad["rejections"]) != 1:
            return fail(f"extra rejections {bad['rejections']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    err = check_receipt(live["freeze_set_hash"])
    if err:
        return fail(err)

    print(
        json.dumps(
            {
                "probe": "probe1-unmigrated-reject",
                "unit_id": UNIT,
                "live_freeze_files": live["file_count"],
                "live_freeze_set_hash": live["freeze_set_hash"],
                "live_identity_ok": True,
                "nonfrozen_edit_silent": True,
                "unmigrated_rejected": True,
                "reject_reason": "unmigrated-no-version-bump",
                "target": TARGET,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0026-probe1 unmigrated schema change is rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
