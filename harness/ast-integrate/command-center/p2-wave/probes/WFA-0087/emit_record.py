#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0087-repair-batch-execution.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from candidates import CANDIDATES  # noqa: E402
from executor import run_campaign  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0087-repair-batch-execution.json"
SENTINEL = "SUCCESS:WFA-0087"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RepairRecord"
QUESTION = (
    "Implementation target: repair each of the 15 REPAIR candidates in its own "
    "disposable worktree so no two repairs share a git index, turning each "
    "unit's red intake test green without changing any behaviour the test "
    "does not cover."
)


def build_record(campaign: dict) -> dict:
    batch = campaign["batch"]
    controls = campaign["controls"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repairs = []
    for row in batch["rows"]:
        repairs.append(
            {
                "candidate_id": row["id"],
                "title": row["title"],
                "defect_class": row["defect_class"],
                "intake_red_exit": row["intake_red"]["exit_code"],
                "intake_green_exit": row["intake_green"]["exit_code"],
                "intake_red_tail": row["intake_red"]["output"],
                "intake_green_tail": row["intake_green"]["output"],
                "red_to_green": row["red_to_green"],
                "canary_held": row["canary_held"],
                "index_path": row["index_path"],
                "shard_path": row["shard_path"],
                "seed_head": row["seed_head"],
                "head_after_repair": row["head_after_repair"],
                "repair_committed": row["repair_committed"],
                "declared_scope": row["declared_scope"],
                "changed_paths": row["changed_paths"],
                "scope_ok": row["scope_ok"],
                "ok": row["ok"],
            }
        )
    ok = bool(campaign["ok"])
    return {
        "id": "WFA-0087",
        "unit_id": "WFA-0087",
        "record_type": "RepairRecord",
        "title": "Execute the 15 candidate repairs in isolated worktrees, one repair per shard",
        "question_or_target": QUESTION,
        "state": "SUCCESS" if ok else "FAILED",
        "status": "DELIVERED" if ok else "FAILED",
        "sentinel": SENTINEL if ok else "FAILED:WFA-0087",
        "completion_sentinel": SENTINEL,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "schema_pack_on_tree": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "ts": now,
        "cloud_ok": False,
        "source_honesty": {
            "windows_registry_path": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "08-WORKFLOW-CANDIDATE-REGISTRY.json"
            ),
            "windows_registry_on_this_linux_tree": False,
            "wfa0086_intake_path": "command-center/wfa/WFA-0086-repair-intake-baselines.json",
            "wfa0086_intake_present": (
                REPO / "command-center/wfa/WFA-0086-repair-intake-baselines.json"
            ).is_file(),
            "corpus": "fixture-REPAIR-class-n=15",
            "note": (
                "Candidate ids are fixture ids for the REPAIR class (catalog "
                "histogram REPAIR n=15). They are not harvested registry ids. "
                "The isolated-worktree protocol, red-to-green intake, scoped "
                "diff, no-repair-commit, and sibling-revert controls are live."
            ),
        },
        "candidate_count": 15,
        "fixture_ids": [c["id"] for c in CANDIDATES],
        "repairs": repairs,
        "isolation": {
            "indexes_unique": batch["indexes_unique"],
            "shared_index_detected": batch["shared_index_detected"],
            "index_paths": batch["index_paths"],
            "any_repair_commit": batch["any_repair_commit"],
            "seed_commit_is_fixture": True,
            "repair_does_not_git_add_or_commit": True,
        },
        "evidence": {
            "A_intake_red_to_green": {
                "all_red_to_green": batch["all_red_to_green"],
                "n": batch["n"],
            },
            "B_scoped_diff_independent_of_green": {
                "all_scoped": batch["all_scoped"],
                "note": (
                    "Scope is reviewed from git status porcelain on each shard "
                    "index, not inferred from the intake test going green."
                ),
            },
        },
        "controls": {
            "shared_index": controls["shared_index"],
            "scope_sibling": controls["scope_sibling"],
            "ok": controls["ok"],
        },
        "tests_required": [
            {
                "id": "own-worktree-unique-index",
                "result": "PASS" if batch["indexes_unique"] else "FAIL",
            },
            {
                "id": "shared-index-is-unit-failure",
                "result": "PASS" if controls["shared_index"]["ok"] else "FAIL",
            },
            {
                "id": "scoped-diff-no-repair-commit",
                "result": (
                    "PASS"
                    if batch["all_scoped"] and not batch["any_repair_commit"]
                    else "FAIL"
                ),
            },
            {
                "id": "sibling-red-reverted-and-reapproached",
                "result": "PASS" if controls["scope_sibling"]["ok"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0087-probe2-shared-index-and-scope",
            "independent": True,
            "verdict": "PASS" if controls["ok"] and batch["ok"] else "FAIL",
        },
        "ok": ok,
    }


def write_record(doc: dict | None = None) -> dict:
    campaign = run_campaign() if doc is None else None
    record = doc if doc is not None else build_record(campaign)
    if not record.get("ok"):
        raise SystemExit(
            "FAILED:WFA-0087 campaign not ok "
            f"batch={campaign and campaign['batch']['ok']} "
            f"controls={campaign and campaign['controls']['ok']}"
        )
    if SENTINEL not in json.dumps(record):
        raise SystemExit("FAILED:WFA-0087 sentinel missing from record")
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    return record


def main() -> int:
    record = write_record()
    print(f"wrote {OUT_REL} ok={record['ok']} n={record['candidate_count']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
