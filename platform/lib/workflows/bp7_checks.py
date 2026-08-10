"""Executable predicates over a blueprint document, for the bp-7 flagship tests.

WHY THE PREDICATES LIVE HERE AND NOT INSIDE THE TESTS
A both-states control is only a control if the SAME function is run against the real document
and against the mutated one. If the positive test asserts one thing and the negative test
asserts another, nothing has been controlled - that is how a probe ends up silent in both
states. Every predicate below returns a :class:`CheckResult` carrying its failure reasons, so a
negative test can additionally assert the mutation killed the property for the RIGHT reason
rather than incidentally.

Each predicate is a mechanical structure query - stage graph reachability, expression identifier
sets, role write-path sets. None of them asks a model anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass
class CheckResult:
    name: str
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return self.ok

    def why(self) -> str:
        return f"{self.name}: " + ("OK" if self.ok else "; ".join(self.reasons))


# ------------------------------------------------------------------ structure helpers


def top_stages(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [s for s in doc.get("stages", []) if isinstance(s, dict)]


def all_stages(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every stage anywhere in the document, including fan-out/loop bodies and repair sub-stages."""
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "kind" in node and "id" in node:
                out.append(node)
            for key in ("body", "diagnose", "repair", "verify"):
                sub = node.get(key)
                if isinstance(sub, list):
                    for x in sub:
                        walk(x)
                elif isinstance(sub, dict):
                    walk(sub)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(doc.get("stages"))
    return out


def stage(doc: Mapping[str, Any], stage_id: str) -> dict[str, Any] | None:
    for s in all_stages(doc):
        if s.get("id") == stage_id:
            return s
    return None


