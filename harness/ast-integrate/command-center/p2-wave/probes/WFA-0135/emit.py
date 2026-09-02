#!/usr/bin/env python3
"""Emit the WFA-0135 foundry tier-ledger artifact from a live gate run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import demote_experiment, unproven_experiment  # noqa: E402
from gate import DEMOTE_MARKER, UNPROVEN_MARKER, first_line_with, gate  # noqa: E402
from library import FLAGSHIP_FLOOR  # noqa: E402
from materialize import run_and_receipt, write_estate  # noqa: E402

OUT = REPO / "command-center/foundry/WFA-0135-quality-tier-evidence-gate-40-flagship-end-to-end-vs.json"
ESTATE = HERE / "estate"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0135/probe1_demote.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0135/probe2_unproven.py"
)
QUESTION = (
    "Implement the two-tier contract - at least 40 flagship workflows with full "
    "end-to-end tests, every remaining workflow executable, schema-valid, "
    "documented and smoke-tested - as a gate that resolves each tier claim to "
    "the test artifacts that back it on disk. Question: for each blueprint "
    "claiming flagship tier, which end-to-end test file and which passing run "
    "id proves it, and how many claims resolve to nothing?"
)


def main() -> int:
    write_estate(ESTATE)
    recs = run_and_receipt(ESTATE)
    led = gate(ESTATE, repo=REPO)
    counts = led["counts"]
    if counts["proven_flagship"] < FLAGSHIP_FLOOR:
        print("FAILED:WFA-0135 proven flagship below floor", counts)
        return 1
    if counts["proven_remainder"] != 56:
        print("FAILED:WFA-0135 remainder not fully proven", counts)
        return 1
    if counts["unproven"] != 0 or counts["demoted"] != 0 or counts["failed"] != 0:
        print("FAILED:WFA-0135 live estate not clean", counts)
        return 1
    if counts["claims_resolving_to_nothing"] != 0:
        print("FAILED:WFA-0135 live claims resolve to nothing", led["claims_resolving_to_nothing"])
        return 1

    demo = demote_experiment(ESTATE)
    planted = unproven_experiment(ESTATE)
    if not demo.get("ok"):
        print("FAILED:WFA-0135 demote control", json.dumps(demo, indent=2))
        return 1
    if not planted.get("ok"):
        print("FAILED:WFA-0135 unproven control", json.dumps(planted, indent=2))
        return 1

    gate_py = HERE / "gate.py"
    demote_line = first_line_with(gate_py, f"# {DEMOTE_MARKER}")
    unproven_line = first_line_with(gate_py, f"# {UNPROVEN_MARKER}")
    if not demote_line or not unproven_line:
        print("FAILED:WFA-0135 missing gate markers")
        return 1

    preferred = REPO / "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
    doc = {
        "unit_id": "WFA-0135",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0135",
        "kind": "tier-ledger",
        "title": "Quality-tier evidence gate (40 flagship end-to-end vs the smoke-tested remainder)",
        "question": QUESTION,
        "mechanism": (
            "tier claim -> on-disk test-artifact resolution with UNPROVEN as a "
            "distinct outcome from PROVEN, DEMOTE, and FAIL"
        ),
        "library_source": {
            "preferred": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            "preferred_present": preferred.is_file(),
            "used": "command-center/p2-wave/probes/WFA-0135/estate/library.json",
            "note": (
                "This worktree has no harvested 09-WORKFLOW-BLUEPRINT-LIBRARY.json. "
                "The gate is implemented and proven on a 96-entry fixture estate "
                "(40 flagship + 56 remainder). This is not a certification of the "
                "absent Windows harvest library."
            ),
        },
        "contract": {
            "flagship_floor": FLAGSHIP_FLOOR,
            "flagship_requires": ["e2e_test_file_line", "passing_run_id"],
            "remainder_requires": [
                "executable",
                "schema_valid",
                "documented",
                "smoke_tested",
            ],
            "path_without_run": "UNPROVEN",
        },
        "counts": counts,
        "rows": led["rows"],
        "claims_resolving_to_nothing": led["claims_resolving_to_nothing"],
        "receipts_written": len(recs),
        "evidence": [
            {
                "id": "E1-demote-on-deleted-test",
                "kind": "rerunnable-command",
                "path": "command-center/p2-wave/probes/WFA-0135/gate.py",
                "line": demote_line,
                "command": P1,
                "snippet": DEMOTE_MARKER,
            },
            {
                "id": "E2-path-without-run-is-unproven",
                "kind": "rerunnable-command",
                "path": "command-center/p2-wave/probes/WFA-0135/gate.py",
                "line": unproven_line,
                "command": P2,
                "snippet": UNPROVEN_MARKER,
            },
        ],
        "tests": [
            {
                "id": "both-states-delete-flagship-test",
                "result": "PASS" if demo["ok"] else "FAIL",
                "detail": demo,
            },
            {
                "id": "path-only-is-unproven",
                "result": "PASS" if planted["ok"] else "FAIL",
                "detail": planted,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0135-probe2-unproven-scope",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not author the gate; it re-resolves every proven "
                "flagship row to a live file:line plus run_id and plants a "
                "path-only mutant that must come back UNPROVEN."
            ),
        },
        "negative_controls": [
            {
                "id": "both-states-delete-flagship-test",
                "kind": "mutation",
                "description": (
                    "Delete one flagship e2e test file; that row must DEMOTE "
                    "out of flagship rather than staying green."
                ),
                "fired_on_bad_state": bool(demo.get("ok")),
                "silent_on_good_state": counts["proven_flagship"] >= FLAGSHIP_FLOOR,
            },
            {
                "id": "path-only-is-unproven",
                "kind": "mutation",
                "description": (
                    "Keep the e2e test path and strip the passing run receipt; "
                    "the row must be UNPROVEN, not PROVEN."
                ),
                "fired_on_bad_state": bool(planted.get("ok")),
                "silent_on_good_state": counts["unproven"] == 0,
            },
        ],
        "report": {
            "kind": "tier-ledger",
            "observations": [
                {
                    "name": "proven_flagship",
                    "measured": counts["proven_flagship"],
                    "method": "gate.resolve_row over on-disk e2e file:line plus passing run_id",
                    "anchor": f"command-center/p2-wave/probes/WFA-0135/gate.py:{demote_line}",
                },
                {
                    "name": "proven_remainder",
                    "measured": counts["proven_remainder"],
                    "method": "executable + schema_valid + documented + smoke_tested with run_id",
                    "anchor": f"command-center/p2-wave/probes/WFA-0135/gate.py:{unproven_line}",
                },
                {
                    "name": "claims_resolving_to_nothing",
                    "measured": counts["claims_resolving_to_nothing"],
                    "method": "reason tag resolves-to-nothing on each row",
                    "anchor": "command-center/p2-wave/probes/WFA-0135/gate.py",
                },
            ],
            "control_ids": [
                "both-states-delete-flagship-test",
                "path-only-is-unproven",
            ],
        },
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output_schema": "command-center/schema/foundry-artifact.schema.json#/$defs/tier-ledger",
    }
    local_schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "kind",
            "counts",
            "rows",
            "tests",
            "contract",
            "evidence",
            "reviewer",
            "report",
        ],
        "properties": {
            "unit_id": {"const": "WFA-0135"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:WFA-0135"},
            "kind": {"const": "tier-ledger"},
            "contract": {
                "type": "object",
                "required": ["path_without_run", "flagship_floor"],
                "properties": {
                    "path_without_run": {"const": "UNPROVEN"},
                    "flagship_floor": {"const": FLAGSHIP_FLOOR},
                },
            },
            "counts": {
                "type": "object",
                "required": [
                    "blueprints",
                    "proven_flagship",
                    "proven_remainder",
                    "unproven",
                    "demoted",
                    "failed",
                    "claims_resolving_to_nothing",
                    "flagship_floor_met",
                ],
            },
            "rows": {"type": "array", "minItems": 96, "maxItems": 96},
            "tests": {"type": "array", "minItems": 2},
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {"kind": {"const": "tier-ledger"}},
            },
        },
    }
    errs = list(jsonschema.Draft202012Validator(local_schema).iter_errors(doc))
    if errs:
        print("FAILED:WFA-0135 local schema", errs[0].message)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(REPO).as_posix()} "
        f"proven_flagship={counts['proven_flagship']} "
        f"nothing={counts['claims_resolving_to_nothing']}"
    )
    print("SUCCESS:WFA-0135")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
