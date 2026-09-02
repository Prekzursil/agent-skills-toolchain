"""Benchmark + certification (Foundry steps 7-9, spec :10851-10853; acceptance bar :11282).

The bar, quoted
---------------
    "A merged workflow is not accepted because it contains more stages. It must demonstrate
    better correctness, coverage, recovery, or usability on representative cases without
    unacceptable regressions."

That sentence is implemented literally, and the "not because it contains more stages" half is
enforced by CONSTRUCTION rather than by intent:

* the score vector contains exactly the four named axes;
* ``stage_count`` and the other cost dimensions live in a SEPARATE vector;
* :func:`certify` asserts at runtime that the two vectors are disjoint, so the failure mode
  cannot be reintroduced by adding a weight to a table;
* a fusion that improves no axis is REJECTED with ``reason="no-axis-improved"`` even when it
  is bigger, better-documented and schema-valid.

Every axis is a deterministic predicate set over the DSL document. No model judgement is
consulted anywhere in this module: the question "does this workflow bound its loops" is exactly
answerable, so it is answered by an algorithm (fan-out-contract C4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from foundry.mechanisms import (
    MechanismProfile,
    hazard_coverage,
    iter_stages,
    structural_capabilities,
)
from foundry.model import BENEFIT_AXES, COST_DIMENSIONS, HAZARD_IDS, capabilities

#: an axis must beat the best source by more than this to count as an improvement. Set above
#: float noise but below the smallest real predicate step (1/12 ~= 0.083 for the correctness set).
IMPROVEMENT_EPSILON = 0.01

#: how far an axis may fall below the best source and still be "without unacceptable
#: regressions". 0.0 means: no axis may regress at all against the best source.
REGRESSION_TOLERANCE = 0.0


# ------------------------------------------------------------------ representative cases


@dataclass(frozen=True)
class Case:
    """One representative case: what the task demands, and what will be thrown at it."""

    id: str
    title: str
    required_capabilities: tuple[str, ...]
    hazards: tuple[str, ...]

    def validate(self) -> list[str]:
        problems = []
        known = set(capabilities())
        for c in self.required_capabilities:
            if c not in known:
                problems.append(f"{self.id}: unknown capability {c!r}")
        for h in self.hazards:
            if h not in set(HAZARD_IDS):
                problems.append(f"{self.id}: unknown hazard {h!r}")
        if not self.required_capabilities and not self.hazards:
            problems.append(
                f"{self.id}: case demands nothing, so it can never discriminate"
            )
        return problems


#: The default case library. Deliberately small and representative rather than exhaustive:
#: each case is a real shape of work this estate runs, and together they demand 20 of the 24
#: capabilities and all 16 hazards. A case that demands nothing cannot discriminate between two
#: workflows, so :meth:`Case.validate` rejects it.
DEFAULT_CASES: tuple[Case, ...] = (
    Case(
        "c1-wide-fanout-build",
        "Fan out ~20 file-disjoint build units and fan back in without losing a straggler",
        (
            "dynamic_fanout",
            "barriers",
            "work_unit_binding",
            "gates",
            "failure_policy",
            "cost_estimate",
        ),
        (
            "straggler-work-silently-dropped",
            "silent-failure",
            "cost-blowout",
            "total-loss-on-freeze",
        ),
    ),
    Case(
        "c2-long-resumable-program",
        "Run a multi-hour program that survives a compaction, a crash and a stale checkpoint",
        (
            "resume",
            "artifact_caching",
            "deterministic_replay",
            "stages",
            "typed_params",
        ),
        (
            "stale-checkpoint-resumed",
            "non-deterministic-replay",
            "total-loss-on-freeze",
        ),
    ),
    Case(
        "c3-adversarial-review",
        "Review a change with independent reviewers and refuse a single-signal verdict",
        ("roles", "gates", "model_routing", "stopping_rules"),
        (
            "single-signal-verdict",
            "detector-silent-in-both-states",
            "unverifiable-claim",
        ),
    ),
    Case(
        "c4-untrusted-input-handling",
        "Ingest third-party content and code without executing it or leaking a credential",
        ("tools", "source_policy", "export_import", "failure_policy"),
        (
            "untrusted-fetched-content-executed",
            "secret-value-in-export",
            "tool-privilege-escalation",
        ),
    ),
    Case(
        "c5-irreversible-ship",
        "Ship something irreversible (publish, delete, force-push) with a way back",
        ("human_checkpoints", "lineage", "gates"),
        ("irreversible-action-without-human", "no-rollback-path"),
    ),
    Case(
        "c6-repair-until-green",
        "Iterate on a failing gate without grinding on the same failed hypothesis",
        ("repair_loops", "loops_with_convergence", "retries"),
        ("unbounded-loop", "unbounded-retry-grind", "silent-failure"),
    ),
)


def load_cases(path: Path | None = None) -> list[Case]:
    if path is None:
        return list(DEFAULT_CASES)
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else doc.get("cases", [])
    return [
        Case(
            id=str(r["id"]),
            title=str(r.get("title", "")),
            required_capabilities=tuple(r.get("required_capabilities", []) or []),
            hazards=tuple(r.get("hazards", []) or []),
        )
        for r in rows
    ]


# ------------------------------------------------------------------ the four axes


def _mean(flags: Sequence[bool]) -> float:
    return (sum(1 for f in flags if f) / len(flags)) if flags else 0.0


def correctness_predicates(doc: Mapping[str, Any]) -> dict[str, bool]:
    """Does the workflow structurally force its own claims to be checkable?

    Not "does it have many stages" - every predicate here is about a claim being verifiable or a
    verdict being blocked when it is not.
    """
    stages = iter_stages(doc)
    gates = [g for g in (doc.get("gates") or {}).values() if isinstance(g, Mapping)]
    gates += [st["gate"] for _, st in stages if isinstance(st.get("gate"), Mapping)]
    work_units = [
        st["work_unit"] for _, st in stages if isinstance(st.get("work_unit"), Mapping)
    ]
    fanouts = [st for _, st in stages if st.get("kind") == "fanout"]
    barriers = [st for _, st in stages if st.get("kind") == "barrier"]
    produced = [p for _, st in stages for p in (st.get("produces") or [])]
    return {
        "has_at_least_one_gate": bool(gates),
        "every_gate_is_blocking": bool(gates)
        and all(g.get("blocking", True) is not False for g in gates),
        "every_gate_requires_evidence": bool(gates)
        and all(g.get("evidence_required", True) is not False for g in gates),
        "no_gate_checks_zero_conditions": all(
            g.get("conditions_required") != [] for g in gates
        ),
        "every_gate_declares_on_fail": bool(gates)
        and all("on_fail" in g for g in gates),
        "work_units_declare_evidence": bool(work_units)
        and all(str(w.get("evidence_requirement", "")).strip() for w in work_units),
        "work_units_declare_output_schema": bool(work_units)
        and all(str(w.get("output_schema", "")).strip() for w in work_units),
        "artifacts_declare_a_schema": bool(produced)
        and all(str(p.get("schema_ref", "")).strip() for p in produced),
        "artifacts_declare_a_min_size": bool(produced)
        and all(isinstance(p.get("min_bytes"), int) for p in produced),
        "artifacts_name_their_consumers": bool(produced)
        and all(p.get("consumers") for p in produced),
        "every_fanout_is_joined_by_a_barrier": (not fanouts) or bool(barriers),
        "has_a_stopping_rule": bool(doc.get("stopping_rules")),
    }


def coverage_axis(doc: Mapping[str, Any], case: Case) -> tuple[float, dict[str, Any]]:
    """Breadth: the case's demanded capabilities AND its hazards, weighted equally."""
    caps = structural_capabilities(doc)
    haz = hazard_coverage(doc)
    cap_flags = [caps.get(c, False) for c in case.required_capabilities]
    haz_flags = [haz.get(h, False) for h in case.hazards]
    flags = cap_flags + haz_flags
    detail = {
        "capabilities_required": list(case.required_capabilities),
        "capabilities_missing": [
            c for c in case.required_capabilities if not caps.get(c)
        ],
        "hazards_required": list(case.hazards),
        "hazards_uncovered": [h for h in case.hazards if not haz.get(h)],
    }
    return _mean(flags), detail


