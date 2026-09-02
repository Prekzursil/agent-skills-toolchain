#!/usr/bin/env python3
"""Probe 1: Draft202012Validator over 72 records + independent 20-key recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0101-a-preset-is-a-typed-delta-over-councilspec-not-a-fork.md"
)
# Independent of corpus.DELTA_KEYS: probe1 classifies by these two sets only.
INDEP_METADATA = {
    "id",
    "title",
    "status",
    "default_binding",
    "editable_dials",
}
INDEP_BASE = {"spec_id", "spec_version"}


def record_validator():
    rec = C.record_schema()
    jsonschema.Draft202012Validator.check_schema(rec)
    return jsonschema.Draft202012Validator(rec)


def main() -> int:
    C.write_fixtures()
    presets = C.load_presets()
    if len(presets) != 72:
        print(f"FAILED:CNL-0101-probe1 preset_count={len(presets)}")
        return 1
    v = record_validator()
    errors = 0
    for rec in presets:
        n = len(list(v.iter_errors(rec)))
        errors += n
        if n:
            print(f"record {rec.get('id')} errors={n}")
            for e in list(v.iter_errors(rec))[:3]:
                print(" ", list(e.path), e.message)
    invalid = json.loads(
        (C.FIXTURES / "invalid_preset.json").read_text(encoding="utf-8")
    )
    invalid_errors = len(list(v.iter_errors(invalid)))
    print(
        json.dumps(
            {
                "probe": "probe1-schema-and-keys",
                "unit_id": "CNL-0101",
                "preset_count": len(presets),
                "schema_errors_over_72": errors,
                "invalid_record_errors": invalid_errors,
                "library_present": C.library_present(),
            },
            sort_keys=True,
        )
    )
    if errors != 0:
        print(f"FAILED:CNL-0101-probe1 schema_errors={errors} expected 0")
        return 1
    if invalid_errors < 1:
        print("FAILED:CNL-0101-probe1 invalid record produced 0 errors (vacuous)")
        return 1

    union = C.independent_union(presets)
    if len(union) != 20:
        print(f"FAILED:CNL-0101-probe1 key_union={len(union)} keys={union}")
        return 1
    mapping = {}
    for k in union:
        if k in INDEP_METADATA:
            mapping[k] = "metadata"
        elif k in INDEP_BASE:
            mapping[k] = "base"
        else:
            mapping[k] = "delta"
    class_counts = {
        "metadata": sum(1 for x in mapping.values() if x == "metadata"),
        "base": sum(1 for x in mapping.values() if x == "base"),
        "delta": sum(1 for x in mapping.values() if x == "delta"),
    }
    print(f"key_union_count={len(union)} classes={class_counts} keys={union}")
    if class_counts != {"metadata": 5, "base": 2, "delta": 13}:
        print(f"FAILED:CNL-0101-probe1 class_counts={class_counts}")
        return 1

    artifact = REPO / OUT
    if not artifact.is_file():
        print(f"FAILED:CNL-0101-probe1 artifact missing {OUT}")
        return 1
    doc = json.loads(artifact.read_text(encoding="utf-8"))
    recorded = {row["key"]: row["class"] for row in doc.get("key_map") or []}
    if recorded != mapping:
        print("FAILED:CNL-0101-probe1 independent map disagrees with artifact")
        print(f"  indep={mapping}")
        print(f"  artifact={recorded}")
        return 1
    if "SUCCESS:CNL-0101" not in artifact.read_text(encoding="utf-8"):
        print("FAILED:CNL-0101-probe1 sentinel absent")
        return 1
    print(
        "negative_control_vacuous_validator: Draft202012Validator.iter_errors "
        f"on invalid_preset.json (extra property fork_copied_artifacts) "
        f"returned {invalid_errors} errors; a vacuous schema would return 0."
    )
    print("SUCCESS:CNL-0101-probe1 schema 0/72 + independent 20-key recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
