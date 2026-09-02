#!/usr/bin/env python3
"""Probe 2: Draft202012Validator over every affected record + vacuity + reviewer instance.

Independent of probe 1's seat checker: this path only loads JSON Schema and
counts iter_errors. The reviewer counterexample is a v1 instance that validates
as the conflated bag and is rejected as a v2 role (obligation stuffed into
permissions[]).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reconstruct as R  # noqa: E402
import role_check as RC  # noqa: E402

FIX = HERE / "fixtures"


def main() -> int:
    v2_schema = RC.load_json(RC.V2_SCHEMA)
    v1_schema = RC.load_json(RC.V1_SCHEMA)
    v2 = RC.draft2020_validator(v2_schema)
    v1 = RC.draft2020_validator(v1_schema)

    catalogue = RC.load_json(FIX / "catalogue.json")
    n_ok, msgs_ok = RC.error_count(v2, catalogue)
    per_role = []
    fail = False
    for role in catalogue["roles"]:
        wrapped = {"roles": [role]}
        n, msgs = RC.error_count(v2, wrapped)
        per_role.append({"id": role["id"], "errors": n, "msgs": msgs[:3]})
        if n != 0:
            fail = True
        overlap = RC.overlapping_ids(role)
        if overlap:
            fail = True
            per_role[-1]["overlap"] = overlap

    invalids = {
        "empty_buckets": RC.load_json(FIX / "invalid_empty_buckets.json"),
        "wrong_kind": RC.load_json(FIX / "invalid_obligation_kind.json"),
        "garbage": RC.load_json(FIX / "invalid_garbage.json"),
    }
    inv_counts = {}
    for name, inst in invalids.items():
        n, msgs = RC.error_count(v2, inst)
        inv_counts[name] = {"errors": n, "head": msgs[:4]}
        if n <= 0:
            fail = True

    v1_critic = RC.load_json(FIX / "v1_critic_conflated.json")
    n_v1, msgs_v1 = RC.error_count(v1, v1_critic)
    n_v1_as_v2, _ = RC.error_count(v2, v1_critic)

    counter = RC.load_json(FIX / "reviewer_counterexample_v1.json")
    n_c_v1, _ = RC.error_count(v1, counter)
    n_c_v2, msgs_c_v2 = RC.error_count(v2, counter)

    stuffed = RC.load_json(FIX / "reviewer_obligation_in_permissions.json")
    n_stuffed, msgs_stuffed = RC.error_count(v2, stuffed)

    rec = R.reconstruct()
    cites_ok = not rec["catalog"]["missing"]
    conflator_ok = rec["conflating_field"] == "permissions"
    source_ok = rec["inventory_source"] in {"disk:$defs.role", "catalog-quotations"}

    print(f"catalogue_records={len(catalogue['roles'])} schema_errors={n_ok} expect=0")
    for row in per_role:
        print(f"role id={row['id']} errors={row['errors']}")
    for name, row in inv_counts.items():
        print(f"invalid {name} errors={row['errors']} head={row['head']}")
    print(f"v1_critic v1_errors={n_v1} v2_errors={n_v1_as_v2}")
    print(
        f"reviewer_counterexample v1_errors={n_c_v1} v2_errors={n_c_v2} "
        f"v2_head={msgs_c_v2[:3]}"
    )
    print(
        f"reviewer_obligation_in_permissions v2_errors={n_stuffed} "
        f"head={msgs_stuffed[:3]}"
    )
    print(
        f"reconstruct conflating_field={rec['conflating_field']} "
        f"schema_source={rec['schema_file']['source']} "
        f"catalog_missing={rec['catalog']['missing']}"
    )
    print(
        "NEGATIVE CONTROL: invalid_garbage.json must produce >0 Draft202012Validator "
        "errors against role_mandate.schema.json. A 0-error result means the schema "
        "is vacuous and this probe must fail."
    )

    reviewer_ok = n_c_v1 == 0 and n_c_v2 > 0 and n_stuffed > 0
    reviewer = {
        "reviewer_id": "CNL-0022-probe2-counterexample",
        "verdict": "PASS" if reviewer_ok else "FAIL",
        "independent": True,
        "instances": [
            "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_counterexample_v1.json",
            "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_obligation_in_permissions.json",
        ],
        "claim": (
            "Instance A: a v1 critic with permissions=[emit_critique, consult_web, vote] "
            "is schema-valid as the reconstructed $defs.role bag and schema-invalid as "
            "v2. Instance B: a v2-shaped role with kind=obligation inside permissions[] "
            "is rejected (const kind=permission), so the split buckets are not labels."
        ),
    }
    print(json.dumps({"reviewer": reviewer}, sort_keys=True))

    if n_ok != 0:
        print(f"FAILED:CNL-0022-probe2 catalogue errors={n_ok} {msgs_ok[:5]}")
        return 1
    if n_v1 != 0:
        print(f"FAILED:CNL-0022-probe2 v1 critic rejected by reconstructed schema {msgs_v1[:3]}")
        return 1
    if n_c_v1 != 0 or n_c_v2 <= 0 or n_stuffed <= 0:
        print("FAILED:CNL-0022-probe2 reviewer counterexample did not split v1/v2")
        return 1
    if not cites_ok or not conflator_ok:
        print("FAILED:CNL-0022-probe2 catalog citations or conflator missing")
        return 1
    if fail:
        print("FAILED:CNL-0022-probe2 vacuity or per-role errors")
        return 1
    if not source_ok:
        print("FAILED:CNL-0022-probe2 inventory source unexpected")
        return 1
    print(
        f"SUCCESS:CNL-0022-probe2 jsonschema errors_on_catalogue=0 "
        f"invalid_garbage={inv_counts['garbage']['errors']} "
        f"invalid_empty={inv_counts['empty_buckets']['errors']} "
        f"invalid_kind={inv_counts['wrong_kind']['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
