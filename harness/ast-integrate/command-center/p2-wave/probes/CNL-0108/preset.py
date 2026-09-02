#!/usr/bin/env python3
"""Incident-lifecycle family: typed deltas, instantiate, floor, sibling distance."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_FIXTURE = HERE / "fixtures" / "reconstructed_catalog.json"
TASK_FIXTURE = HERE / "fixtures" / "task.json"
CATALOG_SCHEMA_REL = "command-center/schema/council-preset.schema.json"
SCHEMA_PATH = REPO / CATALOG_SCHEMA_REL
RECORD_SCHEMA_PATH = HERE / "fixtures" / "preset.record.schema.json"
OUT_REL = (
    "command-center/design/council/"
    "CNL-0108-incident-lifecycle-family-live-war-room-and-retrospective-.md"
)

PRESET_KEYS = (
    "id",
    "name",
    "family",
    "artifact_type",
    "base_spec_ref",
    "base_spec_version",
    "default_binding",
    "protocol_schedule",
    "roster",
    "voting",
    "consensus",
    "stopping",
    "anti_failure",
    "audit",
    "editable_dials",
    "outcome_type",
    "evidence_contract",
    "floor_policy",
    "clock",
    "supersedes",
)
KEY_CLASS = {
    "id": "metadata",
    "name": "metadata",
    "family": "metadata",
    "artifact_type": "metadata",
    "audit": "metadata",
    "supersedes": "metadata",
    "base_spec_ref": "base",
    "base_spec_version": "base",
    "default_binding": "delta",
    "protocol_schedule": "delta",
    "roster": "delta",
    "voting": "delta",
    "consensus": "delta",
    "stopping": "delta",
    "anti_failure": "delta",
    "editable_dials": "delta",
    "outcome_type": "delta",
    "evidence_contract": "delta",
    "floor_policy": "delta",
    "clock": "delta",
}
PROFILE_AXES = (
    "roster",
    "protocols",
    "voting",
    "stopping",
    "floor_may_skip",
    "clock",
    "evidence_order",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def library_present() -> dict[str, bool]:
    return {
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": (
            REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ).is_file(),
        "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": (
            REPO / "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ).is_file(),
    }


def load_sibling_catalog() -> list[dict]:
    doc = load_json(CATALOG_FIXTURE)
    presets = doc.get("presets") or []
    if not isinstance(presets, list) or len(presets) < 2:
        raise RuntimeError("reconstructed sibling catalog is empty")
    return presets


def load_task() -> dict:
    return load_json(TASK_FIXTURE)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def family_presets() -> list[dict]:
    live = {
        "id": "C-IL-LIVE",
        "name": "Live war-room (act now, evidence later)",
        "family": "incident-lifecycle",
        "artifact_type": "council-preset",
        "base_spec_ref": "CouncilSpec/v2",
        "base_spec_version": "2.0.0",
        "default_binding": {"protocol_ids": ["P47", "P51"]},
        "protocol_schedule": [
            {
                "order": 1,
                "protocol_id": "P47",
                "purpose": "Contain harm under a live operational clock",
            },
            {
                "order": 2,
                "protocol_id": "P51",
                "purpose": "Timeboxed spike only if containment needs a probe",
            },
        ],
        "roster": [
            {
                "id": "Incident-Commander",
                "obligation": "Issue a containment action within the live clock",
                "permission": "Override majority on containment only",
                "right": "Skip the deliberation floor for containment, never for cause",
            },
            {
                "id": "Mitigator",
                "obligation": "Apply the commanded mitigation and report blast radius",
                "permission": "Propose a narrower containment",
                "right": "Refuse a mitigation with no rollback",
            },
            {
                "id": "Scribe",
                "obligation": "Log every action and every deferred hypothesis",
                "permission": "Pause speech for a log line",
                "right": "Refuse an unlogged containment",
            },
            {
                "id": "Skeptic",
                "obligation": "Name the harm of acting on a wrong hypothesis",
                "permission": "Force a dissent line onto the transcript",
                "right": "Block a causal verdict while the floor is skipped",
            },
        ],
        "voting": {"method": "commander-decides-with-dissent-record", "quorum": 1},
        "consensus": {
            "reducer": "commander-action-plus-dissent",
            "local_completion_forbidden": True,
        },
        "stopping": {
            "expr": {
                "op": "OR",
                "args": [
                    {"var": "containment_declared", "eq": True},
                    {
                        "op": "AND",
                        "args": [
                            {"var": "elapsed_minutes", "gte": 30},
                            {"var": "mitigation_in_place", "eq": True},
                        ],
                    },
                ],
            },
            "on_timeout": "contain-then-handoff-to-retrospective",
            "max_rounds": 3,
        },
        "anti_failure": {
            "on_split": "commander-acts-dissent-recorded",
            "no_silent_average": True,
        },
        "audit": {"persist_transcript": True, "hash_inputs": True},
        "editable_dials": ["stopping.max_rounds", "clock.containment_minutes"],
        "outcome_type": "containment-action",
        "evidence_contract": {
            "order": "act-now-evidence-later",
            "unevidenced_cause": "deferred-to-retrospective",
        },
        "floor_policy": {
            "min_rounds": 2,
            "min_independent_briefs": 2,
            "min_evidence": 1,
            "may_skip_minimum_deliberation": True,
            "skip_scope": "containment-action-only",
            "ceiling_max_rounds": 3,
        },
        "clock": {"kind": "live-operational", "action_pressure": True},
        "supersedes": ["C-ER47", "P47"],
    }
    retro = {
        "id": "C-IL-RETRO",
        "name": "Retrospective root-cause / postmortem (evidence first)",
        "family": "incident-lifecycle",
        "artifact_type": "council-preset",
        "base_spec_ref": "CouncilSpec/v2",
        "base_spec_version": "2.0.0",
        "default_binding": {"protocol_ids": ["P44", "P38", "P40", "P42"]},
        "protocol_schedule": [
            {
                "order": 1,
                "protocol_id": "P44",
                "purpose": "Walk the 5-whys chain as the causal spine",
            },
            {
                "order": 2,
                "protocol_id": "P38",
                "purpose": "Score competing hypotheses instead of a single story",
            },
            {
                "order": 3,
                "protocol_id": "P40",
                "purpose": "Quality-of-information check on every cited source",
            },
            {
                "order": 4,
                "protocol_id": "P42",
                "purpose": "Map the surviving argument so a skipped premise is visible",
            },
        ],
        "roster": [
            {
                "id": "Facilitator",
                "obligation": "Hold the floor until min rounds, briefs and evidence exist",
                "permission": "Reorder protocols inside the schedule",
                "right": "Refuse any floor skip",
            },
            {
                "id": "Evidence-Clerk",
                "obligation": "Reject a cause that has no cited evidence",
                "permission": "Return a why-link for more sources",
                "right": "Veto an unevidenced close even under majority",
            },
            {
                "id": "Causal-Analyst",
                "obligation": "Draft each why-link with a cited source",
                "permission": "Add a competing hypothesis",
                "right": "Demand ACH scoring before close",
            },
            {
                "id": "Skeptic",
                "obligation": "Name the strongest alternative cause",
                "permission": "Challenge source quality",
                "right": "Attach a minority report",
            },
            {
                "id": "Domain-Owner",
                "obligation": "Confirm operational facts without deciding cause",
                "permission": "Correct a factual error",
                "right": "Refuse blame-as-cause language",
            },
        ],
        "voting": {"method": "evidence-adjudicated-majority", "quorum": 3},
        "consensus": {
            "reducer": "clerk-veto-then-majority",
            "local_completion_forbidden": True,
        },
        "stopping": {
            "expr": {
                "op": "AND",
                "args": [
                    {"var": "each_why_has_evidence", "eq": True},
                    {"var": "competing_hypotheses_scored", "eq": True},
                ],
            },
            "on_timeout": "BLOCKED-incomplete-causal-record",
            "max_rounds": 16,
        },
        "anti_failure": {
            "on_split": "minority-report-mandatory",
            "no_silent_average": True,
        },
        "audit": {"persist_transcript": True, "hash_inputs": True},
        "editable_dials": [
            "floor_policy.min_rounds",
            "floor_policy.min_evidence",
            "stopping.max_rounds",
        ],
        "outcome_type": "evidenced-causal-record",
        "evidence_contract": {
            "order": "evidence-first",
            "unevidenced_cause": "rejected",
        },
        "floor_policy": {
            "min_rounds": 3,
            "min_independent_briefs": 3,
            "min_evidence": 3,
            "may_skip_minimum_deliberation": False,
            "skip_scope": "none",
            "ceiling_max_rounds": 16,
        },
        "clock": {
            "kind": "retrospective-no-action-pressure",
            "action_pressure": False,
        },
        "supersedes": ["C-TC44", "P44"],
    }
    return [live, retro]


def profile(preset: dict) -> dict:
    return {
        "roster": tuple(sorted(r["id"] for r in preset["roster"])),
        "protocols": tuple(step["protocol_id"] for step in preset["protocol_schedule"]),
        "voting": preset["voting"]["method"],
        "stopping": canonical(preset["stopping"]["expr"]),
        "floor_may_skip": bool(
            preset["floor_policy"]["may_skip_minimum_deliberation"]
        ),
        "clock": preset["clock"]["kind"],
        "evidence_order": preset["evidence_contract"]["order"],
    }


def axis_diffs(a: dict, b: dict) -> list[str]:
    pa, pb = profile(a), profile(b)
    return [k for k in PROFILE_AXES if pa[k] != pb[k]]


def protocol_overlap(a: dict, b: dict) -> int:
    pa = {step["protocol_id"] for step in a["protocol_schedule"]}
    pb = {step["protocol_id"] for step in b["protocol_schedule"]}
    return len(pa & pb)


def distance(a: dict, b: dict) -> int:
    """Hamming on profile axes, minus bound-protocol overlap.

    Overlap is the measurable tie-break: a sibling that binds a shared
    P-id is nearer than one that only shares a review-shaped roster.
    """
    return len(axis_diffs(a, b)) * 10 - protocol_overlap(a, b)


def nearest_sibling(preset: dict, catalog: list[dict]) -> tuple[dict, int, list[str]]:
    best: dict | None = None
    best_key: tuple | None = None
    best_diffs: list[str] = []
    supersedes = set(preset.get("supersedes") or [])
    for sib in catalog:
        if sib.get("id") == preset.get("id"):
            continue
        diffs = axis_diffs(preset, sib)
        d = distance(preset, sib)
        key = (d, 0 if sib.get("id") in supersedes else 1, str(sib.get("id")))
        if best_key is None or key < best_key:
            best, best_key, best_diffs = sib, key, diffs
    if best is None:
        raise RuntimeError("no sibling catalog to compare")
    return best, distance(preset, best), best_diffs


def instantiate(preset: dict, task: dict) -> dict:
    """Bind a preset to a fixture task. Profile is a function of the preset, not the name."""
    roles = [r["id"] for r in preset["roster"]]
    schedule = [
        {"order": s["order"], "protocol_id": s["protocol_id"], "purpose": s["purpose"]}
        for s in preset["protocol_schedule"]
    ]
    return {
        "task_id": task.get("id"),
        "preset_id": preset["id"],
        "roster": roles,
        "protocol_schedule": schedule,
        "voting_method": preset["voting"]["method"],
        "stopping_expression": preset["stopping"]["expr"],
        "stopping_on_timeout": preset["stopping"]["on_timeout"],
        "floor_may_skip": preset["floor_policy"]["may_skip_minimum_deliberation"],
        "skip_scope": preset["floor_policy"]["skip_scope"],
        "clock": preset["clock"]["kind"],
        "evidence_order": preset["evidence_contract"]["order"],
        "outcome_type": preset["outcome_type"],
        "harm_continuing_at_bind": bool(task.get("harm_continuing")),
    }


def floors_met(preset: dict, state: dict) -> bool:
    floor = preset["floor_policy"]
    return (
        int(state.get("rounds") or 0) >= int(floor["min_rounds"])
        and int(state.get("independent_briefs") or 0)
        >= int(floor["min_independent_briefs"])
        and int(state.get("evidence_items") or 0) >= int(floor["min_evidence"])
    )


def _leaf_holds(node: dict, state: dict) -> bool:
    if "var" in node:
        val = state.get(node["var"])
        if "eq" in node:
            return val == node["eq"]
        if "gte" in node:
            try:
                return float(val) >= float(node["gte"])
            except (TypeError, ValueError):
                return False
        return False
    op = node.get("op")
    args = node.get("args") or []
    held = [_leaf_holds(a, state) if isinstance(a, dict) else False for a in args]
    if op == "AND":
        return all(held) if held else False
    if op == "OR":
        return any(held)
    if op == "NOT":
        return not held[0] if held else False
    return False


def stop_satisfied(preset: dict, state: dict) -> bool:
    return _leaf_holds(preset["stopping"]["expr"], state)


def apply_floor(preset: dict, state: dict) -> dict:
    """CNL-0077: floors outrank stop, unless this preset's skip_scope covers the action."""
    satisfied = stop_satisfied(preset, state)
    met = floors_met(preset, state)
    action = str(state.get("action") or "")
    ceiling = int(preset["floor_policy"]["ceiling_max_rounds"])
    rounds = int(state.get("rounds") or 0)
    hung = rounds >= ceiling
    skip_ok = bool(preset["floor_policy"]["may_skip_minimum_deliberation"])
    scope = preset["floor_policy"]["skip_scope"]
    skip_covers = skip_ok and scope == "containment-action-only" and action == "containment"
    if satisfied and met:
        return {
            "stop": True,
            "floor_blocked": False,
            "floor_skip_used": False,
            "hung": False,
            "audit": "STOP-AND-FLOOR-MET",
        }
    if satisfied and skip_covers and not met:
        return {
            "stop": True,
            "floor_blocked": False,
            "floor_skip_used": True,
            "hung": False,
            "audit": "FLOOR-SKIP-CONTAINMENT-ONLY",
        }
    if satisfied and not met:
        return {
            "stop": False,
            "floor_blocked": True,
            "floor_skip_used": False,
            "hung": hung,
            "audit": "FLOOR-BLOCKS-SATISFIED-STOP",
        }
    if hung:
        return {
            "stop": False,
            "floor_blocked": False,
            "floor_skip_used": False,
            "hung": True,
            "audit": "CEILING-REACHED-NO-HANG",
        }
    return {
        "stop": False,
        "floor_blocked": False,
        "floor_skip_used": False,
        "hung": False,
        "audit": "CONTINUE",
    }


