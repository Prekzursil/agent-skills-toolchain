#!/usr/bin/env python3
"""Probe 2: schema + nearest-sibling differential + negative controls.

Uses jsonschema Draft202012Validator. Sibling comparison is against ON-DISK
reconstructions; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _jsonschema_boot  # noqa: E402

_jsonschema_boot.boot()
from jsonschema.validators import Draft202012Validator  # noqa: E402

import family as F  # noqa: E402

MIN_SIBLING = 3
EXPERT_LABEL = "Adopt expert recommendation: raise list price 12% and drop the public SLO"


def schema_errors(validator: Draft202012Validator, record: dict) -> list[str]:
    return [
        f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(record)
    ]


def main() -> int:
    schema = json.loads(F.SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    presets = F.family_presets()
    per_record = []
    total = 0
    for preset in presets:
        errs = schema_errors(validator, preset)
        per_record.append({"id": preset["id"], "error_count": len(errs), "errors": errs})
        total += len(errs)
        if errs:
            print(f"FAILED:CNL-0114-probe2 schema {preset['id']} errors={errs}")
            return 1
    if total != 0:
        print(f"FAILED:CNL-0114-probe2 expected 0 schema errors, got {total}")
        return 1

    mutant = copy.deepcopy(presets[0])
    mutant["id"] = 0
    mutant["delta"] = "not-an-object"
    mutant_errs = schema_errors(validator, mutant)
    if not mutant_errs:
        print("FAILED:CNL-0114-probe2 schema mutant produced 0 errors (vacuous validator)")
        return 1

    siblings = F.load_siblings()
    if len(siblings) < 2:
        print("FAILED:CNL-0114-probe2 sibling library too small")
        return 1
    nearest_rows = []
    for preset in presets:
        row = F.nearest_sibling(preset, siblings)
        if row["duplicates"]:
            print(f"FAILED:CNL-0114-probe2 mechanism-duplicate {row}")
            return 1
        nd = row["nearest_distinct"]
        if nd is None:
            print(f"FAILED:CNL-0114-probe2 no distinct sibling for {preset['id']}")
            return 1
        if nd["distance"] < MIN_SIBLING:
            print(
                f"FAILED:CNL-0114-probe2 nearest sibling distance {nd['distance']} "
                f"< {MIN_SIBLING} for {preset['id']} vs {nd['id']}"
            )
            return 1
        nearest_rows.append(
            {
                "preset_id": preset["id"],
                "nearest_sibling_id": nd["id"],
                "distance": nd["distance"],
                "library_source": "on-disk-reconstruction-not-72-record-library",
            }
        )

    clone = F.name_only_clone(
        presets[0],
        "council.preset.multi-interest.negotiation.RENAMED",
        "Renamed negotiation (name-only clone)",
    )
    clone_dist = F.distance(
        F.profile_of_preset(presets[0]), F.profile_of_preset(clone)
    )
    if clone_dist != 0:
        print(f"FAILED:CNL-0114-probe2 name-only clone distance {clone_dist} != 0")
        return 1

    locked_fired = False
    try:
        F.apply_operator_overlay(presets[0], {"voting.method": "majority-rubric"})
    except F.LockedDialError:
        locked_fired = True
    if not locked_fired:
        print("FAILED:CNL-0114-probe2 locked-dial overlay was accepted")
        return 1
    # Known-good overlay: an editable dial.
    F.apply_operator_overlay(presets[0], {"stopping.max_rounds": 9})

    good_ballot = [
        "keep public SLO, raise price 4%",
        "drop public SLO, keep price",
        "keep both, shrink partner discount",
    ]
    bad_ballot = good_ballot + [EXPERT_LABEL]
    silent = F.lay_ballot_steering(good_ballot, EXPERT_LABEL)
    fired = F.lay_ballot_steering(bad_ballot, EXPERT_LABEL)
    if silent["fires"] or not fired["fires"]:
        print("FAILED:CNL-0114-probe2 lay steering both-states failed")
        return 1

    adv = next(p for p in presets if p["id"].endswith("adversarial-collaboration"))
    split_bad = F.split_verdict_fault("split-verdict", False, adv)
    split_good = F.split_verdict_fault("shared-test-result", True, adv)
    if not split_bad["fires"] or split_good["fires"]:
        print("FAILED:CNL-0114-probe2 split-verdict both-states failed")
        return 1

    fake_med = F.name_only_clone(
        presets[0],
        "council.preset.multi-interest.mediation.FAKE",
        "Mediation in name only",
    )
    med_fire = F.mediation_without_mediator(fake_med)
    med_ok = F.mediation_without_mediator(presets[1])
    if not med_fire["fires"] or med_ok["fires"]:
        print("FAILED:CNL-0114-probe2 mediation-name both-states failed")
        return 1

    report = {
        "unit": "CNL-0114",
        "probe": "probe2_schema_sibling_control",
        "schema_path": str(F.SCHEMA_PATH.relative_to(F.HERE.parents[3])).replace("\\", "/"),
        "schema_error_count": total,
        "records_validated": len(presets),
        "mutant_error_count": len(mutant_errs),
        "mutant_errors_head": mutant_errs[:4],
        "nearest_siblings": nearest_rows,
        "library_status": F.library_status(),
        "negative_controls": {
            "name_only_clone_distance": clone_dist,
            "name_only_clone_rejected_as_distinct": clone_dist == 0,
            "locked_dial_overlay_rejected": locked_fired,
            "lay_steering_silent_on_good": not silent["fires"],
            "lay_steering_fires_on_expert_default": fired["fires"],
            "split_verdict_fires_on_bad": split_bad["fires"],
            "split_verdict_silent_on_locked_shared_test": not split_good["fires"],
            "mediation_name_without_mediator_fires": med_fire["fires"],
            "true_mediation_silent": not med_ok["fires"],
        },
        "negative_control_verbatim": (
            "The sibling-distinctness check REJECTS a preset whose profile matches "
            "another record on every axis except id/name (a rename). The locked-dial "
            "check REJECTS an operator overlay of voting.method, which is not in "
            "editable_dials. The lay-panel steering check FIRES when the expert's "
            "recommended label is a ballot option and is SILENT when it is absent. "
            "The adversarial-collaboration check FIRES on claimed outcome "
            "split-verdict and is SILENT on a locked shared-test-result. The "
            "mediation check FIRES when the id/name says mediation but "
            "third_party.kind is not mediator."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"schema_errors={total} mutant_errors={len(mutant_errs)} "
        f"nearest={nearest_rows[0]['nearest_sibling_id']} "
        f"d={nearest_rows[0]['distance']}"
    )
    print("SUCCESS:CNL-0114-probe2 schema sibling negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
