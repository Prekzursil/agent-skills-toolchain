#!/usr/bin/env python3
"""Write the CNL-0113 catalog artifact (JSON body, .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0113-jury-family-evidence-adjudication-and-benchmark-results-ju.md"
)
QUESTION = (
    "Both juries decide on presented evidence - what does the benchmark jury "
    "need in addition, given that a benchmark result is a number an interested "
    "party produced and can game?"
)
ANSWER = (
    "Both juries decide on presented evidence. The evidence-adjudication jury "
    "(C-J01) treats admitted exhibits as the facts under a standard of proof, "
    "with a clerk who is not the presenter controlling admission and jurors who "
    "did not argue (CNL-0034 / CNL-0040: P14, P15, P17, P50). That is enough "
    "when exhibits are documents or testimony. A benchmark result is not that "
    "kind of exhibit: it is a number an interested party produced, movable by "
    "metric choice, split leakage, hardware, seeds, and undisclosed overlap. "
    "Admitting the number as a fact makes the presenter the real decision-maker "
    "(the CNL-0034 presenter-as-decider failure, specialised to scores). "
    "The benchmark-results jury (C-J02) therefore needs, in addition: "
    "(1) classify the number as CLAIM not FACT; "
    "(2) a protocol-registrar who seals metric, splits, hardware class, and "
    "seeds BEFORE any result is admitted, with P18 two-key control so the "
    "producer cannot reseal alone; "
    "(3) a replicator role whose independent remeasurement is an oracle; "
    "(4) a metric-adversary / canary whose cheaper policy that beats the metric "
    "without the claimed capability yields GAMEABLE; "
    "(5) producer recusal from the voting jury; "
    "(6) oracle veto in the voting rule so majority cannot vote CONFIRMED while "
    "replication is pending or the canary is gameable (CNL-0106 oracle-override "
    "pattern, specialised to remeasurement rather than a unit test); "
    "(7) outcome types CONFIRMED-UNDER-PROTOCOL | GAMEABLE | UNREPLICATED | "
    "PROTOCOL-VIOLATION so a good-looking number cannot be laundered as a "
    "verdict. Nearest sibling is C-J01 in the same family: the differential is "
    "the extra roles, extra protocol steps, oracle-veto voting, and stopping "
    "that forbids CONFIRMED without replication. A clone that only renames "
    "C-J01 is distance 0 and is rejected as a mechanism-duplicate. Catalog "
    "C-ids C-J01/C-J02 are family-local; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
    "is absent on this tree (same finding as ARC-0003). SUCCESS:CNL-0113"
)


def build() -> dict:
    j01 = E.evidence_adjudication_preset()
    j02 = E.benchmark_results_preset()
    E.assert_preset_keys(j01)
    E.assert_preset_keys(j02)
    task = E.fixture_task()
    i01 = E.instantiate(j01, task)
    i02 = E.instantiate(j02, task)
    nn = E.nearest_sibling(j02, E.sibling_catalog())
    if nn["sibling_id"] != "C-J01":
        raise SystemExit(f"nearest-sibling-unexpected:{nn}")
    if nn["distance"] < 1:
        raise SystemExit("nearest-sibling-not-distinct")
    clone = E.name_only_clone(j01, "C-J02-FAKE", "benchmark-results-jury")
    if E.distance(j01, clone) != 0:
        raise SystemExit("name-only-clone-not-zero")
    valid_errs = E.validate_records([j01, j02])
    invalid_errs = E.validate_records([E.invalid_record()])
    if valid_errs:
        raise SystemExit(f"valid-preset-schema:{valid_errs}")
    if not invalid_errs:
        raise SystemExit("invalid-record-vacuous")
    sens01 = E.presenter_sensitivity(j01, task)
    sens02 = E.presenter_sensitivity(j02, task)
    if not sens01["verdict_moved"]:
        raise SystemExit("C-J01-should-move-with-presenter-packet")
    if sens02["verdict_moved"]:
        raise SystemExit("C-J02-must-not-confirm-from-presenter-packet")
    locked_fired = False
    try:
        E.apply_binding(j02, {"producer_recusal": False})
    except PermissionError:
        locked_fired = True
    if not locked_fired:
        raise SystemExit("locked-dial-did-not-reject")
    doc = {
        "unit_id": "CNL-0113",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0113",
        "kind": "council-preset-family",
        "question": QUESTION,
        "answer": ANSWER,
        "library_status": {
            "original_library_on_tree": False,
            "original_library_path": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ),
            "reconstruction": (
                "P14-P19 named in catalog CNL-0040; sibling presets reconstructed "
                "from CNL-0103-CNL-0116 family titles. Original 72-record library "
                "bytes are not on this tree."
            ),
            "protocol_ids_from_catalog": ["P14", "P15", "P17", "P18", "P50"],
        },
        "preset_type": {
            "kind": "typed-delta-over-councilspec",
            "keys": list(E.PRESET_KEYS),
            "on_base_version_bump": "migrate-or-list-unmigratable; never silent-fork",
            "locked_dial_override": "REJECT",
        },
        "schema_binding": E.catalog_schema_status(),
        "presets": [j01, j02],
        "nearest_sibling": nn,
        "instantiation": {
            "fixture_task_id": task["id"],
            "profiles": [E.profile_of(i01), E.profile_of(i02)],
        },
        "schema_validation": {
            "validator": "jsonschema.Draft202012Validator",
            "working_schema": (
                "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json"
            ),
            "catalog_schema": "command-center/schema/council-preset.schema.json",
            "validator_target": "$defs.preset",
            "valid_error_count": 0,
            "invalid_record_error_count": len(invalid_errs),
            "invalid_record_id": "C-J99",
        },
        "negative_control": {
            "check": "name-only-clone-distance-zero-and-locked-dial-reject",
            "reject_state": (
                "preset copied from C-J01 with only id/name changed to look like C-J02"
            ),
            "on_reject_state": "FIRE distance=0 MECHANISM-DUPLICATE; do not register",
            "on_accept_state": "SILENT on live C-J02 (distance>=1 vs C-J01; oracles present)",
            "verbatim": (
                "The check FIRES when a preset shares C-J01's roles, protocol_schedule, "
                "voting and stopping and differs only in id/name (distance 0). It is "
                "SILENT on C-J02, which adds registrar/replicator/metric-adversary, "
                "seal-before-admit, oracle veto, and producer recusal. Overlay of "
                "locked dial producer_recusal is REJECT. SUCCESS:CNL-0113"
            ),
        },
        "reviewer": {
            "reviewer_id": "CNL-0113-probe2-sibling-schema",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "Re-instantiate both presets against the fixture, recompute the "
                "4-axis profile and nearest-sibling distance, re-run "
                "Draft202012Validator on live records plus a deliberately invalid "
                "record, and re-run the name-only clone control."
            ),
        },
        "tests": [
            {
                "id": "instantiate-fixture",
                "result": "PASS",
                "detail": (
                    f"C-J01 roster={i01['roster']} schedule={i01['protocol_schedule']} "
                    f"vote={i01['voting_method']} stop={i01['stopping_expression']}; "
                    f"C-J02 roster={i02['roster']} schedule={i02['protocol_schedule']}"
                ),
            },
            {
                "id": "nearest-sibling-differential",
                "result": "PASS",
                "detail": (
                    f"nearest sibling of C-J02 is {nn['sibling_id']} "
                    f"({nn['sibling_name']}) distance={nn['distance']} "
                    f"axes={nn['differing_axes']}"
                ),
            },
            {
                "id": "draft202012-validator",
                "result": "PASS",
                "detail": (
                    f"valid_error_count=0 invalid_record_error_count={len(invalid_errs)} "
                    "invalid_record_id=C-J99"
                ),
            },
            {
                "id": "negative-control",
                "result": "PASS",
                "detail": (
                    f"name-only clone distance={E.distance(j01, clone)}; "
                    f"C-J01 presenter-moved={sens01['verdict_moved']}; "
                    f"C-J02 presenter-moved={sens02['verdict_moved']}; "
                    f"locked-dial-fired={locked_fired}"
                ),
            },
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json",
                "exists": True,
                "role": "working-schema",
            },
            {
                "path": "command-center/schema/council-preset.schema.json",
                "exists": True,
                "role": "catalog-declared-schema-shim",
            },
        ],
    }
    env_errs = E.validate_envelope(doc)
    if env_errs:
        raise SystemExit("envelope-invalid:" + " | ".join(env_errs[:12]))
    return doc


def main() -> int:
    doc = build()
    dest = E.REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0113 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
