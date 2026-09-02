#!/usr/bin/env python3
"""Probe 2: nearest-sibling differential + Draft202012 schema + negative controls."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import composer as C  # noqa: E402

ARTIFACT = (
    REPO
    / "command-center/design/council/CNL-0116-general-purpose-auto-composed-council-preset-the-flagship.md"
)
# Catalog output_schema path is occupied by CNL-0107 ($defs.council_preset).
# This unit's executable contract is the unit-local schema below.
SCHEMA = HERE / "council-preset.schema.json"
SIBLING_LIB = HERE / "fixtures" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
TASKS = HERE / "fixtures" / "tasks.json"


def n_errors(validator: Draft202012Validator, instance) -> int:
    return sum(1 for _ in validator.iter_errors(instance))


def main() -> int:
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sib_lib = json.loads(SIBLING_LIB.read_text(encoding="utf-8"))
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    fail = False

    wrapper = Draft202012Validator(schema)
    rec_schema = schema["$defs"]["preset_record"]
    # Draft202012Validator needs a full schema object; wrap the def.
    record_validator = Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$id": schema["$id"] + "#preset_record",
            **rec_schema,
        }
    )

    valid_errors = n_errors(wrapper, doc)
    print(f"schema_wrapper_errors={valid_errors}")
    if valid_errors != 0:
        print("FAILED:CNL-0116-probe2 wrapper schema errors")
        fail = True

    rec_errors = 0
    for row in [doc["preset"], *sib_lib["presets"]]:
        n = n_errors(record_validator, row)
        rec_errors += n
        print(f"record id={row.get('id')} errors={n} keys={len(row.keys())}")
        if tuple(row.keys()) != C.TWENTY_KEYS:
            print(f"FAILED:CNL-0116-probe2 key set {row.get('id')} {list(row.keys())}")
            fail = True
    print(f"schema_record_errors_total={rec_errors}")
    if rec_errors != 0:
        print("FAILED:CNL-0116-probe2 preset records not valid")
        fail = True

    bad = deepcopy(doc["preset"])
    del bad["editable_dials"]
    bad_n = n_errors(record_validator, bad)
    print(f"deliberately_invalid_editable_dials_missing errors={bad_n}")
    if bad_n <= 0:
        print("FAILED:CNL-0116-probe2 validator vacuous (invalid accepted)")
        fail = True

    canonical = next(t for t in tasks if t["id"] == "T-PROD-GNG")
    inst = C.compose(canonical["text"])
    nearest = C.nearest_sibling(inst, sib_lib["presets"])
    print(
        json.dumps(
            {
                "nearest_named": nearest["nearest_id"],
                "integer_axes": nearest["distance"]["integer_axes"],
                "differed": nearest["distance"]["differed"],
                "name_only": nearest["distance"]["name_only"],
                "ranked_ids": [r["id"] for r in nearest["ranked"]],
            },
            sort_keys=True,
        )
    )
    if nearest["nearest_id"] != "C-M01":
        print(f"FAILED:CNL-0116-probe2 nearest {nearest['nearest_id']} != C-M01")
        fail = True
    if nearest["distance"]["name_only"] or nearest["distance"]["integer_axes"] < 2:
        print("FAILED:CNL-0116-probe2 not measurably distinct from nearest sibling")
        fail = True
    if doc.get("sibling", {}).get("nearest_named") != "C-M01":
        print("FAILED:CNL-0116-probe2 artifact sibling.nearest_named drift")
        fail = True

    # name-only mutant of the instantiated flagship
    mutant = deepcopy(inst)
    mutant["id"] = "C-GP01-RENAMED"
    mutant["name"] = "renamed-flagship"
    dmut = C.distance(inst, mutant)
    print(f"name_mutant name_only={dmut['name_only']} axes={dmut['integer_axes']}")
    if not dmut["name_only"]:
        print("FAILED:CNL-0116-probe2 name mutant should be a mechanism-duplicate")
        fail = True

    # missing-explanation both-states
    broken = deepcopy(inst)
    for e in broken["explanation"]:
        if e.get("dial") == "voting.rule":
            e["reason"] = ""
            break
    fired = C.check_integrity(broken)
    silent = C.check_integrity(inst)
    miss_ok = any(x == "missing-explanation:voting.rule" for x in fired)
    print(
        "negative_control verbatim: check_integrity FIRES "
        "missing-explanation:voting.rule on a composed instance whose "
        "explanation reason for voting.rule was deleted; the unmodified "
        f"instance is SILENT (errors={silent}). "
        f"fired={fired} miss_ok={miss_ok} silent_ok={silent == []}"
    )
    if not miss_ok or silent:
        print("FAILED:CNL-0116-probe2 missing-explanation both-states")
        fail = True

    if fail:
        print("FAILED:CNL-0116-probe2 sibling schema negative-control")
        return 1
    print(
        "SUCCESS:CNL-0116-probe2 nearest-sibling C-M01, schema 0 errors, "
        "invalid record fires, negative controls"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
