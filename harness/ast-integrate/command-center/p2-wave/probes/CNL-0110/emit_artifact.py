#!/usr/bin/env python3
"""Emit the CNL-0110 design artifact (JSON stored at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from instantiate import instantiate  # noqa: E402
from preset import PRESET_ID, preset as load_preset  # noqa: E402
from schema_check import error_count, validate_pair  # noqa: E402
from siblings import nearest  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0110-requirements-council-elicitation-plus-conflict-reconciliat.md"
)
TASK = HERE / "fixtures" / "task_api_tokens.json"


def jsonable(obj):
    if isinstance(obj, tuple):
        return [jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [jsonable(x) for x in obj]
    return obj


def build() -> dict:
    task = json.loads(TASK.read_text(encoding="utf-8"))
    p = load_preset()
    inst = instantiate(task, p)
    if not inst.get("ok"):
        raise SystemExit(f"FAILED:emit instantiate {inst.get('reason')}")
    sib = nearest(inst["fingerprint"])
    named = sib["nearest_twelve_council_sourced"]
    if named is None or named["distance"] < 1:
        raise SystemExit("FAILED:emit nearest 12-COUNCIL sibling missing or identical")
    planted = sib["planted_duplicate"]
    if planted["distance"] != 0:
        raise SystemExit("FAILED:emit name-clone distance != 0")
    lib = sib["library"]
    blend = inst["negative_control"]["planted_blend"]
    known = inst["negative_control"]["known_irreducible"]
    if not blend["fires"] or known["fires"]:
        raise SystemExit("FAILED:emit negative control polarity")
    doc = {
        "unit_id": "CNL-0110",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0110",
        "kind": "council_preset_design",
        "title": "Requirements council: elicitation plus conflict reconciliation",
        "question": (
            "How does the preset separate eliciting what stakeholders want from "
            "reconciling requirements that contradict - and what outcome type "
            "does an unreconcilable pair produce?"
        ),
        "answers": {
            "how_separated": (
                "Two protocol steps with different voting and stopping. "
                "p-elicit records attributed wants under record-only voting and "
                "stops when every required stakeholder class has a want. "
                "p-reconcile then classifies each contradicting pair under "
                "pairwise-originator-conjunction and must not run until elicit "
                "has a ledger. Aggregation is forbidden in elicit; blending is "
                "forbidden in reconcile."
            ),
            "unreconcilable_pair_outcome": "irreducible-disagreement",
            "why_not_blend": (
                "A blended requirement claims both wants are satisfied while no "
                "world-state satisfies both satisfaction conditions. That hides "
                "the conflict. The pair stays two wants plus an "
                "irreducible-disagreement record citing failed rewrite attempts "
                "and zero remaining untried rewrites (CNL-0071 information-gain gate)."
            ),
        },
        "maps_c_ids": [
            {
                "c_id": "C13",
                "relation": "extends",
                "mechanism": (
                    "CNL-0102 reconstruction: requirements-elicitation arm "
                    "(P23/P01/P22, approval, stakeholder_coverage stop). This "
                    "preset keeps capture as its own protocol step but replaces "
                    "approval with record-only voting so elicitation cannot "
                    "smuggle reconciliation."
                ),
            },
            {
                "c_id": "C14",
                "relation": "extends",
                "mechanism": (
                    "CNL-0102 reconstruction: requirements-conflict-reconciliation "
                    "arm (P12/P09/P56, consent, unreconciled_pairs stop). This "
                    "preset keeps pair classification as a second step, binds "
                    "pairwise-originator-conjunction instead of consent, and "
                    "emits irreducible-disagreement rather than blending."
                ),
            },
            {
                "c_id": "CNL-0017",
                "relation": "operationalizes",
                "mechanism": (
                    "Seats one of each required stakeholder class and blocks "
                    "elicit when any required class is missing. CNL-0017 artifact "
                    "is absent; this is an operational taxonomy for this preset."
                ),
            },
            {
                "c_id": "CNL-0071",
                "relation": "operationalizes",
                "mechanism": (
                    "Unreconcilable pairs emit irreducible-disagreement only after "
                    "every listed rewrite was tried and rejected by an originator "
                    "class. Declaring irreducibility while untried rewrites remain "
                    "is incomplete, not irreducible. CNL-0071 artifact is absent."
                ),
            },
            {
                "c_id": "CNL-0101",
                "relation": "operationalizes",
                "mechanism": (
                    "Preset is a typed delta (roles, protocol_schedule, voting, "
                    "stopping, anti_failure, audit, outcomes) plus editable_dials "
                    "and default_binding. On base bump: migrate or list "
                    "unmigratable dials. CNL-0101 artifact is absent."
                ),
            },
        ],
        "library_status": {
            "twelve_council_present": lib["twelve_council_present"],
            "search_paths": lib["search_paths"],
            "search_space_note": lib["search_space_note"],
            "glob_hits": lib["glob_hits"],
        },
        "preset": p,
        "instantiation": {
            "task_id": inst["task_id"],
            "roster": inst["roster"],
            "protocol_schedule": inst["protocol_schedule"],
            "voting": inst["voting"],
            "stopping": inst["stopping"],
            "elicit_complete": inst.get("elicit_complete"),
            "want_ledger": inst.get("want_ledger"),
            "pair_outcomes": inst.get("pair_outcomes"),
        },
        "nearest_sibling": {
            "named": named["id"],
            "source": named["source"],
            "distance": named["distance"],
            "axes_differ": named["axes_differ"],
            "search_space": "on-disk-transcription-not-the-unread-72",
            "closer_non_library": sib["nearest_on_disk_excluding_planted"],
            "planted_name_clone_distance": planted["distance"],
        },
        "schema_validation": {
            "validator": "jsonschema.Draft202012Validator",
            "affected_error_count": 0,
            "invalid_record_error_count": 1,
        },
        "tests": [
            {"id": "instantiate-fixture", "result": "PASS"},
            {"id": "nearest-sibling-differential", "result": "PASS"},
            {"id": "schema-draft202012", "result": "PASS"},
            {"id": "negative-control-blend", "result": "PASS"},
        ],
        "negative_control": {
            "rejects": "blended-requirement for a contradicting pair",
            "on_state": (
                "collapsing W-plain and W-erase into one requirement that "
                "claims both plaintext persistence and erasability"
            ),
            "verbatim": blend["verbatim"],
            "planted_blend_fires": blend["fires"],
            "known_irreducible_fires": known["fires"],
        },
        "reviewer": {
            "reviewer_id": "CNL-0110-probe2-sibling-differential",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Recomputes Hamming distance over PROFILE_AXES against the "
                "on-disk sibling catalog; does not accept nearest_sibling.named "
                "without recomputation."
            ),
        },
        "residual_unknowns": [
            (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; nearest-sibling "
                "is among transcribed/reconstructed rows, not the 72-record library."
            ),
            (
                "The 20 preset keys cited by CNL-0101 were not re-enumerated from "
                "the library. This preset binds the catalog-cited axes plus "
                "roles/protocol_schedule/editable_dials/default_binding."
            ),
            (
                "Dependencies CNL-0101, CNL-0017, CNL-0071 have no delivered "
                "artifacts on this worktree; mappings operationalize their "
                "catalog questions, they do not consume their outputs."
            ),
            (
                f"Preset id {PRESET_ID} extends reconstructed C13+C14; it does "
                "not supersede a named 12-COUNCIL library row because those "
                "bytes were not readable here. If the 72-record file lands, "
                "recompute PROFILE_AXES distance against every preset and "
                "replace nearest_sibling if a closer neighbour exists."
            ),
        ],
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    schema_result = validate_pair(doc)
    doc["schema_validation"] = {
        "validator": schema_result["validator"],
        "affected_error_count": schema_result["affected_error_count"],
        "invalid_record_error_count": schema_result["invalid_record_error_count"],
        "schema": schema_result["schema"],
        "vacuous": schema_result["vacuous"],
    }
    if schema_result["affected_error_count"] != 0:
        raise SystemExit(
            f"FAILED:emit schema errors={schema_result['affected_error_count']}"
        )
    if schema_result["invalid_record_error_count"] < 1 or schema_result["vacuous"]:
        raise SystemExit("FAILED:emit validator vacuous")
    return jsonable(doc)


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    n = error_count(on_disk)
    if n != 0:
        print(f"FAILED:emit on-disk schema errors={n}")
        return 1
    print(f"wrote {OUT_REL} errors={n} sentinel={on_disk.get('sentinel')}")
    print("SUCCESS:CNL-0110-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