def recovery_predicates(doc: Mapping[str, Any]) -> dict[str, bool]:
    stages = iter_stages(doc)
    fp = doc.get("failure_policy") or {}
    resume = doc.get("resume") or {}
    retry = doc.get("retry_policy") or {}
    return {
        "declares_a_failure_policy": bool(fp),
        "failure_is_never_silent": bool(fp.get("terminal_state_required"))
        or bool(fp.get("never_silent")),
        "preserves_partial_artifacts": fp.get("preserve_partial_artifact") is not False
        and bool(fp),
        "retry_is_bounded": bool(retry)
        and (
            str(retry.get("strategy")) == "none"
            or isinstance(retry.get("max_attempts"), int)
        ),
        "retry_pivots_instead_of_grinding": str(retry.get("strategy"))
        == "two-strikes-then-pivot",
        "resume_is_enabled": bool(resume.get("enabled")),
        "resume_has_a_durable_store": bool(resume.get("checkpoint_store")),
        "resume_has_a_stable_idempotency_key": bool(resume.get("idempotency_key_from")),
        "handles_a_stale_checkpoint": bool(resume.get("on_stale")),
        "has_a_repair_loop_with_independent_verify": any(
            st.get("kind") == "repair_loop" and isinstance(st.get("verify"), Mapping)
            for _, st in stages
        ),
        "declares_a_rollback_target": bool(
            (doc.get("lineage") or {}).get("rollback_to")
        ),
        "checkpoints_mid_run": any(st.get("checkpoint") is True for _, st in stages),
    }


