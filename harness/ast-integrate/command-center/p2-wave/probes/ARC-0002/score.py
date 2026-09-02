"""Frozen tournament scoring contract for ARC-0002.

Weights are basis points (1.0 == 10000) so the sum is exact. Decimal
weights are derived, never hand-typed as binary floats.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

BPS_TOTAL = 10000
MUTATION_DELTA = Decimal("0.01")
MUTATION_BPS = 100

# Ranked against catalog citations of _USER-PROMPTS.md:10487-10498.
# That file is not on this worktree; each row names the citation used.
DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "correctness",
        "rank": 1,
        "basis_points": 4000,
        "catalog_citation": (
            "command-center/WORK-UNIT-CATALOG.json ARC-0002 question_or_target: "
            "'correctness first'"
        ),
        "definition": (
            "Does the proposed control plane do the right thing on the named "
            "capability sample: load order, precedence, and expressibility "
            "verdicts match the dossier's own claims when re-run."
        ),
        "evidence_required": (
            "At least one transcribed sample with source_id, plus a named probe "
            "command that a second agent can re-run."
        ),
        "zero_if": "Sample transcription missing, or a claimed EXPRESSIBLE construct fails mapping.",
    },
    {
        "id": "verified_improvement",
        "rank": 2,
        "basis_points": 2500,
        "catalog_citation": (
            "command-center/WORK-UNIT-CATALOG.json cites objective 2 "
            "'verified improvement' at _USER-PROMPTS.md:10490"
        ),
        "definition": (
            "The dossier states a measurable before/after (or both-states) "
            "check. Improvement is scored only when a probe records baseline "
            "and post values, never because an agent asserted it."
        ),
        "evidence_required": "Named both-states or delta probe with recorded numbers.",
        "zero_if": "No measured baseline, or improvement claimed only in prose.",
    },
    {
        "id": "operator_usability",
        "rank": 3,
        "basis_points": 1800,
        "catalog_citation": (
            "command-center/WORK-UNIT-CATALOG.json rationale: objective function "
            "ranks usability above performance"
        ),
        "definition": (
            "An operator can locate, load, and override a capability from the "
            "declared file set without a resident runtime or a generated layer "
            "the operator cannot inspect."
        ),
        "evidence_required": "File set + load order + a worked example path an operator would touch.",
        "zero_if": "Operator path depends on an unpublished generator or a hidden live tree.",
    },
    {
        "id": "performance",
        "rank": 4,
        "basis_points": 1200,
        "catalog_citation": (
            "Same catalog rationale: usability is ranked above performance, so "
            "performance is present and strictly below usability."
        ),
        "definition": (
            "Load and judge cost stays bounded: no unbounded directory walk, "
            "no extra orchestration runtime, no N-agent fan-out as a substitute "
            "for evidence."
        ),
        "evidence_required": "Bound stated (file count, load order length, or probe wall-clock).",
        "zero_if": "Architecture requires a second orchestration runtime or unbounded scan.",
    },
    {
        "id": "resource_efficiency",
        "rank": 5,
        "basis_points": 500,
        "catalog_citation": (
            "command-center/WORK-UNIT-CATALOG.json: _USER-PROMPTS.md:10498 "
            "resource efficiency is last, but it is on the list"
        ),
        "definition": (
            "Tokens, wall-clock, tool calls, and estimated spend are visible "
            "next to any quality claim. Efficiency is last, not invisible."
        ),
        "evidence_required": "Cost fields named even when unmeasured (UNMEASURED, not omitted).",
        "zero_if": "Quality claimed with cost fields stripped.",
    },
)


def weight_decimal(basis_points: int) -> Decimal:
    return Decimal(basis_points) / Decimal(BPS_TOTAL)


def dimension_public(row: dict[str, Any]) -> dict[str, Any]:
    bp = int(row["basis_points"])
    dec = weight_decimal(bp)
    out = dict(row)
    out["weight_decimal"] = f"{dec:.2f}"
    out["weight"] = float(dec)
    out["catalog_citation"] = out["catalog_citation"]
    return out


def public_dimensions() -> list[dict[str, Any]]:
    return [dimension_public(r) for r in DIMENSIONS]


def weights_map(dims: list[dict[str, Any]] | None = None) -> dict[str, Decimal]:
    rows = dims if dims is not None else public_dimensions()
    out: dict[str, Decimal] = {}
    for row in rows:
        out[str(row["id"])] = Decimal(str(row["weight_decimal"]))
    return out


def basis_points_sum(dims: list[dict[str, Any]] | None = None) -> int:
    rows = dims if dims is not None else public_dimensions()
    return sum(int(r["basis_points"]) for r in rows)


def weights_sum(dims: list[dict[str, Any]] | None = None) -> Decimal:
    return sum(weights_map(dims).values(), Decimal("0"))


def assert_weight_contract(dims: list[dict[str, Any]] | None = None) -> None:
    rows = dims if dims is not None else public_dimensions()
    if basis_points_sum(rows) != BPS_TOTAL:
        raise AssertionError(f"basis_points sum {basis_points_sum(rows)} != {BPS_TOTAL}")
    if weights_sum(rows) != Decimal("1.00"):
        raise AssertionError(f"weights sum {weights_sum(rows)} != 1.00")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError(f"duplicate dimension ids: {ids}")
    for row in rows:
        if int(row["basis_points"]) <= 0:
            raise AssertionError(f"non-positive weight for {row['id']}")


def score_vector(scores: dict[str, Decimal | int | float | str], dims: list[dict[str, Any]] | None = None) -> Decimal:
    """Weighted sum. Each dimension score is in [0, 1]."""
    w = weights_map(dims)
    total = Decimal("0")
    for dim_id, weight in w.items():
        if dim_id not in scores:
            raise KeyError(f"missing dimension {dim_id}")
        val = Decimal(str(scores[dim_id]))
        if val < 0 or val > 1:
            raise ValueError(f"{dim_id} score {val} not in [0,1]")
        total += weight * val
    return total


def strictly_better(
    better: dict[str, Decimal | int | float | str],
    worse: dict[str, Decimal | int | float | str],
    dims: list[dict[str, Any]] | None = None,
) -> bool:
    """True iff `better` is >= on every dimension and > on at least one."""
    w = weights_map(dims)
    ge_all = True
    gt_one = False
    for dim_id in w:
        a = Decimal(str(better[dim_id]))
        b = Decimal(str(worse[dim_id]))
        if a < b:
            ge_all = False
        if a > b:
            gt_one = True
    return ge_all and gt_one


TIE_BREAK_ORDER = (
    "correctness",
    "verified_improvement",
    "operator_usability",
    "performance",
    "resource_efficiency",
    "architecture_id_lexicographic",
)

DISQUALIFIERS = (
    {
        "id": "DQ-DUPLICATE-CONTROL-PLANE",
        "condition": (
            "Entry introduces a second orchestration runtime or a second writable "
            "capability root that can silently diverge from the declared file set "
            "(catalog cites _USER-PROMPTS.md:10483)."
        ),
        "effect": "DISQUALIFIED; numeric score 0; not ranked against qualified entries.",
    },
    {
        "id": "DQ-OVERCLAIM",
        "condition": "A load-bearing claim has verdict CONFIRMED without a file:line or probe anchor.",
        "effect": "DISQUALIFIED. Overclaim is a failure class of this unit, not a low score.",
    },
    {
        "id": "DQ-POST-HOC-RUBRIC",
        "condition": (
            "RUBRIC.json sha256 at judging time != sha256 recorded in "
            "ARTIFACT-MANIFEST.json."
        ),
        "effect": "Judging must stop. The freeze is broken; scores are not issued.",
    },
    {
        "id": "DQ-INSUFFICIENT-EVIDENCE",
        "condition": "Any minimum_evidence.required_fields item is missing.",
        "effect": "Scored zero (INSUFFICIENT_EVIDENCE), not judged on dimensions.",
    },
    {
        "id": "DQ-SCHEMA-INVALID",
        "condition": "Dossier fails architecture-dossier.schema.json.",
        "effect": "DISQUALIFIED.",
    },
    {
        "id": "DQ-PREDATES-FREEZE",
        "condition": (
            "Dossier mtime is not strictly after ARTIFACT-MANIFEST registered_at. "
            "Pre-existing DESIGN.json files on this worktree are in this class."
        ),
        "effect": (
            "Ineligible as a freeze-compliant tournament entry until re-emitted "
            "after this freeze. Not silently scored."
        ),
    },
)

MINIMUM_EVIDENCE_FIELDS = (
    "architecture_id",
    "file_set",
    "load_order",
    "precedence",
    "samples",
    "named_probes",
    "honest_library_presence",
)


def has_minimum_evidence(entry: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = [f for f in MINIMUM_EVIDENCE_FIELDS if not entry.get(f)]
    samples = entry.get("samples") or []
    if isinstance(samples, list) and len(samples) < 1:
        if "samples" not in missing:
            missing.append("samples")
    return (not missing, missing)


# Call-site names used by emit_rubric.py, prereg.py, and the probes.
public_dimensions = public_dimensions
assert_weight_contract = assert_weight_contract
weights_sum = weights_sum
basis_points_sum = basis_points_sum
score_vector = score_vector
strictly_better = strictly_better
MUTATION_DELTA = MUTATION_DELTA
MUTATION_BPS = MUTATION_BPS
MINIMUM_EVIDENCE_FIELDS = MINIMUM_EVIDENCE_FIELDS
