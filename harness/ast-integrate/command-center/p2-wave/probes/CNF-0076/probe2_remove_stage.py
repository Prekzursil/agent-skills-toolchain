#!/usr/bin/env python3
"""Named probe 2: remove-one-stage control (different field than probe 1).

Probe 1 reads recovered-output sha256. This probe mutates the fusion stage
set, re-runs decompose, and requires a NEW lost-capability issue plus a
schema-valid artifact. Intact fusion must stay silent on stage-removal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from workflow import (  # noqa: E402
    OMITTED_SOURCE_ID,
    REMOVED_STAGE_ID,
    capability_diff,
    metadata_only_mutant,
    remove_one_stage,
    remove_one_stage_control,
    run_analysis,
)

ART = REPO / "command-center/confirmation/CNF-0076-fusion-decomposition.json"
SCHEMA = REPO / "command-center/schema/lineage-report.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0076-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.validate(garbage, schema)
    except jsonschema.ValidationError:
        garbage_rejected = True
    else:
        print("FAILED:CNF-0076-probe2 schema accepts garbage")
        return 1

    analysis = run_analysis()
    fusion = analysis["fusion"]
    sources = analysis["sources"]
    control = remove_one_stage_control(fusion, sources, REMOVED_STAGE_ID)
    if not control["detected"]:
        print("FAILED:CNF-0076-probe2 control did not detect stage removal")
        print(json.dumps(control, indent=2, default=str)[:3000])
        return 1
    if not control["intact_does_not_fire"]:
        print("FAILED:CNF-0076-probe2 intact fusion fired removal issue")
        return 1
    if not control["mutilated_fires"]:
        print("FAILED:CNF-0076-probe2 mutilated fusion silent")
        return 1
    if control["mutilated_recovered_stage_count"] != control["intact_recovered_stage_count"] - 1:
        print("FAILED:CNF-0076-probe2 recovered stage count did not drop by 1")
        return 1

    mutilated = remove_one_stage(fusion, REMOVED_STAGE_ID)
    mut_diff = capability_diff(mutilated, sources)
    if not any(item.get("reason") == "stage-missing-after-decompose" for item in mut_diff["lost_capabilities"]):
        print("FAILED:CNF-0076-probe2 missing-stage reason absent")
        return 1

    meta = metadata_only_mutant(fusion, OMITTED_SOURCE_ID)
    meta_diff = capability_diff(meta, sources)
    if not any(item.get("source_id") == OMITTED_SOURCE_ID for item in meta_diff["lost_capabilities"]):
        print("FAILED:CNF-0076-probe2 metadata-only mutant cleared the loss")
        return 1

    recorded = doc.get("remove_one_stage_control") or {}
    if recorded.get("detected") is not True:
        print("FAILED:CNF-0076-probe2 artifact control not detected")
        return 1
    if recorded.get("removed_stage_id") != REMOVED_STAGE_ID:
        print("FAILED:CNF-0076-probe2 artifact stage id drift", recorded.get("removed_stage_id"))
        return 1

    both = analysis["lost_capability_both_states"]
    if not both["detector_silent_on_complete"] or not both["detector_fires_on_omission"]:
        print("FAILED:CNF-0076-probe2 lost-capability both-states failed")
        print(json.dumps(both, indent=2))
        return 1

    out = {
        "probe": "probe2-remove-one-stage",
        "unit_id": "CNF-0076",
        "removed_stage_id": REMOVED_STAGE_ID,
        "detected": True,
        "intact_does_not_fire": True,
        "mutilated_fires": True,
        "schema_valid": True,
        "garbage_rejected": garbage_rejected,
        "metadata_only_still_lost": True,
        "new_issues": control["new_issues"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"removed={REMOVED_STAGE_ID} detected=True "
        f"intact_silent=True mutilated_fires=True garbage_rejected={garbage_rejected}"
    )
    print("SUCCESS:CNF-0076-probe2 remove-one-stage control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