def reject_non_editable_override(preset: dict, proposed: dict) -> dict:
    """A silent override of a non-editable dial is rejected (CNL-0101 control)."""
    allowed = set(preset.get("editable_dials") or [])
    violations = []
    if proposed.get("floor_policy", {}).get("may_skip_minimum_deliberation") != preset[
        "floor_policy"
    ]["may_skip_minimum_deliberation"]:
        if "floor_policy.may_skip_minimum_deliberation" not in allowed:
            violations.append("floor_policy.may_skip_minimum_deliberation")
    if proposed.get("evidence_contract", {}).get("order") != preset["evidence_contract"][
        "order"
    ]:
        if "evidence_contract.order" not in allowed:
            violations.append("evidence_contract.order")
    return {"rejected": bool(violations), "violations": violations}


def name_only_clone(preset: dict, new_id: str, new_name: str) -> dict:
    clone = copy.deepcopy(preset)
    clone["id"] = new_id
    clone["name"] = new_name
    return clone


def mechanism_duplicate(a: dict, b: dict) -> bool:
    return len(axis_diffs(a, b)) == 0 and a.get("id") != b.get("id")


def load_executable_schema() -> dict:
    """Prefer catalog $defs.preset if present; else the unit-local record schema.

    command-center/schema/council-preset.schema.json is a generated
    generic_report shim with no $defs.preset. Rewriting that shared file
    is the same-fingerprint structural fail; this unit parks that path
    and validates records locally.
    """
    catalog = load_json(SCHEMA_PATH)
    defs = catalog.get("$defs") if isinstance(catalog, dict) else None
    if isinstance(defs, dict) and "preset" in defs:
        return catalog
    return load_json(RECORD_SCHEMA_PATH)