def usability_predicates(doc: Mapping[str, Any]) -> dict[str, bool]:
    stages = iter_stages(doc)
    params = doc.get("params") or {}
    outputs = doc.get("outputs") or {}
    hcs = [st for _, st in stages if st.get("kind") == "human_checkpoint"]
    return {
        "declares_typed_params": bool(params),
        "every_param_is_described": bool(params)
        and all(
            str(p.get("description", "")).strip()
            for p in params.values()
            if isinstance(p, Mapping)
        ),
        "supports_dry_run": bool((doc.get("dry_run") or {}).get("supported")),
        "dry_run_emits_something_readable": bool(
            (doc.get("dry_run") or {}).get("emits")
        ),
        "declares_a_cost_estimate": bool(doc.get("estimate")),
        "estimate_declares_its_basis": bool((doc.get("estimate") or {}).get("basis")),
        "declares_named_outputs": bool(outputs),
        "has_a_description": len(str(doc.get("description", ""))) >= 80,
        "every_stage_has_a_title": bool(stages)
        and all(str(st.get("title", "")).strip() for _, st in stages),
        "human_checkpoints_cannot_hang": (not hcs)
        or all(str(st.get("on_timeout")) in {"fail", "escalate"} for st in hcs),
        "is_exportable": bool((doc.get("portability") or {}).get("export")),
        "declares_its_lineage": bool((doc.get("lineage") or {}).get("derived_from")),
    }


def cost_vector(doc: Mapping[str, Any]) -> dict[str, int]:
    """Cost, NOT benefit. Kept in its own vector so it can never certify a fusion."""
    stages = iter_stages(doc)
    return {
        "stage_count": len(stages),
        "timeout_budget_seconds": sum(
            int(st.get("timeout_seconds") or 0) for _, st in stages
        ),
        "human_checkpoints": sum(
            1 for _, st in stages if st.get("kind") == "human_checkpoint"
        ),
        "max_fanout_concurrency": max(
            [
                int(st.get("max_concurrency") or 0)
                for _, st in stages
                if st.get("kind") == "fanout"
            ]
            or [0]
        ),
    }


# ------------------------------------------------------------------------- scoring


@dataclass
class CaseScore:
    case_id: str
    axes: dict[str, float]
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "axes": {k: round(v, 4) for k, v in self.axes.items()},
            "detail": self.detail,
        }


@dataclass
class BenchResult:
    workflow_id: str
    per_case: list[CaseScore]
    axes_mean: dict[str, float]
    cost: dict[str, int]
    schema_valid: bool
    semantic_violations: int
    validator_errors: list[str] = field(default_factory=list)

    @property
    def gate_ok(self) -> bool:
        return self.schema_valid and self.semantic_violations == 0

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "schema_valid": self.schema_valid,
            "semantic_violations": self.semantic_violations,
            "validator_errors": self.validator_errors[:8],
            "axes_mean": {k: round(v, 4) for k, v in self.axes_mean.items()},
            "cost": self.cost,
            "per_case": [c.to_json() for c in self.per_case],
        }


