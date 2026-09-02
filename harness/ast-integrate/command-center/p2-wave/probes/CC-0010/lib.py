"""CC-0010 freeze-protocol helpers shared by emit and named probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.freeze.protocol import (  # noqa: E402
    NINE_CLASSES,
    PROGRAM_ANCHOR_PREFIX,
    freeze_live_worktree,
    run_adversarial_control,
    run_quiescent_baseline_control,
    run_rollback_rehearsal,
)

UNIT = "CC-0010"
OUT_REL = "command-center/receipts/CC-0010.json"
SCHEMA_REL = "command-center/schema/freeze-protocol-receipt.schema.json"
CATALOG_SCHEMA_REL = "command-center/schema/receipt.schema.json"
MODULE_REL = "tools/freeze/protocol.py"
SENTINEL = (
    "SUCCESS:CC-0010 emitted only when the freeze protocol exists, both named "
    "probes exit 0, and the receipt is not BLOCKED"
)
QUESTION = (
    "Question: what exactly is frozen at Phase 0? The baseline lane's snapshot "
    "ran while concurrent sibling agents mutated the tree, so every working-tree "
    "number in that snapshot is a timestamped sample and only SHA 53c37c6c is a "
    "valid rollback anchor. Implementation target: a freeze protocol that pins "
    "that SHA, snapshots the nine named classes, tags working-tree measurements "
    "SAMPLE, and refuses to emit BASELINE while the tree is being written."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0010/probe1_adversarial_writer.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0010/probe2_quiescent_and_rollback.py"
)


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def probe1_payload() -> dict[str, Any]:
    adv = run_adversarial_control(mutate_rel="tracked.txt")
    return {
        "probe": "probe1-adversarial-writer",
        "unit_id": UNIT,
        "adversarial": adv,
        "nine_classes": list(NINE_CLASSES),
        "program_pin": PROGRAM_ANCHOR_PREFIX,
        "ok": bool(adv.get("ok")) and adv.get("verdict") == "SAMPLE",
    }


def probe2_payload() -> dict[str, Any]:
    # Independent race: mutate a different tracked file than probe 1.
    race = run_adversarial_control(mutate_rel="reviewer.txt")
    baseline = run_quiescent_baseline_control()
    rollback = run_rollback_rehearsal()
    ok = (
        bool(race.get("ok"))
        and race.get("verdict") == "SAMPLE"
        and bool(baseline.get("ok"))
        and baseline.get("verdict") == "BASELINE"
        and bool(rollback.get("ok"))
        and rollback.get("digests_reproduced") is True
        and list(baseline.get("class_ids") or []) == list(NINE_CLASSES)
    )
    return {
        "probe": "probe2-reviewer-race-baseline-rollback",
        "unit_id": UNIT,
        "independent_race": race,
        "quiescent_baseline": {
            "ok": baseline.get("ok"),
            "verdict": baseline.get("verdict"),
            "classes_complete": baseline.get("classes_complete"),
            "class_ids": baseline.get("class_ids"),
            "class_status": baseline.get("class_status"),
            "git_status_match": baseline.get("git_status_match"),
            "mtime_scan_match": baseline.get("mtime_scan_match"),
            "independent_signal_count": baseline.get("independent_signal_count"),
            "working_tree_measurements": baseline.get("working_tree_measurements"),
            "program_anchor": baseline.get("program_anchor"),
        },
        "rollback_rehearsal": {
            "ok": rollback.get("ok"),
            "digests_reproduced": rollback.get("digests_reproduced"),
            "restored_verdict": rollback.get("restored_verdict"),
            "recorded_digest_keys": sorted((rollback.get("recorded_digests") or {}).keys()),
        },
        "nine_classes": list(NINE_CLASSES),
        "ok": ok,
    }


def live_snapshot() -> dict[str, Any]:
    return freeze_live_worktree(REPO)
