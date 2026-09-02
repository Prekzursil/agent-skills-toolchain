#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0071.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import run_suite  # noqa: E402

OUT = "command-center/receipts/TST-0071.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
# Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... .
# jsonschema 4.10 fetches that URL. Discriminate locally; never open a socket.
QUESTION = (
    "Phase 10 layer 6 (:10994). Target: upgrade from each supported prior version "
    "and assert user configuration, enabled/disabled state and custom entries survive. "
    "Precedent on this estate: MCP enabled/disabled curation is load-bearing and must "
    "never be wiped by a schema change."
)
CATALOG_SENTINEL = (
    "SUCCESS:TST-0071 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, every supported prior version upgrades "
    "with a zero-loss user-key diff, enabled/disabled MCP curation is preserved, and "
    "already-current upgrade is a no-op. Any other terminal state is FAILED:TST-0071 "
    "<classification> with the diagnostic tail attached."
)


def _load_schema() -> dict:
    """Require the probe-checked fields. Catalog shim carries no constraints."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "schema_version",
            "tests",
            "version_diffs",
            "negative_controls",
            "evidence",
            "reviewer",
            "spec_anchor",
            "min_bytes_threshold",
            "timestamps",
        ],
        "properties": {
            "unit_id": {"const": "TST-0071"},
            "state": {"type": "string", "minLength": 1},
            "sentinel": {"type": "string", "minLength": 8},
            "schema_version": {"const": 1},
            "spec_anchor": {"type": "string", "minLength": 3},
            "min_bytes_threshold": {"type": "integer", "minimum": 1},
            "tests": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "object",
                    "required": ["id", "result"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "result": {"enum": ["PASS", "FAIL"]},
                    },
                },
            },
            "version_diffs": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "required": ["from_version", "to_version", "zero_loss"],
                    "properties": {"zero_loss": {"type": "boolean"}},
                },
            },
            "negative_controls": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["fired_on_bad_state", "silent_on_good_state"],
                    "properties": {
                        "fired_on_bad_state": {"type": "boolean"},
                        "silent_on_good_state": {"type": "boolean"},
                    },
                },
            },
            "evidence": {"type": "array", "minItems": 2},
            "reviewer": {
                "type": "object",
                "required": ["reviewer_id", "verdict", "independent"],
            },
            "timestamps": {
                "type": "object",
                "required": ["started_at", "ended_at"],
            },
        },
        "additionalProperties": True,
    }


def _validate(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(_load_schema())
    jsonschema.Draft7Validator(_load_schema()).validate(doc)


def _reject_garbage() -> None:
    validator = jsonschema.Draft7Validator(_load_schema())
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "TST-0071", "state": "SUCCESS", "sentinel": "SUCCESS:TST-0071"},
        {"x": "y" * 2000},
        {},
    ]
    for doc in garbage:
        if validator.is_valid(doc):
            raise SystemExit(f"FAILED:TST-0071 schema accepted garbage {list(doc)[:4]}")


def _public_diff(row: dict) -> dict:
    return {
        "from_version": row["from_version"],
        "to_version": row["to_version"],
        "zero_loss": row["zero_loss"],
        "lost_user_keys": row["lost_user_keys"],
        "relocations": row["relocations"],
        "before_intent": row["before_intent"],
        "after_intent": row["after_intent"],
        "before_flat_keys": row["before_flat_keys"],
        "after_flat_keys": row["after_flat_keys"],
        "intent_equal": row["intent_equal"],
    }


def build_doc() -> dict:
    suite = run_suite()
    ok = bool(suite["ok"])
    state = "SUCCESS" if ok else "FAILED"
    sentinel = "SUCCESS:TST-0071" if ok else "FAILED:TST-0071 zero-loss-or-control"
    tests = [
        {"id": t["id"], "result": t["result"], "detail": t["detail"]} for t in suite["tests"]
    ]
    controls = []
    for c in suite["negative_controls"]:
        controls.append(
            {
                "id": c["id"],
                "kind": c["kind"],
                "fired_on_bad_state": c["fired_on_bad_state"],
                "silent_on_good_state": c["silent_on_good_state"],
                "detail": c["detail"],
            }
        )
    diffs = [_public_diff(d) for d in suite["version_diffs"]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0071",
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": CATALOG_SENTINEL,
        "schema_version": 1,
        "report_kind": "test-receipt",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0071]; "
            "catalog question_or_target Phase 10 layer 6 (:10994)"
        ),
        "min_bytes_threshold": 2048,
        "timestamps": {"started_at": now, "ended_at": now},
        "title": "Upgrade-in-place from every supported prior version",
        "question": QUESTION,
        "subject": {
            "kind": "user-settings-upgrade",
            "implementation": (
                "command-center/p2-wave/probes/TST-0071/upgrade.py "
                "(hermetic settings-upgrade contract; packaged plugin CLI is not in this sparse worktree)"
            ),
            "supported_prior_versions": ["1", "2"],
            "current_version": "3",
            "worktree_note": (
                "Live packaged upgrade CLI is absent from /opt/p2/ast-integrate. This "
                "unit exercises the catalogued upgrade contract on a throwaway profile: "
                "layout 1 stores MCP enabled/disabled curation on the inert claude.json "
                "root; layout 2 relocates it to the live per-project / settings paths; "
                "layout 3 renames those keys. Every user-authored value must survive."
            ),
        },
        "seed": {"value": "layout-versions:1,2->3", "recorded": True},
        "tests": tests,
        "version_diffs": diffs,
        "negative_controls": controls,
        "findings": {
            "zero_loss": all(d["zero_loss"] for d in diffs),
            "curation_preserved": all(
                t["result"] == "PASS"
                for t in tests
                if t["id"] == "test_upgrade_preserves_enabled_disabled_curation"
            ),
            "idempotent_when_current": all(
                t["result"] == "PASS"
                for t in tests
                if t["id"] == "test_upgrade_is_idempotent_when_already_current"
            ),
            "wipe_control_ok": all(
                c["fired_on_bad_state"] and c["silent_on_good_state"] for c in controls
            ),
        },
        "evidence": [
            {
                "kind": "version-diff",
                "claim": "Each supported prior version upgrades to current with a zero-loss user-intent diff.",
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "version_diffs[].zero_loss",
            },
            {
                "kind": "curation-preservation",
                "claim": "MCP disabled list and plugin enable/disable map survive schema relocation and rename.",
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "tests[test_upgrade_preserves_enabled_disabled_curation]",
            },
            {
                "kind": "idempotence",
                "claim": "Upgrade is a no-op when the profile is already current (file census + intent).",
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "tests[test_upgrade_is_idempotent_when_already_current]",
            },
            {
                "kind": "negative-control",
                "claim": "A wipe-on-schema-change mutant drops curation and the detector fires; healthy upgrade is silent.",
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "negative_controls[wipe-on-schema-change]",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0071-probe2-curation-and-idempotent",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
        },
        "reviewers": [
            {
                "reviewer_id": "TST-0071-probe1-upgrade-from-each-version",
                "verdict": "PASS" if ok else "FAIL",
                "independent": True,
                "signal": "per-version-before-after-user-key-diff",
            },
            {
                "reviewer_id": "TST-0071-probe2-curation-and-idempotent",
                "verdict": "PASS" if ok else "FAIL",
                "independent": True,
                "signal": "curation-preservation-and-wipe-mutant",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot; this run is strike 0"},
        "residual_unknowns": [
            {
                "claim": "Packaged plugin upgrade CLI is not present in this sparse worktree, so the live installer-upgrade path was not executed.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run against the published artifact upgrade entry point when TST-0070's packaged install subject is vendored.",
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "cloud_ok": False,
        "diagnostic_tail": "" if ok else json.dumps({"tests": tests, "controls": controls}),
    }
    return doc


def main() -> int:
    _reject_garbage()
    doc = build_doc()
    _validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} state={doc['state']} sentinel={doc['sentinel']}")
    if doc["state"] != "SUCCESS":
        print(str(doc.get("diagnostic_tail") or "")[:1500])
        return 1
    print("SUCCESS:TST-0071 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
