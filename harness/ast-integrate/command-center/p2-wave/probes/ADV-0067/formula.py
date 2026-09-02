"""Marketplace quality/conformance score (IMP-0094 reconstruction).

Production `tools/marketplace/quality_score.py` is absent on this tree.
IMP-0094 specifies a decomposable score from auditable inputs only:
conformance pass rate, test presence and pass rate, documentation
completeness, SBOM and provenance presence, advisory cleanliness.
Popularity must not change the score. A package with no tests must
score strictly lower than an identical one with passing tests.

Declared-benchmark count is included because ADV-0067 names it as an
attack surface. Reproduction is NOT required by IMP-0094 and is
therefore a cheap term — that is the finding, not a hidden patch.

Substance (non-trivial asserts, unique doc tokens, reproduced
benchmarks) is measured separately and does not enter the score.
"""
from __future__ import annotations

from typing import Any, Mapping

WEIGHTS: dict[str, float] = {
    "conformance_pass_rate": 20.0,
    "test_presence": 10.0,
    "test_pass_rate": 15.0,
    "documentation_completeness": 15.0,
    "sbom_present": 10.0,
    "provenance_present": 10.0,
    "advisory_cleanliness": 10.0,
    "declared_benchmarks": 10.0,
}

TERM_IDS = tuple(WEIGHTS.keys())
SCORE_SCALE = sum(WEIGHTS.values())
PRODUCTION_MODULE = "tools/marketplace/quality_score.py"


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
    """Map published measurements onto the 0..1 inputs the weights multiply.

    test_pass_rate contributes only when tests are present, so a no-test
    package cannot harvest the pass-rate term with a vacuous 100%.
    """
    presence = 1.0 if clip01(raw.get("test_presence")) >= 0.5 else 0.0
    declared = raw.get("declared_benchmarks")
    if declared is None:
        declared_ratio = clip01(raw.get("declared_benchmarks_ratio"))
    else:
        try:
            declared_ratio = min(max(int(declared), 0), 3) / 3.0
        except (TypeError, ValueError):
            declared_ratio = 0.0
    return {
        "conformance_pass_rate": clip01(raw.get("conformance_pass_rate")),
        "test_presence": presence,
        "test_pass_rate": clip01(raw.get("test_pass_rate")) if presence else 0.0,
        "documentation_completeness": clip01(raw.get("documentation_completeness")),
        "sbom_present": 1.0 if clip01(raw.get("sbom_present")) >= 0.5 else 0.0,
        "provenance_present": 1.0 if clip01(raw.get("provenance_present")) >= 0.5 else 0.0,
        "advisory_cleanliness": 1.0 if clip01(raw.get("advisory_cleanliness")) >= 0.5 else 0.0,
        "declared_benchmarks": declared_ratio,
    }


def score_from_components(raw: Mapping[str, Any]) -> dict[str, Any]:
    components = effective_components(raw)
    parts = {term: round(WEIGHTS[term] * components[term], 6) for term in TERM_IDS}
    total = round(sum(parts.values()), 6)
    rederived = round(sum(WEIGHTS[term] * components[term] for term in TERM_IDS), 6)
    popularity = raw.get("downloads")
    return {
        "total": total,
        "rederived": rederived,
        "rederivable": abs(total - rederived) < 1e-9,
        "scale": SCORE_SCALE,
        "parts": parts,
        "components": components,
        "weights": dict(WEIGHTS),
        "popularity_ignored": True,
        "downloads_observed": popularity,
    }


def score_with_popularity_term(raw: Mapping[str, Any], weight: float = 10.0) -> float:
    """Mutant used only as the BAD arm of the popularity negative control."""
    base = score_from_components(raw)["total"]
    try:
        downloads = float(raw.get("downloads") or 0)
    except (TypeError, ValueError):
        downloads = 0.0
    bonus = weight if downloads >= 1000 else 0.0
    return round(base + bonus, 6)