def preset_schema_body(schema: dict | None = None) -> dict:
    schema = schema if schema is not None else load_executable_schema()
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    if not isinstance(defs, dict) or "preset" not in defs:
        raise RuntimeError("executable schema missing $defs.preset")
    return {
        "$schema": schema.get(
            "$schema", "https://json-schema.org/draft/2020-12/schema"
        ),
        "$defs": defs,
        **defs["preset"],
    }


def schema_errors(instance: dict, schema: dict | None = None) -> list[str]:
    from jsonschema import Draft202012Validator

    body = preset_schema_body(schema)
    validator = Draft202012Validator(body)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def envelope_errors(instance: dict) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = load_executable_schema()
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def who_may_skip(presets: list[dict]) -> dict:
    skippers = [
        p["id"]
        for p in presets
        if p["floor_policy"]["may_skip_minimum_deliberation"]
    ]
    holders = [
        p["id"]
        for p in presets
        if not p["floor_policy"]["may_skip_minimum_deliberation"]
    ]
    return {
        "may_skip": skippers,
        "must_hold_floor": holders,
        "answer": (
            "Only the live war-room preset may skip the minimum deliberation "
            "floor, and only for containment actions. The retrospective "
            "preset must hold the floor; a satisfied stop under an unmet "
            "floor is blocked and audited."
        ),
    }