def work_units(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            wu = node.get("work_unit")
            if isinstance(wu, dict):
                units.append(wu)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return units


def ancestors(doc: Mapping[str, Any], stage_id: str) -> set[str]:
    """Transitive ``depends_on`` closure of a TOP-LEVEL stage, within the top-level scope."""
    by_id = {s["id"]: s for s in top_stages(doc)}
    seen: set[str] = set()
    frontier = list(by_id.get(stage_id, {}).get("depends_on", []) or [])
    while frontier:
        cur = str(frontier.pop())
        if cur in seen:
            continue
        seen.add(cur)
        frontier.extend(by_id.get(cur, {}).get("depends_on", []) or [])
    return seen


def gate_expression(doc: Mapping[str, Any], stage_id: str) -> str | None:
    """The expression a gate stage evaluates, following ``gate_ref`` into the gate library."""
    st = stage(doc, stage_id)
    if st is None:
        return None
    inline = st.get("gate")
    if isinstance(inline, dict):
        expr = inline.get("expression")
        return expr if isinstance(expr, str) else None
    ref = st.get("gate_ref")
    if isinstance(ref, str):
        g = (doc.get("gates") or {}).get(ref) or {}
        expr = g.get("expression")
        return expr if isinstance(expr, str) else None
    return None


def gate_on_fail(doc: Mapping[str, Any], stage_id: str) -> str | None:
    st = stage(doc, stage_id)
    if st is None:
        return None
    inline = st.get("gate")
    if isinstance(inline, dict):
        return inline.get("on_fail")
    ref = st.get("gate_ref")
    if isinstance(ref, str):
        return ((doc.get("gates") or {}).get(ref) or {}).get("on_fail")
    return None


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def identifiers(expression: str | None) -> set[str]:
    if not isinstance(expression, str):
        return set()
    words = set(_IDENT.findall(expression))
    return words - {"AND", "OR", "NOT", "true", "false"}


def roles_writing(doc: Mapping[str, Any], prefixes: Iterable[str]) -> set[str]:
    """Role names whose ``write_paths`` touch any of ``prefixes``."""
    hits: set[str] = set()
    pref = tuple(prefixes)
    for name, spec in (doc.get("roles") or {}).items():
        for p in (spec or {}).get("write_paths", []) or []:
            if str(p).startswith(pref):
                hits.add(name)
    return hits


# --------------------------------------------------------- 73 bounded-corpus-distillation


def two_probe_agreement_gates_streaming(doc: Mapping[str, Any]) -> CheckResult:
    """Streaming may not start until two MECHANICALLY INDEPENDENT enumerations agree."""
    r = CheckResult("two-probe-agreement-gates-streaming")
    gate_id = "probe-agreement"
    expr = gate_expression(doc, gate_id)
    if expr is None:
        r.reasons.append(f"no gate stage {gate_id!r} with an expression")
        return r
    ids = identifiers(expr)
    if not {"probe_a_count", "probe_b_count"} <= ids:
        r.reasons.append(
            f"gate expression does not compare the two probe counts: {expr!r}"
        )

    g = stage(doc, gate_id) or {}
    deps = set(g.get("depends_on") or [])
    if not {"enumerate-glob", "enumerate-independent"} <= deps:
        r.reasons.append(
            f"agreement gate does not depend on both probes: {sorted(deps)}"
        )

    a, b = stage(doc, "enumerate-glob"), stage(doc, "enumerate-independent")
    if a is None or b is None:
        r.reasons.append("one of the two enumeration stages is missing")
    elif a.get("role") == b.get("role"):
        r.reasons.append(
            f"both probes use the same role {a.get('role')!r}: a re-run of one instrument is not a second signal"
        )

    if gate_id not in ancestors(doc, "stream-extract"):
        r.reasons.append(
            "stream-extract does not transitively depend on the agreement gate"
        )
    return r


def malformed_and_dropped_tail_are_accounted(doc: Mapping[str, Any]) -> CheckResult:
    """A silent skip is a coverage lie: both counters must be gate conditions."""
    r = CheckResult("malformed-and-dropped-tail-accounted")
    expr = gate_expression(doc, "coverage-gate")
    ids = identifiers(expr)
    for needed in ("malformed_records_counted", "dropped_tail_recorded"):
        if needed not in ids:
            r.reasons.append(f"coverage gate does not require {needed}: {expr!r}")
    return r


# ------------------------------------------------ 74 measurement-instrument-validation


SHAPE_CHAIN = (
    "shape-self-contradiction",
    "shape-self-match",
    "shape-comparator",
    "shape-harness-fit",
)


def four_shapes_precede_the_control(doc: Mapping[str, Any]) -> CheckResult:
    """The four construction checks run FIRST, then the known-present control, then the verdict."""
    r = CheckResult("four-shapes-precede-the-control")
    for sid in SHAPE_CHAIN:
        if stage(doc, sid) is None:
            r.reasons.append(f"missing shape stage {sid!r}")
    if r.reasons:
        return r
    for earlier, later in zip(SHAPE_CHAIN, SHAPE_CHAIN[1:]):
        if earlier not in ancestors(doc, later):
            r.reasons.append(
                f"{later!r} does not depend on {earlier!r}: the chain is broken"
            )
    ctl = "known-present-control"
    if stage(doc, ctl) is None:
        r.reasons.append(f"missing {ctl!r}")
    else:
        anc = ancestors(doc, ctl)
        for sid in SHAPE_CHAIN:
            if sid not in anc:
                r.reasons.append(f"the control does not run after {sid!r}")
    if ctl not in ancestors(doc, "emit-verdict"):
        r.reasons.append("emit-verdict does not depend on the known-present control")
    return r


def self_contradiction_halts_the_analysis(doc: Mapping[str, Any]) -> CheckResult:
    """A self-contradicting run must HALT, not be recorded and stepped over."""
    r = CheckResult("self-contradiction-halts")
    gid = "halt-on-self-contradiction"
    expr = gate_expression(doc, gid)
    if "self_contradiction_found" not in identifiers(expr):
        r.reasons.append(f"halt gate does not test self_contradiction_found: {expr!r}")
    on_fail = gate_on_fail(doc, gid)
    if on_fail not in ("fail", "escalate-to-human"):
        r.reasons.append(
            f"halt gate on_fail is {on_fail!r}, which does not halt the analysis"
        )
    for sid in ("shape-self-match", "emit-verdict"):
        if gid not in ancestors(doc, sid):
            r.reasons.append(f"{sid!r} is reachable without passing the halt gate")
    return r


# ------------------------------------------------------ 76 hermetic-eval-registry-run


def delta_gated_on_variance_and_degraded_control(doc: Mapping[str, Any]) -> CheckResult:
    """An improvement claim needs a supra-band delta AND an eval proven able to see a regression."""
    r = CheckResult("delta-gated-on-variance-and-degraded-control")
    expr = gate_expression(doc, "delta-gate")
    ids = identifiers(expr)
    for needed in (
        "delta_vs_baseline",
        "rerun_variance_band",
        "degraded_control_scored_lower",
    ):
        if needed not in ids:
            r.reasons.append(f"delta gate does not require {needed}: {expr!r}")
    anc = ancestors(doc, "compare-to-baseline")
    for sid in ("measure-variance", "degraded-control"):
        if sid not in anc:
            r.reasons.append(f"compare-to-baseline does not depend on {sid!r}")
    return r


def run_is_hermetic(doc: Mapping[str, Any]) -> CheckResult:
    """No wall clock, no unseeded entropy, no unrecorded network - gated AND declared."""
    r = CheckResult("run-is-hermetic")
    ids = identifiers(gate_expression(doc, "hermeticity-gate"))
    for needed in (
        "wall_clock_reads",
        "unseeded_entropy_reads",
        "unrecorded_network_calls",
    ):
        if needed not in ids:
            r.reasons.append(f"hermeticity gate does not count {needed}")
    forbidden = set(
        (doc.get("replay") or {}).get("forbid_nondeterministic_sources") or []
    )
    for needed in ("clock", "random", "network"):
        if needed not in forbidden:
            r.reasons.append(
                f"replay does not forbid the nondeterministic source {needed!r}"
            )
    return r


# ---------------------------------------------------- 77 design-studio-eight-gate-loop


def exactly_one_source_write_stage_with_revert(doc: Mapping[str, Any]) -> CheckResult:
    """One gate writes app source; a repair loop reverts it and verifies independently."""
    r = CheckResult("one-source-write-stage-with-revert")
    writers = roles_writing(doc, ("app/", "src/"))
    # the reverter is allowed to write source in order to UNDO; it is not an authoring role
    authoring = writers - {"reverter"}
    if authoring != {"implementer"}:
        r.reasons.append(
            f"expected exactly one authoring role with app-source write access, found {sorted(authoring)}"
        )
    rl = stage(doc, "revert-gate")
    if rl is None or rl.get("kind") != "repair_loop":
        r.reasons.append("no repair_loop stage 'revert-gate'")
        return r
    if list(rl.get("target") or []) != ["g5-implement"]:
        r.reasons.append(
            f"revert loop targets {rl.get('target')!r}, not the source-write stage"
        )
    verify = rl.get("verify")
    if not isinstance(verify, dict):
        r.reasons.append(
            "revert loop has no verify stage: a repair without an independent verify is a retry"
        )
        return r
    vexpr = (
        verify.get("gate", {}).get("expression")
        if isinstance(verify.get("gate"), dict)
        else None
    )
    vids = identifiers(vexpr)
    if "regression_count" not in vids:
        r.reasons.append(f"revert verify does not re-check the regression: {vexpr!r}")
    repair = rl.get("repair") or {}
    if repair.get("role") == (stage(doc, "g5-implement") or {}).get("role"):
        r.reasons.append(
            "the reverter is the same role as the implementer: the author would certify its own undo"
        )
    return r


def every_gate_declares_its_router_entry(doc: Mapping[str, Any]) -> CheckResult:
    """The mode router is declarative: each G-stage carries a `when` over entry_gate."""
    r = CheckResult("router-entry-declared-on-every-gate")
    if "entry_gate" not in (doc.get("params") or {}):
        r.reasons.append(
            "entry_gate is not a declared param, so the router cannot be evaluated"
        )
    gates = [s for s in top_stages(doc) if str(s.get("id", "")).startswith("g")]
    if len(gates) < 8:
        r.reasons.append(
            f"expected at least 8 router-guarded gate stages, found {len(gates)}"
        )
    for s in gates:
        if "entry_gate" not in identifiers(s.get("when")):
            r.reasons.append(
                f"stage {s.get('id')!r} has no entry_gate router condition"
            )
    return r


# ------------------------------------------------- 78 two-track-ui-audit-rubric-verdict


def critical_error_caps_the_composite(doc: Mapping[str, Any]) -> CheckResult:
    """A measured critical error CAPS the composite; it is not averaged into it."""
    r = CheckResult("critical-error-caps-composite")
    expr = gate_expression(doc, "cap-gate")
    ids = identifiers(expr)
    if not {"composite", "critical_error_cap"} <= ids:
        r.reasons.append(f"cap gate does not bound composite by the cap: {expr!r}")
    elif "<=" not in str(expr):
        r.reasons.append(f"cap gate does not express an upper bound: {expr!r}")
    if "consistency-gate" not in ancestors(doc, "apply-critical-override"):
        r.reasons.append(
            "the cap is computed before Track B is checked against Track A"
        )
    return r


def one_scoring_call_per_dimension(doc: Mapping[str, Any]) -> CheckResult:
    """Track B makes exactly ONE scoring call per rubric dimension."""
    r = CheckResult("one-scoring-call-per-dimension")
    st = stage(doc, "score-track-b")
    if st is None or st.get("kind") != "fanout":
        r.reasons.append("score-track-b is not a fanout over the rubric dimensions")
        return r
    over = st.get("over") or {}
    if over.get("source") != "param" or over.get("ref") != "rubric_dimensions":
        r.reasons.append(
            f"scoring does not fan out over the rubric_dimensions param: {over!r}"
        )
    scoring_bodies = [b for b in st.get("body") or [] if b.get("kind") == "task"]
    if len(scoring_bodies) != 1:
        r.reasons.append(
            f"the fan-out body contains {len(scoring_bodies)} scoring tasks; more than one breaks the one-call-per-dimension protocol"
        )
    ids = identifiers(gate_expression(doc, "protocol-gate"))
    for needed in ("scoring_calls", "scored_dimensions", "multi_dimension_calls"):
        if needed not in ids:
            r.reasons.append(f"protocol gate does not assert {needed}")
    return r


# ------------------------------------------------------------ 81 design-first-ui-intake


def implementation_unreachable_without_a_direction(
    doc: Mapping[str, Any],
) -> CheckResult:
    """The implement stage is structurally gated on a recorded design direction."""
    r = CheckResult("implementation-unreachable-without-direction")
    gid = "admission-gate"
    expr = gate_expression(doc, gid)
    if "design_direction_recorded" not in identifiers(expr):
        r.reasons.append(
            f"admission gate does not require a recorded direction: {expr!r}"
        )
    if gate_on_fail(doc, gid) not in ("fail", "escalate-to-human"):
        r.reasons.append(
            f"admission gate on_fail is {gate_on_fail(doc, gid)!r} and does not block"
        )
    impl = stage(doc, "implement")
    if impl is None:
        r.reasons.append("no implement stage")
        return r
    if gid not in ancestors(doc, "implement"):
        r.reasons.append("implement does not transitively depend on the admission gate")
    return r


def non_ui_request_passes_through(doc: Mapping[str, Any]) -> CheckResult:
    """A non-UI request must not be captured: the design stages are all `when`-guarded."""
    r = CheckResult("non-ui-request-passes-through")
    ids = identifiers(gate_expression(doc, "routing-control"))
    if "false_routing_detected" not in ids:
        r.reasons.append("routing control does not test false_routing_detected")
    for sid in ("recommend-direction", "produce-canvas", "implement"):
        st = stage(doc, sid)
        if st is None:
            r.reasons.append(f"missing stage {sid!r}")
        elif "request_is_ui" not in identifiers(st.get("when")):
            r.reasons.append(f"stage {sid!r} runs unconditionally on a non-UI request")
    return r


# -------------------------------------------------- 84 ssot-documentation-reconcile


def authority_is_assigned_by_measurability(doc: Mapping[str, Any]) -> CheckResult:
    """Authority goes to the statement a probe AGREES with, or the fact is UNVERIFIED everywhere."""
    r = CheckResult("authority-by-measurability")
    expr = gate_expression(doc, "measurability-gate")
    ids = identifiers(expr)
    for needed in (
        "authoritative_source_agrees_with_probe",
        "fact_marked_unverified_everywhere",
    ):
        if needed not in ids:
            r.reasons.append(
                f"measurability gate does not reference {needed}: {expr!r}"
            )
    st = stage(doc, "designate-authority")
    if st is None:
        r.reasons.append("no designate-authority stage")
        return r
    wu = st.get("work_unit") or {}
    if not any("measurability_probe" in str(i) for i in wu.get("inputs", [])):
        r.reasons.append(
            "the adjudicator does not take the measurability probe as an input"
        )
    if "measurability-gate" not in ancestors(doc, "rewrite-as-pointers"):
        r.reasons.append("the pointer rewrite can run without the measurability gate")
    return r


def no_contradiction_is_resolved_silently(doc: Mapping[str, Any]) -> CheckResult:
    """Every rewritten statement lands in the superseded register."""
    r = CheckResult("no-silent-resolution")
    ids = identifiers(gate_expression(doc, "superseded-gate"))
    for needed in ("contradictions_resolved_silently", "superseded_register_written"):
        if needed not in ids:
            r.reasons.append(f"superseded gate does not assert {needed}")
    if "rewrite-as-pointers" not in ancestors(doc, "register-superseded"):
        r.reasons.append(
            "the register does not run after the rewrite it is supposed to record"
        )
    fp = identifiers(gate_expression(doc, "false-positive-gate"))
    if "legitimate_repeats_flagged_as_contradiction" not in fp:
        r.reasons.append("no false-positive control on legitimately repeated context")
    return r
