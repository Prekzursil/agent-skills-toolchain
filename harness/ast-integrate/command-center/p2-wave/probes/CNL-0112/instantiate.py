"""Instantiate a council preset (typed delta) against a fixture task."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Local copy: sibling CNL units race the shared schema file.
SCHEMA = HERE / "artifact.schema.json"
TASK = HERE / "fixtures/task.json"
SIBLING = HERE / "fixtures/sibling.json"

LIBRARY_CANDIDATES = (
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)

UNRESOLVABLE_CLASSES = frozenset(
    {
        "preference",
        "metaphysical",
        "unbounded_ever",
        "missing_resolution_source",
        "missing_resolution_date",
        "criterion_not_checkable",
    }
)

NON_EDITABLE_DIALS = (
    "scoring.primary_rule",
    "unresolvable_policy",
    "resolution.require_source_and_date",
    "topology.feedback_mode",
)

# Reconstructed base envelope. CNL-0001 / CNL-0101 artifacts are absent on this
# worktree; this is a local delta target, not a claim that those units delivered.
BASE_SPEC = {
    "id": "councilspec.v2.reconstructed-base",
    "version": "2.0.0",
    "source": "reconstructed-for-delta-application; CNL-0001 artifact absent on this worktree",
    "roles": [],
    "voting": {"method": "unanimous-or-record-dissent", "quorum": 1},
    "stopping": {
        "max_rounds": 4,
        "on_timeout": "halt",
        "expression": "rounds >= max_rounds",
    },
    "protocol_schedule": [],
}

CNL_0112_PRESET = {
    "id": "council.preset.forecast-elicit.proper-score",
    "kind": "typed_delta",
    "relation": "extends",
    "base_spec": {"id": BASE_SPEC["id"], "version": BASE_SPEC["version"]},
    "extends_c_ids": ["C-M01"],
    "extends_c_ids_basis": (
        "WORK-UNIT-CATALOG.json CNL-0002 evidence_requirement names C-M01 "
        "as a catalogued 20-key preset; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
        "bytes were not read on this worktree."
    ),
    "binds_protocols": ["P33", "P35", "P36"],
    "binds_protocols_basis": (
        "CNL-0043 names the FORECASTING family as P33 prediction-tournament, "
        "P34 scenario-planning, P35 reference-class-planning-poker, "
        "P36 calibration-tournament, P37 pairwise-comparison. This preset "
        "binds P33+P35+P36. P34 is optional. P37 is excluded: pairwise option "
        "ranking is not a probability forecast and cannot take a proper score."
    ),
    "roles": [
        {
            "id": "elicitor",
            "obligation": "emit only items that carry a named resolution source, date, and checkable criterion",
        },
        {
            "id": "forecaster",
            "obligation": "report probabilities; updates may use the full distribution and arguments, never the reported median alone",
        },
        {
            "id": "aggregator",
            "obligation": "combine credences with a logarithmic opinion pool, not a majority vote on a point forecast",
        },
        {
            "id": "resolution_clerk",
            "obligation": "ACCEPT or REJECT each item at emission; cannot be overridden to score an UNSCOREABLE item",
        },
        {
            "id": "calibration_analyst",
            "obligation": "score only SCOREABLE resolved items; keep an UNSCOREABLE tally that never enters the score",
        },
        {
            "id": "anti_herding_skeptic",
            "obligation": "flag variance collapse across Delphi rounds when the evidence hash is unchanged",
        },
    ],
    "voting": {
        "method": "logarithmic_opinion_pool",
        "quorum": 3,
        "note": "The forecast number is a pool of probabilities, not a role-majority.",
    },
    "stopping": {
        "max_rounds": 6,
        "expression": (
            "stop when every emitted item is SCOREABLE or UNSCOREABLE "
            "AND delphi_round >= 2 AND (delphi_round >= max_rounds "
            "OR herding_flag OR resolution_clerk.batch_closed)"
        ),
        "on_timeout": "close_batch_with_unscored_remainder_as_UNSCOREABLE",
        "on_unresolved": "UNSCOREABLE",
    },
    "protocol_schedule": ["P35", "P33", "P36"],
    "topology": {
        "id": "delphi-controlled-feedback",
        "from_unit": "CNL-0035",
        "feedback_mode": "full_distribution_and_arguments",
        "forbidden_feedback": "median_only",
        "reason": (
            "Median-only feedback produces regression to the reported median "
            "(herding), not genuine revision. Full distribution plus arguments "
            "is the feedback this preset returns. Detection of herding is a "
            "separate variance+evidence-hash check; distribution feedback does "
            "not by itself prove the panel is not herding."
        ),
    },
    "scoring": {
        "primary_rule": "logarithmic",
        "primary_rule_status": "strictly_proper",
        "secondary_rule": "brier",
        "secondary_rule_status": "strictly_proper_not_local",
        "rejected_rule": "linear_probability_score",
        "rejected_rule_status": "improper",
        "citation": (
            "Gneiting and Raftery 2007 JASA: Strictly Proper Scoring Rules, "
            "Prediction, and Estimation. Log is local and strictly proper; "
            "Brier is strictly proper and bounded; linear is not proper."
        ),
    },
    "resolution": {
        "require_source_and_date": True,
        "source_must_be_named": True,
        "date_format": "ISO-8601",
        "criterion_must_be_checkable": True,
    },
    "unresolvable_policy": "REJECT-UNSCOREABLE-at-emission",
    "unresolvable_disposition": "UNSCOREABLE",
    "calibration_alignment": {
        "from_unit": "CNL-0074",
        "deferred_resolution_remains_scoreable_without_session": True,
        "council_with_no_resolvable_outcome": "UNSCOREABLE",
        "unscoreable_never_counted_as_calibrated": True,
    },
    "editable_dials": [
        "stopping.max_rounds",
        "roles.forecaster_count",
        "scoring.report_secondary_brier",
        "protocol_schedule.include_P34",
    ],
    "non_editable_dials": list(NON_EDITABLE_DIALS),
    "default_binding": "FORECASTING",
    "on_base_bump": "migrate_or_list_unmigratable",
}


def library_on_disk() -> dict[str, Any]:
    found = [p.relative_to(REPO).as_posix() for p in LIBRARY_CANDIDATES if p.is_file()]
    return {
        "candidates": [p.relative_to(REPO).as_posix() for p in LIBRARY_CANDIDATES],
        "found": found,
        "on_this_worktree": bool(found),
        "presets_compared_from_disk": 0,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_item(item: dict) -> dict:
    reasons: list[str] = []
    if not item.get("resolution_source"):
        reasons.append("missing_resolution_source")
    if not item.get("resolution_date"):
        reasons.append("missing_resolution_date")
    if not item.get("resolution_criterion"):
        reasons.append("criterion_not_checkable")
    klass = str(item.get("criterion_class") or "")
    if klass in UNRESOLVABLE_CLASSES:
        reasons.append(klass)
    if reasons:
        return {
            "id": item.get("id"),
            "disposition": "REJECT",
            "score_class": "UNSCOREABLE",
            "reasons": reasons,
        }
    return {
        "id": item.get("id"),
        "disposition": "ACCEPT",
        "score_class": "SCOREABLE",
        "reasons": [],
        "resolution_source": item["resolution_source"],
        "resolution_date": item["resolution_date"],
        "resolution_criterion": item["resolution_criterion"],
    }


def apply_overrides(preset: dict, overrides: dict | None) -> dict:
    overrides = overrides or {}
    editable = set(preset.get("editable_dials") or [])
    non_editable = set(preset.get("non_editable_dials") or NON_EDITABLE_DIALS)
    for key in overrides:
        if key in non_editable or key not in editable:
            return {
                "accepted": False,
                "reason": "silent-override-of-non-editable-dial",
                "dial": key,
            }
    return {"accepted": True, "reason": "ok", "dial": None}


def _variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / n


def herding_flag(
    round1: list[float],
    round2: list[float],
    evidence_hash_1: str,
    evidence_hash_2: str,
) -> bool:
    if evidence_hash_1 != evidence_hash_2:
        return False
    v1 = _variance(round1)
    v2 = _variance(round2)
    return v1 > 0 and v2 <= 0.25 * v1


def instantiate(
    preset: dict,
    task: dict,
    overrides: dict | None = None,
) -> dict:
    gate = apply_overrides(preset, overrides)
    if not gate["accepted"]:
        return {
            "ok": False,
            "reject": gate,
            "task_id": task.get("id"),
            "preset_id": preset.get("id"),
        }
    classifications = [classify_item(it) for it in (task.get("items") or [])]
    accepted = [c for c in classifications if c["disposition"] == "ACCEPT"]
    rejected = [c for c in classifications if c["disposition"] == "REJECT"]
    roster_ids = [r["id"] for r in preset.get("roles") or []]
    evidence = "fixture-v1"
    eh = hashlib.sha256(evidence.encode("utf-8")).hexdigest()[:16]
    herding = herding_flag([0.2, 0.5, 0.8], [0.5, 0.5, 0.5], eh, eh)
    return {
        "ok": True,
        "task_id": task.get("id"),
        "preset_id": preset.get("id"),
        "roster_ids": roster_ids,
        "protocol_schedule": list(preset.get("protocol_schedule") or []),
        "voting": dict(preset.get("voting") or {}),
        "stopping": dict(preset.get("stopping") or {}),
        "scoring": dict(preset.get("scoring") or {}),
        "unresolvable_policy": preset.get("unresolvable_policy"),
        "classifications": classifications,
        "accepted_ids": [c["id"] for c in accepted],
        "rejected_ids": [c["id"] for c in rejected],
        "unscoreable_tally": len(rejected),
        "scoreable_tally": len(accepted),
        "herding_control_same_evidence_median_collapse": herding,
        "profile": {
            "roles": tuple(roster_ids),
            "voting": (preset.get("voting") or {}).get("method")
            or (preset.get("voting") or {}).get("rule"),
            "stopping": (preset.get("stopping") or {}).get("expression")
            or (preset.get("stopping") or {}).get("on_unresolved"),
            "protocol_schedule": tuple(preset.get("protocol_schedule") or []),
            "scoring": (preset.get("scoring") or {}).get("primary_rule"),
            "unresolvable_policy": preset.get("unresolvable_policy"),
        },
    }


def sibling_as_preset(raw: dict) -> dict:
    """Lift the transcribed catalog-class sibling into the instantiate shape."""
    roles = [{"id": r, "obligation": "catalog-class four-voice role"} for r in raw.get("roles") or []]
    stopping = dict(raw.get("stopping") or {})
    stopping.setdefault(
        "expression",
        f"rounds >= {stopping.get('max_rounds', 8)} OR unresolved -> {stopping.get('on_unresolved', 'BLOCKED')}",
    )
    return {
        "id": raw.get("id"),
        "kind": "typed_delta",
        "relation": "delta",
        "base_spec": {"id": "catalog-class-transcribed", "version": "unknown"},
        "extends_c_ids": ["C-M01"],
        "roles": roles,
        "voting": raw.get("voting") or {},
        "stopping": stopping,
        "protocol_schedule": raw.get("protocol_schedule") or [],
        "scoring": raw.get("scoring") or {"primary_rule": None},
        "unresolvable_policy": raw.get("unresolvable_policy") or "BLOCKED-on-unresolved",
        "editable_dials": ["stopping.max_rounds"],
        "non_editable_dials": list(NON_EDITABLE_DIALS),
        "default_binding": "catalog-class",
    }


PROFILE_AXES = (
    "roles",
    "voting",
    "stopping",
    "protocol_schedule",
    "scoring",
    "unresolvable_policy",
)


def differ_axes(a: dict, b: dict) -> list[str]:
    pa, pb = a["profile"], b["profile"]
    return [k for k in PROFILE_AXES if pa.get(k) != pb.get(k)]


def validator():
    import jsonschema

    schema = load_json(SCHEMA)
    return jsonschema.Draft202012Validator(schema)


def error_count(instance: dict) -> int:
    return sum(1 for _ in validator().iter_errors(instance))
