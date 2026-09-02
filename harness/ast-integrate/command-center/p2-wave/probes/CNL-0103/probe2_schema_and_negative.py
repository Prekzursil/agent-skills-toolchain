#!/usr/bin/env python3
"""Probe 2: Draft202012Validator over affected records plus a live invalid mutant."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

NEGATIVE_VERBATIM = (
    "NEGATIVE CONTROL: Draft202012Validator is applied to a deliberately "
    "invalid preset that omits required keys (including weighting). The check "
    "must emit one or more ValidationError objects on that record. A validator "
    "that is silent on the invalid record is vacuous and this probe fails."
)


def iter_errors(validator: Draft202012Validator, instance) -> list[str]:
    return [
        f"{list(err.absolute_path)}: {err.message}"
        for err in validator.iter_errors(instance)
    ]


def main() -> int:
    schema = E.load_schema()
    Draft202012Validator.check_schema(schema)
    family_v = E.envelope_validator()
    preset_v = Draft202012Validator(E.preset_subschema(schema))

    if not E.OUT_PATH.is_file():
        print("FAILED:CNL-0103-probe2 artifact-missing")
        return 1
    artifact = json.loads(E.OUT_PATH.read_text(encoding="utf-8"))
    art_errors = iter_errors(family_v, artifact)
    if art_errors:
        print("FAILED:CNL-0103-probe2 artifact-schema-errors")
        print("\n".join(art_errors[:12]))
        return 1
    if str(artifact.get("sentinel") or "") != "SUCCESS:CNL-0103":
        print("FAILED:CNL-0103-probe2 sentinel-absent")
        return 1
    if str((artifact.get("report") or {}).get("kind") or "") != "council-preset":
        print("FAILED:CNL-0103-probe2 report-kind")
        return 1

    kind_mutant = copy.deepcopy(artifact)
    kind_mutant["report"]["kind"] = "receipt"
    kind_errors = iter_errors(family_v, kind_mutant)
    if len(kind_errors) < 1:
        print("FAILED:CNL-0103-probe2 envelope-vacuous")
        return 1

    family = E.family_members()
    records = [E.project_preset(p) for p in family]
    inner = (artifact.get("report") or {}).get("preset") or artifact.get("preset")
    if not isinstance(inner, dict):
        print("FAILED:CNL-0103-probe2 artifact-preset-missing")
        return 1
    records.append(inner)
    error_count = 0
    for rec in records:
        error_count += len(iter_errors(preset_v, rec))
    if error_count != 0:
        print(f"FAILED:CNL-0103-probe2 error_count={error_count}")
        return 1

    invalid = E.load_json(E.INVALID_PATH)
    invalid_errors = iter_errors(preset_v, invalid)
    if len(invalid_errors) < 1:
        print("FAILED:CNL-0103-probe2 vacuous-validator")
        return 1

    print(
        json.dumps(
            {
                "validator": "jsonschema.Draft202012Validator",
                "schema_path": "command-center/schema/council-preset.schema.json",
                "envelope_resolution": "disk-local RefResolver store",
                "typed_delta_schema": (
                    "command-center/p2-wave/probes/CNL-0103/fixtures/"
                    "preset.record.schema.json"
                ),
                "records_checked": len(records),
                "error_count": error_count,
                "deliberately_invalid_error_count": len(invalid_errors),
                "envelope_kind_mutant_error_count": len(kind_errors),
                "invalid_error_sample": invalid_errors[:4],
                "negative_control_verbatim": NEGATIVE_VERBATIM,
            },
            indent=2,
        )
    )
    print("SUCCESS:CNL-0103-probe2 schema-and-negative")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
