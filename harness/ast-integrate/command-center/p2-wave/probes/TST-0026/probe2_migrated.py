#!/usr/bin/env python3
"""Probe 2: a migrated change with a schema_version bump is accepted.

Catalog test: test_migrated_change_with_version_bump_is_accepted.

Negative controls (must stay red):
  * version bump without a matching migration entry
  * migration entry without a version bump
  * migration whose from_sha256 does not match the freeze hash
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
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
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
        return f"receipt frozen_set.hash {recorded} != live {live['freeze_set_hash']}"
    checks = {c.get("id"): c.get("verdict") for c in (doc.get("checks") or []) if isinstance(c, dict)}
    if checks.get("test_migrated_change_with_version_bump_is_accepted") != "PASS":
        return (
            "receipt check migrated="
            f"{checks.get('test_migrated_change_with_version_bump_is_accepted')}"
        )
    evidence = doc.get("evidence") or {}
    if not (evidence.get("unmigrated_rejected") and evidence.get("migrated_accepted")):
        return "receipt evidence missing both-states demonstration"
    return None


def freeze_sha(freeze: dict, rel: str) -> str:
    for row in freeze["files"]:
        if row["path"] == rel:
            return str(row["sha256"])
    raise KeyError(rel)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tst0026-p2-"))
    try:
        tree = copy_tree(tmp / "tree")
        freeze = G.snapshot_paths(tree, G.FIXTURE_FROZEN)
        before = freeze_sha(freeze, TARGET)
        target = tree / TARGET

        # --- bump only, no migration ---
        G.mutate_json_add_property(target, "x_migrated")
        G.bump_json_schema_version(target, 2)
        bumped_sha = G.digest_file(target)[0]
        if bumped_sha == before:
            return fail("bump+edit did not change hash")
        bump_only = G.evaluate(freeze, tree, [])
        if bump_only["ok"]:
            return fail("version bump without migration was accepted")
        bump_reasons = [r.get("reason") for r in bump_only["rejections"]]
        if "version-bump-without-migration" not in bump_reasons:
            return fail(f"bump-only reasons {bump_reasons}")

        # --- migration without bump (restore version 1, keep extra property) ---
        G.bump_json_schema_version(target, 1)
        no_bump_sha = G.digest_file(target)[0]
        if G.extract_schema_version(target)[0] != 1:
            return fail("failed to restore schema_version=1")
        fake_mig = [
            {
                "id": "mig-no-bump",
                "path": TARGET,
                "from_sha256": before,
                "to_sha256": no_bump_sha,
                "from_schema_version": 1,
                "to_schema_version": 1,
            }
        ]
        mig_only = G.evaluate(freeze, tree, fake_mig)
        if mig_only["ok"]:
            return fail("migration without version bump was accepted")
        mig_reasons = [r.get("reason") for r in mig_only["rejections"]]
        if "migration-without-version-bump" not in mig_reasons:
            return fail(f"mig-only reasons {mig_reasons}")

        # --- wrong from_sha ---
        G.bump_json_schema_version(target, 2)
        good_sha = G.digest_file(target)[0]
        wrong_from = [
            {
                "id": "mig-wrong-from",
                "path": TARGET,
                "from_sha256": "0" * 64,
                "to_sha256": good_sha,
                "from_schema_version": 1,
                "to_schema_version": 2,
            }
        ]
        wrong = G.evaluate(freeze, tree, wrong_from)
        if wrong["ok"]:
            return fail("migration with wrong from_sha256 was accepted")

        # --- honest migrated path: bump + matching migration ---
        good = [
            {
                "id": "mig-unit-v1-v2",
                "path": TARGET,
                "from_sha256": before,
                "to_sha256": good_sha,
                "from_schema_version": 1,
                "to_schema_version": 2,
            }
        ]
        accepted = G.evaluate(freeze, tree, good)
        if not accepted["ok"]:
            return fail(f"migrated+bumped edit was rejected {accepted['rejections']}")
        if not accepted["accepted"]:
            return fail("accepted list empty")
        if accepted["accepted"][0]["path"] != TARGET:
            return fail(f"accepted path {accepted['accepted'][0]['path']}")
        if accepted["accepted"][0]["live_schema_version"] != 2:
            return fail("accepted live version is not 2")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    err = check_receipt()
    if err:
        return fail(err)

    print(
        json.dumps(
            {
                "probe": "probe2-migrated-accept",
                "unit_id": UNIT,
                "target": TARGET,
                "bump_without_migration_rejected": True,
                "migration_without_bump_rejected": True,
                "wrong_from_sha_rejected": True,
                "migrated_with_bump_accepted": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0026-probe2 migrated change with version bump is accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
