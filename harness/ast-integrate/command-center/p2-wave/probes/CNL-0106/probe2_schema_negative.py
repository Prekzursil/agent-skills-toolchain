#!/usr/bin/env python3
"""Probe 2: Draft 2020-12 schema + negative control (YES despite bound FAIL)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import NOT_YES, ORACLE_CHALLENGE, YES, adjudicate  # noqa: E402
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0106-code-review-tribunal-backed-by-an-executable-oracle.md"
)
CATALOG_SCHEMA = "command-center/schema/council-preset.schema.json"
LOCAL_SCHEMA = HERE / "council-preset.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0106-probe2 {msg}")
    return 1


def err_count(validator: Draft202012Validator, instance: object) -> int:
    return sum(1 for _ in validator.iter_errors(instance))


def record_validator(schema: dict) -> Draft202012Validator:
    rec = schema["$defs"]["preset_record"]
    return Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$id": str(schema.get("$id") or "") + "#preset_record",
            **rec,
        }
    )


def main() -> int:
    live_path = REPO / OUT
    if not live_path.is_file():
        return fail("artifact-absent")
    catalog_path = REPO / CATALOG_SCHEMA
    if not catalog_path.is_file():
        return fail("catalog-schema-path-absent")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if "$ref" not in catalog:
        return fail("catalog-schema-expected-ref-shim")
    # Do not Draft202012Validator(catalog): the $ref is https://ast-integrate.invalid/
    # and raises RefResolutionError off-network.

    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    live = json.loads(live_path.read_text(encoding="utf-8"))
    siblings = json.loads((HERE / "siblings.json").read_text(encoding="utf-8"))[
        "presets"
    ]

    envelope_v = Draft202012Validator(schema)
    core_v = record_validator(schema)

    affected = [("live-artifact", live, envelope_v)]
    for sib in siblings:
        affected.append((sib["id"], sib, core_v))
    affected.append(("canonical-preset", PRESET, core_v))

    per_record: list[dict] = []
    total_errors = 0
    for name, inst, validator in affected:
        n = err_count(validator, inst)
        total_errors += n
        per_record.append({"record": name, "errors": n})
        if n:
            msgs = [
                f"{e.json_path}: {e.message}"
                for e in list(validator.iter_errors(inst))[:4]
            ]
            return fail(f"schema {name} errors={n} {msgs}")
    if total_errors != 0:
        return fail(f"total_errors={total_errors} expected 0")

    invalid = {
        "id": 12,
        "title": "x",
        "family": "ENGINEERING-REVIEW",
        "roles": "not-an-array",
        "protocol_schedule": [],
        "voting": {"rule": "majority"},
        "stopping": {"max_rounds": 0},
        "default_binding": {},
        "editable_dials": [],
    }
    invalid_errors = err_count(core_v, invalid)
    if invalid_errors < 1:
        return fail("validator-vacuous: planted-invalid produced 0 errors")

    bound = "pytest tests/test_parser.py -q"
    unanimous = [YES, YES, YES, YES]
    rejected_state = adjudicate(
        ballots=unanimous,
        oracle_status="FAIL",
        oracle_command=bound,
        binding_commands=[bound],
        subject_kind="code",
    )
    if rejected_state["outcome"] != NOT_YES:
        return fail(
            f"negative-control-missed outcome={rejected_state['outcome']}"
        )
    if rejected_state["vote"] != YES:
        return fail("negative-control-dropped-vote-exhibit")

    unbound = adjudicate(
        ballots=unanimous,
        oracle_status="FAIL",
        oracle_command="pytest tests/unrelated.py -q",
        binding_commands=[bound],
        subject_kind="code",
    )
    if unbound["outcome"] != YES:
        return fail(f"unbound-fail-vetoed outcome={unbound['outcome']}")

    disputed = adjudicate(
        ballots=unanimous,
        oracle_status="FAIL",
        oracle_command=bound,
        binding_commands=[bound],
        subject_kind="test",
    )
    if disputed["outcome"] != ORACLE_CHALLENGE:
        return fail(f"disputed-test-auto-veto outcome={disputed['outcome']}")

    confirmed = adjudicate(
        ballots=unanimous,
        oracle_status="FAIL",
        oracle_command=bound,
        binding_commands=[bound],
        subject_kind="test",
        clerk_verdict="CONFIRMED-LOAD-BEARING",
    )
    if confirmed["outcome"] != NOT_YES:
        return fail("clerk-confirm-did-not-restore-gate")

    print(
        json.dumps(
            {
                "probe": "probe2-schema-negative",
                "unit_id": "CNL-0106",
                "validator": "jsonschema.Draft202012Validator",
                "catalog_schema": CATALOG_SCHEMA,
                "catalog_schema_is_ref_shim": True,
                "executable_schema": (
                    "command-center/p2-wave/probes/CNL-0106/"
                    "council-preset.schema.json"
                ),
                "affected_records": per_record,
                "total_errors": total_errors,
                "planted_invalid_errors": invalid_errors,
                "negative_control": {
                    "rejected_state": (
                        "outcome=YES after unanimous YES while bound "
                        "oracle reports FAIL"
                    ),
                    "check_does": (
                        "adjudicate returns outcome=NOT-YES; vote=YES is "
                        "retained as exhibit and is not the recorded outcome"
                    ),
                    "observed": rejected_state,
                },
                "unbound_fail_cannot_veto": unbound,
                "disputed_test_demotes_oracle": disputed,
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        f"SUCCESS:CNL-0106-probe2 schema_errors={total_errors} "
        f"invalid_errors={invalid_errors} "
        f"neg_outcome={rejected_state['outcome']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
