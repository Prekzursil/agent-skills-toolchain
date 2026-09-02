"""Detectors used by named probes: build-bias, rationale completeness, schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from fixtures import ADOPTION_GOAL, LOOKS_RIGHT_OP, UNCOVERED_GOAL
from forge import FORGE_INPUT_INVALID, KIND_COST, forge

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Catalog path exists as a generated $ref shim. jsonschema 4.10.3 on this
# box follows that $ref over HTTPS to ast-integrate.invalid (NameResolutionError).
# Discrimination lives in the local contract (same pivot as WFA-0143).
CATALOG_SCHEMA = REPO / "command-center/schema/foundry-artifact.schema.json"
LOCAL_SCHEMA = HERE / "artifact.schema.json"
ART = (
    REPO
    / "command-center/foundry/WFA-0144-workflow-forge-mechanism-decomposition-and-synthesis.json"
)


def forge_schema() -> dict[str, Any]:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))


def schema_rejects_garbage() -> bool:
    validator = jsonschema.Draft202012Validator(forge_schema())
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "WFA-0144", "state": "SUCCESS"},
        {"blob": "x" * 2000},
    )
    return all(list(validator.iter_errors(g)) for g in garbage)


def schema_accepts(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    validator = jsonschema.Draft202012Validator(forge_schema())
    errors = [e.message for e in validator.iter_errors(doc)]
    return not errors, errors


def rationale_complete(result: dict[str, Any]) -> dict[str, Any]:
    text = str(result.get("rationale") or "")
    winner = result.get("winner") or {}
    missing: list[str] = []
    if winner.get("variant_id") not in text:
        missing.append(f"winner:{winner.get('variant_id')}")
    for v in result.get("rejected") or []:
        vid = v.get("variant_id")
        if vid not in text:
            missing.append(f"rejected:{vid}")
        score = f"{float(v.get('measured_score')):.4f}"
        if score not in text:
            missing.append(f"score:{vid}")
        if not str(v.get("why_rejected") or ""):
            missing.append(f"why:{vid}")
    return {"ok": not missing, "missing": missing}


def strip_rejected_rationale(result: dict[str, Any]) -> dict[str, Any]:
    """Over-claim mutant: keep the winner line, drop every REJECTED line."""
    mutant = dict(result)
    lines = [
        ln
        for ln in str(result.get("rationale") or "").splitlines()
        if not ln.startswith("REJECTED ")
    ]
    mutant["rationale"] = "\n".join(lines) + "\n"
    return mutant


def build_bias_verdict(result: dict[str, Any]) -> dict[str, Any]:
    winner = result.get("winner") or {}
    rejected = result.get("rejected") or []
    build = next(
        (v for v in rejected if v.get("variant_id") == "BUILD:from-scratch"), None
    )
    vendor = next(
        (v for v in rejected if v.get("variant_id") == "ADOPT:wf.vendor-locked-etl"),
        None,
    )
    reasons: list[str] = []
    if winner.get("kind") != "ADOPT":
        reasons.append(f"winner-kind:{winner.get('kind')}")
    sources = (winner.get("source_candidate_ids") or []) or (
        (winner.get("workflow") or {}).get("source_candidate_ids") or []
    )
    if "wf.json-ingest-v3" not in sources:
        reasons.append(f"winner-source:{sources}")
    if build is None:
        reasons.append("build-not-benchmarked")
    elif float(build["measured_score"]) >= float(winner["measured_score"]):
        reasons.append("build-not-losing")
    if vendor is None:
        reasons.append("vendor-twin-absent")
    elif vendor.get("ineligible_reason") != "license-incompatible":
        reasons.append("vendor-twin-not-license-rejected")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "winner_kind": winner.get("kind"),
        "winner_id": winner.get("variant_id"),
        "build_score": None if build is None else build.get("measured_score"),
        "adopt_score": winner.get("measured_score"),
    }


def zero_build_cost_mutant_fires() -> dict[str, Any]:
    """Load-bearing check: dropping KIND_COST['BUILD'] must change the winner.

    If ADOPT still wins at BUILD cost 0, the control is not the named
    penalty (probe must fail so we do not ship a vacuous detector).
    """
    honest = forge(ADOPTION_GOAL)
    mutant_cost = dict(KIND_COST)
    mutant_cost["BUILD"] = 0.0
    mutant = forge(ADOPTION_GOAL, kind_cost=mutant_cost)
    honest_kind = (honest.get("winner") or {}).get("kind")
    mutant_kind = (mutant.get("winner") or {}).get("kind")
    detector_on_honest = honest_kind != "BUILD"
    detector_on_mutant = mutant_kind != "BUILD"
    fired = detector_on_honest and not detector_on_mutant
    return {
        "ok": fired,
        "honest_kind": honest_kind,
        "mutant_kind": mutant_kind,
        "honest_winner": (honest.get("winner") or {}).get("variant_id"),
        "mutant_winner": (mutant.get("winner") or {}).get("variant_id"),
        "note": (
            "KIND_COST['BUILD']=0 must let BUILD:from-scratch beat ADOPT "
            "on the adoption goal so the detector is two-sided."
        ),
    }


def uncovered_not_false_adopt(result: dict[str, Any]) -> dict[str, Any]:
    winner = result.get("winner") or {}
    kind = winner.get("kind")
    false_adopt = kind == "ADOPT"
    return {
        "ok": not false_adopt and kind in {"ADAPT", "MERGE", "COMPOSE", "BUILD"},
        "winner_kind": kind,
        "winner_id": winner.get("variant_id"),
    }


def looks_right_not_returned(result: dict[str, Any]) -> dict[str, Any]:
    winner = result.get("winner") or {}
    cosmetic = next(
        (
            v
            for v in (result.get("rejected") or [])
            if v.get("variant_id") == "BUILD:looks-right"
        ),
        None,
    )
    stages = (winner.get("workflow") or {}).get("stages") or []
    leaked = any(s.get("op") == LOOKS_RIGHT_OP for s in stages)
    ok = (
        cosmetic is not None
        and not cosmetic.get("static_ok")
        and str(cosmetic.get("static_reason") or "").startswith("unknown-op:")
        and winner.get("variant_id") != "BUILD:looks-right"
        and not leaked
    )
    return {
        "ok": ok,
        "cosmetic_present": cosmetic is not None,
        "cosmetic_static_ok": None if cosmetic is None else cosmetic.get("static_ok"),
        "leaked_into_winner": leaked,
    }


def empty_scout_typed_failure() -> dict[str, Any]:
    rec = forge(ADOPTION_GOAL, candidates=[])
    return {
        "ok": rec.get("error_type") == FORGE_INPUT_INVALID and rec.get("ok") is False,
        "error_type": rec.get("error_type"),
    }


def resolve_anchor(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


# Silence unused-import linters that do not see UNCOVERED_GOAL used by probes.
_ = UNCOVERED_GOAL
