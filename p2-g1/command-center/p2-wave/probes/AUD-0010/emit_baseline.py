#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0010-repo-weight-baseline.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

OUT = "command-center/audit/AUD-0010-repo-weight-baseline.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
QUESTION = (
    "What does a fresh clone of each owner repo cost in objects, packed bytes, "
    "and wall-clock, and which individual objects or paths dominate that weight?"
)
SENTINEL = (
    "SUCCESS:AUD-0010 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def main() -> int:
    bundle = M.live_bundle()
    fixture = bundle["fixture"]
    owner = bundle["owner"]
    if not fixture["packed_repeat_ok"]:
        print("FAILED:AUD-0010 packed size did not repeat within 2 percent")
        return 1
    if not fixture["clone_repeat_ok"]:
        print("FAILED:AUD-0010 clone disk did not repeat within 2 percent")
        return 1
    if fixture["packed_equals_clone"] or not fixture["clone_exceeds_packed"]:
        print("FAILED:AUD-0010 packed size and clone disk did not diverge")
        return 1
    if fixture["dominant_path"] != M.DOMINATE_REL:
        print(f"FAILED:AUD-0010 dominant path {fixture['dominant_path']!r}")
        return 1
    if owner["git_present"]:
        print("FAILED:AUD-0010 unexpected .git on this worktree")
        return 1

    p1_raw = json.dumps(
        {
            "probe": "probe1-count-objects",
            "command": M.P1_CMD,
            "packed_bytes": fixture["packed_bytes"],
            "packed_run2_bytes": fixture["packed_run2"]["packed_bytes"],
            "within_2pct": True,
            "object_count": fixture["object_count"],
            "owner_git_present": False,
            "count_objects_raw": fixture["packed_run1"]["raw"],
        },
        indent=2,
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": "probe2-timed-clone",
            "command": M.P2_CMD,
            "clone_disk_bytes": fixture["clone_disk_bytes"],
            "clone_run2_bytes": fixture["clone_run2"]["clone_disk_bytes"],
            "clone_wall_ms": fixture["clone_wall_ms"],
            "packed_bytes": fixture["packed_bytes"],
            "packed_equals_clone": False,
            "clone_exceeds_packed": True,
            "dominant_path": fixture["dominant_path"],
            "dominant_blob_bytes": fixture["dominant_blob_bytes"],
            "falsified": "packed-size-as-clone-cost",
        },
        indent=2,
        sort_keys=True,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "AUD-0010",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0010",
        "completion_sentinel": SENTINEL,
        "kind": "audit-metric-baseline",
        "schema_version": 1,
        "title": "Repository object-size and history-weight baseline",
        "question": QUESTION,
        "produced_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "headline": {
            "packed_bytes": fixture["packed_bytes"],
            "clone_disk_bytes": fixture["clone_disk_bytes"],
            "clone_wall_ms": fixture["clone_wall_ms"],
            "packed_equals_clone": False,
            "object_count": fixture["object_count"],
            "dominant_path": fixture["dominant_path"],
            "dominant_blob_bytes": fixture["dominant_blob_bytes"],
            "owner_git_repos_with_dot_git": 0,
            "owner_clone_cost": "NOT-CHECKED",
        },
        "fixture": {
            "dominate_path": M.DOMINATE_REL,
            "dominate_planted_bytes": M.DOMINATE_LEN,
            "packed_bytes": fixture["packed_bytes"],
            "clone_disk_bytes": fixture["clone_disk_bytes"],
            "clone_wall_ms": fixture["clone_wall_ms"],
            "packed_repeat_ok": True,
            "clone_repeat_ok": True,
            "clone_exceeds_packed": True,
            "blobs": fixture["blobs"],
            "count_objects_raw": fixture["packed_run1"]["raw"],
        },
        "owner_repos": [owner],
        "observations": [
            {
                "name": "fixture_packed_bytes",
                "measured": fixture["packed_bytes"],
                "method": "git count-objects -v / -vH, (size + size-pack) KiB * 1024",
                "anchor": "command-center/p2-wave/probes/AUD-0010/probe1_count_objects.py",
            },
            {
                "name": "fixture_clone_disk_bytes",
                "measured": fixture["clone_disk_bytes"],
                "method": "timed git clone --no-hardlinks; du -sb of destination",
                "anchor": "command-center/p2-wave/probes/AUD-0010/probe2_timed_clone.py",
            },
            {
                "name": "owner_ast_integrate_clone_cost",
                "measured": "NOT-CHECKED",
                "method": "git rev-parse / exists(.git)",
                "anchor": str(M.REPO),
            },
            {
                "name": "owner_ast_integrate_filesystem_bytes",
                "measured": owner["filesystem_bytes"],
                "method": "du -sb of the worktree; not a clone cost",
                "anchor": str(M.REPO),
            },
        ],
        "named_probes": [
            {
                "id": "probe1-count-objects",
                "command": M.P1_CMD,
                "role": "packed-size",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2-timed-clone",
                "command": M.P2_CMD,
                "role": "clone-disk",
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "packed-repeat-within-2pct",
                "command": M.P1_CMD,
                "result": "PASS",
                "requirement": (
                    "record the measurement twice on an unchanged repo and "
                    "require the two runs agree within 2 percent"
                ),
            },
            {
                "id": "clone-repeat-and-diverge-from-packed",
                "command": M.P2_CMD,
                "result": "PASS",
                "requirement": (
                    "independently timed clone --no-hardlinks; disk bytes are "
                    "not the packed view from count-objects"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0010-probe2-timed-clone",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-clones the fixture and falsifies using packed size "
                "as clone cost. Not a second human in a fresh context; disclosed."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/AUD-0010/probe1_count_objects.py",
                "kind": "command",
                "claim": (
                    "git count-objects -vH twice on an unchanged fixture agrees "
                    f"within 2 percent at {fixture['packed_bytes']} packed bytes."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0010/probe2_timed_clone.py",
                "kind": "command",
                "claim": (
                    "git clone --no-hardlinks materializes "
                    f"{fixture['clone_disk_bytes']} bytes, exceeding packed "
                    f"{fixture['packed_bytes']}; dominant blob is "
                    f"{fixture['dominant_path']} ({fixture['dominant_blob_bytes']} B)."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0010/measure.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree /opt/p2/ast-integrate has no .git, so a fresh "
                    "clone cost for the owner repo is not defined here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run AUD-0010 against a git checkout of the owner repo "
                    "and record count-objects plus clone --no-hardlinks there."
                ),
            },
            {
                "claim": (
                    "Other owner-controlled repos (~/Documents/GitHub, live "
                    "agent worktrees) were not walked; this wave's floor forbids "
                    "that crawl."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Inventory owner git remotes from an approved list and "
                    "repeat both probes per remote."
                ),
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "this worktree is a git repository",
                "clone cost of every owner repo on the estate",
            ],
            "proof_surface": (
                "Fixture git repo: count-objects twice within 2 percent, clone "
                "--no-hardlinks twice within 2 percent, clone disk exceeds packed "
                "size, planted dominate.bin is the largest blob."
            ),
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:AUD-0010 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:AUD-0010 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:AUD-0010 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} packed={fixture['packed_bytes']} "
        f"clone={fixture['clone_disk_bytes']} dominant={fixture['dominant_path']}"
    )
    print("SUCCESS:AUD-0010 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
