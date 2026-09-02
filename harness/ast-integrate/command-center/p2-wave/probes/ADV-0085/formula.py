"""Workflow QUALITY composite (WFA-0114 reconstruction) attacked by ADV-0085.

Production `tools/bench/quality_metric.py` is absent. WFA-0114 requires a
computed (not judged) rubric on correctness, coverage, recovery and usability
that decides certification. ADV-0085 is not ADV-0067: that unit games the
marketplace conformance score; this games the workflow-output quality metric.

Because WFA-0114 never shipped estimators, the only *computable* stand-ins
this tree can score are the cheap proxies a "computed not judged" harness
typically ships:

* correctness  := envelope schema_validity (not oracle match)
* coverage     := unique evidence-anchor count / ANCHOR_SATURATION (not slot fill)
* recovery     := all-cases-abstain OR any recovered flag (flag is trusted)
* usability    := schema_valid AND (all abstain OR any payload/evidence)

Oracle match and resolving-anchor rate are measured as SUBSTANCE and do not
enter the certification score. That split is the Goodhart surface.
"""
from __future__ import annotations

from typing import Any, Mapping

WEIGHTS: dict[str, float] = {
    "correctness": 25.0,
    "coverage": 25.0,
    "recovery": 25.0,
    "usability": 25.0,
}

TERM_IDS = tuple(WEIGHTS.keys())
SCORE_SCALE = sum(WEIGHTS.values())
ANCHOR_SATURATION = 3
PRODUCTION_MODULE = "tools/bench/quality_metric.py"


def clip01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def effective_components(raw: Mapping[str, Any]) -> dict[str, float]:
    return {
        "correctness": clip01(raw.get("correctness")),
        "coverage": clip01(raw.get("coverage")),
        "recovery": clip01(raw.get("recovery")),
        "usability": clip01(raw.get("usability")),
    }


def score_from_components(raw: Mapping[str, Any]) -> dict[str, Any]:
    components = effective_components(raw)
    parts = {term: round(WEIGHTS[term] * components[term], 6) for term in TERM_IDS}
    total = round(sum(parts.values()), 6)
    rederived = round(sum(WEIGHTS[term] * components[term] for term in TERM_IDS), 6)
    return {
        "total": total,
        "rederived": rederived,
        "rederivable": abs(total - rederived) < 1e-9,
        "scale": SCORE_SCALE,
        "parts": parts,
        "components": components,
        "weights": dict(WEIGHTS),
    }


def score_with_term_zeroed(raw: Mapping[str, Any], dropped: str) -> dict[str, Any]:
    """Ablation: drop one term's contribution without renormalising the rest."""
    scored = score_from_components(raw)
    if dropped not in WEIGHTS:
        raise KeyError(dropped)
    total = round(scored["total"] - scored["parts"][dropped], 6)
    parts = dict(scored["parts"])
    parts[dropped] = 0.0
    return {
        "total": total,
        "dropped_term": dropped,
        "parts": parts,
        "components": scored["components"],
        "baseline_total": scored["total"],
        "marginal": scored["parts"][dropped],
    }


def score_with_length_mutant(raw: Mapping[str, Any], answer_chars: int, bonus: float = 10.0) -> float:
    """Mutant used only as the BAD arm of the length negative control."""
    base = score_from_components(raw)["total"]
    extra = bonus if int(answer_chars or 0) >= 500 else 0.0
    return round(base + extra, 6)


# Import aliases used by inspect_output / probe_common.
PRODUCTION_MODULE = PRODUCTION_MODULE
ANCHOR_SATURATION = ANCHOR_SATURATION
score_from_components = score_from_components
score_with_term_zeroed = score_with_term_zeroed
score_with_length_mutant = score_with_length_mutant