def score_case(doc: Mapping[str, Any], case: Case) -> CaseScore:
    corr = correctness_predicates(doc)
    cov, cov_detail = coverage_axis(doc, case)
    rec = recovery_predicates(doc)
    use = usability_predicates(doc)
    return CaseScore(
        case_id=case.id,
        axes={
            "correctness": _mean(list(corr.values())),
            "coverage": cov,
            "recovery": _mean(list(rec.values())),
            "usability": _mean(list(use.values())),
        },
        detail={
            "coverage": cov_detail,
            "correctness_failed": sorted(k for k, v in corr.items() if not v),
            "recovery_failed": sorted(k for k, v in rec.items() if not v),
            "usability_failed": sorted(k for k, v in use.items() if not v),
        },
    )


def _run_dsl_gate(doc: Mapping[str, Any]) -> tuple[bool, int, list[str]]:
    """Validate against the REAL DSL gate (``wfdsl``), not a local re-implementation.

    Using the shipped validator is the mechanically independent second signal on the emitted
    document: the forge builds it, and a module the forge does not own decides whether it is
    legal.
    """
    from wfdsl import schemas, semantics

    errs = sorted(
        schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    sem = semantics.check_workflow(doc)
    violations = sum(len(r.violations) for r in sem if r.severity == "violation")
    return (not errs), violations, schemas.error_summary(errs, limit=8)


def benchmark(doc: Mapping[str, Any], cases: Sequence[Case]) -> BenchResult:
    per_case = [score_case(doc, c) for c in cases]
    axes_mean = {
        axis: (
            sum(cs.axes[axis] for cs in per_case) / len(per_case) if per_case else 0.0
        )
        for axis in BENEFIT_AXES
    }
    valid, violations, errors = _run_dsl_gate(doc)
    return BenchResult(
        workflow_id=str(doc.get("id", "<unnamed>")),
        per_case=per_case,
        axes_mean=axes_mean,
        cost=cost_vector(doc),
        schema_valid=valid,
        semantic_violations=violations,
        validator_errors=errors,
    )


# --------------------------------------------------------------------- certification


@dataclass
class Certification:
    accepted: bool
    verdict: str  # CERTIFIED | REJECTED
    reasons: list[str]
    improvements: dict[str, float]
    regressions: dict[str, float]
    cost_delta: dict[str, int]
    fused: dict[str, Any]
    sources: list[dict[str, Any]]

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "accepted": self.accepted,
            "reasons": self.reasons,
            "axis_improvements_over_best_source": {
                k: round(v, 4) for k, v in self.improvements.items()
            },
            "axis_regressions_against_best_source": {
                k: round(v, 4) for k, v in self.regressions.items()
            },
            "cost_delta_vs_largest_source": self.cost_delta,
            "fused": self.fused,
            "sources": self.sources,
            "acceptance_bar": (
                "spec :11282 - a merged workflow is not accepted because it contains more "
                "stages; it must beat the best source on correctness, coverage, recovery or "
                "usability without unacceptable regressions"
            ),
        }


def gratuitous_stages(
    doc: Mapping[str, Any],
    cases: Sequence[Case],
    candidate_stage_ids: Sequence[str],
) -> list[str]:
    """Which of ``candidate_stage_ids`` change NO axis when removed.

    This is the mechanical form of "a merged workflow is not accepted because it contains more
    stages" (spec :11282). Improving an axis is not enough on its own: a fusion can improve an
    axis with two stages and then carry six more that measure nothing. Each candidate stage is
    ABLATED and the axes recomputed; a stage whose removal leaves every axis identical is
    riding along for free and its presence is a cost with no benefit.

    Measured need: the ``union`` strategy on
    ``bp-cnc-07-probe-wins-split-verdict-resolver`` + ``bp-arc-05.vendor-neutral-workflow-spec-emission``
    produced the SAME +0.1048 coverage / +0.0833 recovery as ``best-of-breed`` while adding
    **+8** stages instead of -1, and the first version of this certifier accepted both.

    Ablation note: removing a stage can leave a dangling ``depends_on`` in the ablated COPY.
    That is harmless here because every axis predicate reads stage content, not referential
    integrity - and the ablated copy is never emitted, only scored.
    """
    top = [s for s in (doc.get("stages") or []) if isinstance(s, Mapping)]
    baseline = {
        axis: sum(sc.axes[axis] for sc in [score_case(doc, c) for c in cases])
        for axis in BENEFIT_AXES
    }
    out: list[str] = []
    wanted = set(candidate_stage_ids)
    for i, st in enumerate(top):
        sid = str(st.get("id"))
        if sid not in wanted:
            continue
        ablated = dict(doc)
        ablated["stages"] = top[:i] + top[i + 1 :]
        after = {
            axis: sum(sc.axes[axis] for sc in [score_case(ablated, c) for c in cases])
            for axis in BENEFIT_AXES
        }
        if all(abs(after[a] - baseline[a]) < 1e-9 for a in BENEFIT_AXES):
            out.append(sid)
    return out


