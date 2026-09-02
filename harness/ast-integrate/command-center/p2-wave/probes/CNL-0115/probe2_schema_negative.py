#!/usr/bin/env python3
"""Probe 2: Draft 2020-12 schema + negative control (six-week re-litigation)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import ACK_UNCHANGED, SLEEP, WAKE_DELTA, classify  # noqa: E402
from fixtures import (  # noqa: E402
    task_clock,
    task_delta,
    task_reask,
    task_stale_six_weeks,
)
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0115-standing-watch-council-long-running-trigger-woken-low-inte.md"
)
CATALOG_SHIM = "command-center/schema/council-preset.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0115/council-preset.schema.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0115-probe2 {msg}")
    return 1


def err_count(validator: Draft202012Validator, instance: object) -> int:
    return sum(1 for _ in validator.iter_errors(instance))


def main() -> int:
    shim_path = REPO / CATALOG_SHIM
    if not shim_path.is_file():
        return fail("catalog-shim-absent")
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    if not isinstance(shim.get("$ref"), str) or "ast-integrate.invalid" not in str(
        shim.get("$ref")
    ):
        return fail("catalog-shim-unexpected")
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    live = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    siblings = json.loads((HERE / "siblings.json").read_text(encoding="utf-8"))[
        "presets"
    ]

    # Do not Draft202012Validator(catalog shim): jsonschema 4.10.3 RefResolver
    # fetches https://ast-integrate.invalid/... . The unit-local schema is the
    # executable contract; overwriting the shared shim is a sibling rebuild.
    envelope_v = Draft202012Validator(schema)
    rec = dict(schema["$defs"]["preset_record"])
    rec["$schema"] = schema["$schema"]
    rec["$defs"] = schema["$defs"]
    core_v = Draft202012Validator(rec)

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
        "family": "STANDING-WATCH",
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

    stale = task_stale_six_weeks()
    rejected_state = classify(event=stale["event"], ledger=stale["ledger"])
    if rejected_state["disposition"] != ACK_UNCHANGED:
        return fail(
            f"negative-control-missed disposition={rejected_state['disposition']}"
        )
    if rejected_state["wake"] is True:
        return fail("negative-control-woke-on-stale")
    if rejected_state["new_decision_id"] is not None:
        return fail("negative-control-wrote-new-decision")
    if rejected_state["prior_decision_id"] != "D-2026-07-13-shipping-window":
        return fail("negative-control-dropped-prior-decision")

    clock = classify(event=task_clock()["event"], ledger=task_clock()["ledger"])
    if clock["disposition"] != SLEEP:
        return fail(f"clock-tick-woke disposition={clock['disposition']}")

    delta = classify(event=task_delta()["event"], ledger=task_delta()["ledger"])
    if delta["disposition"] != WAKE_DELTA:
        return fail(f"material-delta-slept disposition={delta['disposition']}")

    reask = classify(event=task_reask()["event"], ledger=task_reask()["ledger"])
    if reask["wake"]:
        return fail("bare-reask-woke")

    print(
        json.dumps(
            {
                "probe": "probe2-schema-negative",
                "unit_id": "CNL-0115",
                "validator": "jsonschema.Draft202012Validator",
                "schema": LOCAL_SCHEMA,
                "catalog_shim": CATALOG_SHIM,
                "affected_records": per_record,
                "total_errors": total_errors,
                "planted_invalid_errors": invalid_errors,
                "negative_control": {
                    "rejected_state": (
                        "same question fingerprint 42 days later records a "
                        "new competing decision"
                    ),
                    "check_does": (
                        "classify returns ACK-UNCHANGED; wake=false; "
                        "new_decision_id=null; prior decision_id is retained"
                    ),
                    "observed": rejected_state,
                },
                "clock_tick_stays_asleep": clock,
                "material_delta_wakes": delta,
                "bare_reask_does_not_reopen": reask,
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        f"SUCCESS:CNL-0115-probe2 schema_errors={total_errors} "
        f"invalid_errors={invalid_errors} "
        f"neg_disposition={rejected_state['disposition']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
