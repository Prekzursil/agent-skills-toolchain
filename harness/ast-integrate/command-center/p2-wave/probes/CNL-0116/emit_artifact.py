#!/usr/bin/env python3
"""Emit the CNL-0116 flagship preset artifact (JSON written at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import composer as C  # noqa: E402

OUT = "command-center/design/council/CNL-0116-general-purpose-auto-composed-council-preset-the-flagship.md"
SCHEMA = "command-center/p2-wave/probes/CNL-0116/council-preset.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-preset.schema.json"
SIBLING_LIB = HERE / "fixtures" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
TASKS = HERE / "fixtures" / "tasks.json"
QUESTION = (
    "For an arbitrary owner request with no preset named, what does the "
    "auto-composer produce, how does it explain every dial it chose, and "
    "what is the owner's one-step override path?"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    schema = load(REPO / SCHEMA)
    sib_lib = load(SIBLING_LIB)
    tasks = load(TASKS)["tasks"]
    canonical = next(t for t in tasks if t["id"] == "T-PROD-GNG")
    preset = C.flagship_preset()
    if tuple(preset.keys()) != C.TWENTY_KEYS:
        print(f"FAILED:emit twenty keys {list(preset.keys())}")
        return 1
    inst = C.compose(canonical["text"])
    nearest = C.nearest_sibling(inst, sib_lib["presets"])
    if nearest["nearest_id"] != "C-M01":
        print(f"FAILED:emit nearest={nearest['nearest_id']} expected C-M01")
        return 1
    if nearest["distance"]["name_only"] or nearest["distance"]["integer_axes"] < 2:
        print(f"FAILED:emit sibling not distinct {nearest['distance']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0116",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0116",
        "completion_sentinel": "SUCCESS:CNL-0116",
        "title": "General-purpose auto-composed council preset (the flagship)",
        "question": QUESTION,
        "answer": (
            "When the owner names no preset, the flagship C-GP01 auto-composer "
            "is the default_binding. It derives risk_tier from the task (or an "
            "explicit charter value), seats Orchestrator+Domain+Adversary+"
            "Evidence-auditor plus feature-triggered Legal/Security/Operator "
            "seats, binds a risk-tier protocol schedule, a matching vote rule "
            "and a declarative stopping expression, and emits a contestable "
            "explanation for every dial. The owner's one-step override path is "
            "owner.override(dial, value): one call records the override and "
            "re-derives unlocked dials. Naming a preset is also one-step and "
            "exits the flagship path. Silent edits and non-editable dials are "
            "rejected. Nearest sibling in the estate fixture is C-M01 (static "
            "general-purpose four-voice); the differential is auto-compose, "
            "mandatory explanation, recorded override, and a different roster/"
            "vote/stop — not the name. SUCCESS:CNL-0116"
        ),
        "preset": preset,
        "auto_composer": {
            "module": "command-center/p2-wave/probes/CNL-0116/composer.py",
            "entry": "compose(task, risk_tier=None, override=None, named_preset=None)",
            "core_roles": list(C.CORE_ROLES),
            "feature_seats": ["Legal", "Security", "Operator"],
            "risk_tiers": ["low", "medium", "high", "critical"],
            "unnamed_path_only": True,
            "twenty_keys": list(C.TWENTY_KEYS),
        },
        "one_step_override": {
            "path": "owner.override(dial, value)",
            "editable_dials": list(C.EDITABLE_DIALS),
            "locked_dials": sorted(C.LOCKED_DIALS),
            "named_preset_exit": "owner.override('preset', '<id>') leaves flagship unused",
            "unsatisfiable_constraint": "BLOCKED, never a quiet relaxation (CNL-0004)",
        },
        "sibling": {
            "library": "command-center/p2-wave/probes/CNL-0116/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "harness_restore_on_this_tree": False,
            "catalog_cited_preset_count": 72,
            "fixture_preset_count": len(sib_lib["presets"]),
            "nearest_named": nearest["nearest_id"],
            "distance": nearest["distance"],
            "supersedes": ["C-M01"],
            "extends": ["council.preset.catalog-class.editable"],
            "name_only_duplicate_rejected": True,
        },
        "worked_example": {
            "task_id": canonical["id"],
            "task": canonical["text"],
            "instance": {
                "roles": inst["roles"],
                "protocol_schedule": inst["protocol_schedule"],
                "voting": inst["voting"],
                "stopping": inst["stopping"],
                "risk_tier": inst["charter"]["risk_tier"],
                "binding": inst["binding"],
                "override_path": inst["one_step_override_path"],
                "explanation_count": len(inst["explanation"]),
            },
            "fingerprint": C.fingerprint(inst),
        },
        "tests": [
            {
                "id": "instantiate-fixture-task",
                "probe": "probe1_instantiate.py",
                "records": [
                    "roster",
                    "protocol_schedule",
                    "voting_method",
                    "stopping_expression",
                ],
            },
            {
                "id": "nearest-sibling-differential",
                "probe": "probe2_sibling_schema.py",
                "nearest_must_be_named": True,
            },
            {
                "id": "jsonschema-draft202012",
                "probe": "probe2_sibling_schema.py",
                "expected_errors_on_valid": 0,
            },
            {
                "id": "negative-control",
                "probe": "probe2_sibling_schema.py",
            },
        ],
        "negative_controls": [
            {
                "id": "missing-explanation",
                "rejects": "a composed instance whose voting.rule explanation reason is empty",
                "verbatim": (
                    "check_integrity FIRES missing-explanation:voting.rule on a "
                    "composed instance whose explanation reason for voting.rule "
                    "was deleted; the unmodified instance is SILENT (0 errors)."
                ),
            },
            {
                "id": "non-editable-dial",
                "rejects": "owner.override('default_binding', 'static')",
                "verbatim": (
                    "compose(..., override={'default_binding': 'static'}) raises "
                    "ComposerError non-editable dial override rejected."
                ),
            },
            {
                "id": "name-only-duplicate",
                "rejects": "a sibling copy of the flagship instance with only id/name changed",
                "verbatim": (
                    "distance(name-mutant, flagship).name_only is True and the "
                    "preset is rejected as a mechanism-duplicate; C-M01 is not."
                ),
            },
            {
                "id": "legal-false-positive",
                "rejects": "seating Legal on a task with no legal cue",
                "verbatim": (
                    "T-CSV 'Refactor an internal CSV parser...' must NOT seat Legal."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0116-probe2-sibling-schema",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "Re-instantiate C-GP01 against T-PROD-GNG and recompute nearest "
                "sibling over the fixture catalog; require integer_axes >= 2 "
                "versus named C-M01."
            ),
        },
        "honesty": {
            "catalog_output_schema": CATALOG_SCHEMA,
            "catalog_schema_owner_on_this_tree": "CNL-0107",
            "catalog_schema_defs": ["council_preset"],
            "executable_schema": SCHEMA,
            "twelve_council_bytes_present": False,
            "nearest_sibling_scope": "estate fixture (not a 72-row recount)",
            "cloud_ok_is_not_delivery": True,
        },
        "residual_unknowns": [
            {
                "id": "12-COUNCIL-bytes-absent",
                "detail": (
                    "harness-restore 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not "
                    "on this worktree. Nearest-sibling is computed over the "
                    "estate fixture (C-M01 citation + on-tree catalog-class "
                    "sample + contrast row), not a 72-row recount."
                ),
            },
            {
                "id": "CNL-0101-0102-not-on-disk",
                "detail": (
                    "Typed-delta key list is the 20 names this unit enumerates "
                    "and validates; CNL-0101/0102 artifacts are not present to "
                    "cross-check the binding matrix of all 72."
                ),
            },
            {
                "id": "catalog-schema-path-occupied-by-CNL-0107",
                "detail": (
                    "command-center/schema/council-preset.schema.json is the "
                    "CNL-0107 typed-delta wrapper (unit_id const CNL-0107, "
                    "$defs.council_preset). CNL-0116 did not overwrite it. "
                    "Live Draft202012 validation uses the unit-local schema."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0116/composer.py",
                "role": "composer",
            },
        ],
        "ts": now,
    }
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print(f"FAILED:emit schema errors {len(errors)}")
        for e in errors[:8]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} nearest={nearest['nearest_id']} axes={nearest['distance']['integer_axes']}")
    print("SUCCESS:CNL-0116 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