def certify(
    fused: BenchResult,
    sources: Sequence[BenchResult],
    decomposes_back: bool | None = None,
    improvement_epsilon: float = IMPROVEMENT_EPSILON,
    regression_tolerance: float = REGRESSION_TOLERANCE,
    gratuitous: Sequence[str] | None = None,
) -> Certification:
    """Decide CERTIFIED or REJECTED. The only place a fusion can be accepted."""
    # Structural guarantee, checked every call: the benefit vector and the cost vector are
    # disjoint. If someone later adds "stage_count" to BENEFIT_AXES this raises instead of
    # silently certifying bigger-is-better.
    overlap = set(BENEFIT_AXES) & set(COST_DIMENSIONS)
    if overlap:  # pragma: no cover - guard
        raise AssertionError(
            f"cost dimensions leaked into the benefit axes: {sorted(overlap)}. "
            "The spec bar at :11282 forbids certifying a fusion for being bigger."
        )

    reasons: list[str] = []
    if not sources:
        return Certification(
            False,
            "REJECTED",
            ["no source workflows supplied; nothing to beat"],
            {},
            {},
            {},
            fused.to_json(),
            [],
        )

    best = {axis: max(s.axes_mean[axis] for s in sources) for axis in BENEFIT_AXES}
    improvements = {
        axis: fused.axes_mean[axis] - best[axis]
        for axis in BENEFIT_AXES
        if fused.axes_mean[axis] - best[axis] > improvement_epsilon
    }
    regressions = {
        axis: best[axis] - fused.axes_mean[axis]
        for axis in BENEFIT_AXES
        if best[axis] - fused.axes_mean[axis] > regression_tolerance
    }
    largest = max(sources, key=lambda s: s.cost["stage_count"])
    cost_delta = {k: fused.cost[k] - largest.cost[k] for k in COST_DIMENSIONS}

    if not fused.gate_ok:
        reasons.append(
            f"fused workflow fails the DSL gate: schema_valid={fused.schema_valid}, "
            f"semantic_violations={fused.semantic_violations}"
        )
    for s in sources:
        if not s.gate_ok:
            reasons.append(
                f"source {s.workflow_id} fails the DSL gate; a fusion cannot be measured "
                "against an invalid baseline"
            )
    if not improvements:
        reasons.append(
            "no-axis-improved: the fusion does not beat the best source on correctness, "
            "coverage, recovery or usability by more than "
            f"{improvement_epsilon} - and per spec :11282 a larger stage count "
            f"(delta {cost_delta['stage_count']:+d}) is NOT an acceptance reason"
        )
    if regressions:
        reasons.append(
            "unacceptable regression on "
            + ", ".join(f"{k} -{v:.4f}" for k, v in sorted(regressions.items()))
        )
    if decomposes_back is False:
        reasons.append(
            "the fusion does not decompose back into its source mechanisms (spec :11282)"
        )
    if gratuitous:
        reasons.append(
            f"gratuitous-cost: {len(gratuitous)} grafted stage(s) {sorted(gratuitous)} change "
            "NO axis when ablated - the fusion carries them for free. Per spec :11282 a merged "
            "workflow is not accepted because it contains more stages, so a stage that measures "
            "nothing must not ride along"
        )

    accepted = not reasons
    if accepted:
        reasons.append(
            "improved "
            + ", ".join(f"{k} +{v:.4f}" for k, v in sorted(improvements.items()))
            + f" over the best source, with no axis regression; cost delta stage_count "
            f"{cost_delta['stage_count']:+d} (recorded, never a reason to accept)"
        )
    return Certification(
        accepted=accepted,
        verdict="CERTIFIED" if accepted else "REJECTED",
        reasons=reasons,
        improvements=improvements,
        regressions=regressions,
        cost_delta=cost_delta,
        fused=fused.to_json(),
        sources=[s.to_json() for s in sources],
    )


def profile_gap(prof: MechanismProfile, required: Sequence[str]) -> list[str]:
    """Which required capabilities a profile does not provide. Used by scout's recommender."""
    return [c for c in required if not prof.capabilities.get(c)]
