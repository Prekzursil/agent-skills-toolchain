"""Shared test kit for the bp-5 flagship blueprint tests (library cards 49-60).

Design rule: the tests read the JSON **from disk**, never from the generator. The deliverable
is ``platform/workflows/<id>.json``; a test that imported the builder would prove the builder
self-consistent while a stale or hand-edited file on disk went unchecked.

``assert_rejected`` is the both-states half. Every flagship test mutates its own blueprint in
a way that removes the mechanism the card is FOR, then asserts the real validator rejects it.
A test whose mutation still validates has proven nothing about the constraint it claims to
protect.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
REPO = LIB.parents[1]
for _p in (str(HERE), str(LIB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from wfdsl import expr as _expr  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

WORKFLOW_DIR = REPO / "platform" / "workflows"

#: the 12 documents this slice owns, in card order 49-60
SLUGS: tuple[str, ...] = (
    "crv.split-role-reviewer-panel",
    "crv.differential-change-review-with-history",
    "crv.refactor-equivalence-proof",
    "crv.bug-class-variant-sweep",
    "crv.overclaim-scoping-review",
    "tst.smallest-check-ladder",
    "tst.diff-scoped-mutation-gate",
    "tst.spec-blind-test-synthesis",
    "tst.ui-invariant-walk",
    "tst.packaged-artifact-golden-journey-smoke",
    "tst.fail-first-red-proof-certification",
    "tst.hook-event-reachability-conformance",
)


def load(slug: str) -> dict[str, Any]:
    """Read a blueprint from the deliverable directory."""
    path = WORKFLOW_DIR / f"{slug}.json"
    assert path.is_file(), f"blueprint not on disk: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(doc: dict[str, Any]) -> list[str]:
    errs = sorted(
        schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    return schemas.error_summary(errs, limit=8)


def semantic_violations(doc: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        (r.rule, v)
        for r in semantics.check_workflow(doc)
        if r.severity == "violation"
        for v in r.violations
    ]


def assert_accepted(doc: dict[str, Any]) -> None:
    assert not schema_errors(doc), (
        f"schema rejected a document that must validate: {schema_errors(doc)}"
    )
    assert not semantic_violations(doc), (
        f"semantic violations: {semantic_violations(doc)}"
    )


def assert_rejected(doc: dict[str, Any], why: str) -> None:
    """The both-states control: a mutated blueprint MUST be rejected by the real validator."""
    errs = schema_errors(doc)
    sem = semantic_violations(doc)
    assert errs or sem, (
        f"MUTATION SURVIVED - the validator accepted a document that should be invalid ({why}). "
        "A gate that cannot reject this is not protecting it."
    )


def worked_context(doc: dict[str, Any]) -> dict[str, Any]:
    ex = (doc.get("x_extensions") or {}).get("worked_example") or {}
    ctx = ex.get("context")
    assert isinstance(ctx, dict) and ctx, (
        f"{doc['id']}: worked example carries no context"
    )
    return dict(ctx)


def worked_example(doc: dict[str, Any]) -> dict[str, Any]:
    ex = (doc.get("x_extensions") or {}).get("worked_example")
    assert isinstance(ex, dict) and ex, f"{doc['id']}: no worked example"
    return ex


def gate_expression(doc: dict[str, Any], gate_id: str) -> Any:
    gate = (doc.get("gates") or {}).get(gate_id)
    assert gate is not None, f"{doc['id']}: no gate {gate_id!r}"
    assert "expression" in gate, (
        f"{doc['id']}: gate {gate_id!r} has no expression to evaluate"
    )
    return gate["expression"]


def evaluate_gate(
    doc: dict[str, Any], gate_id: str, overrides: dict[str, Any] | None = None
) -> bool:
    ctx = worked_context(doc)
    ctx.update(overrides or {})
    return _expr.evaluate(gate_expression(doc, gate_id), ctx, strict=True)


def evaluate_stop(
    doc: dict[str, Any], rule_id: str, overrides: dict[str, Any] | None = None
) -> bool:
    rules = {r["id"]: r for r in doc.get("stopping_rules") or []}
    assert rule_id in rules, f"{doc['id']}: no stopping rule {rule_id!r}"
    ctx = worked_context(doc)
    ctx.update(overrides or {})
    return _expr.evaluate(rules[rule_id]["expression"], ctx, strict=True)


def stages_by_id(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        sid: st
        for sid, st in ((str(s.get("id")), s) for _, s in semantics.iter_stages(doc))
    }


def top_stage_order(doc: dict[str, Any]) -> list[str]:
    return [str(s["id"]) for s in doc["stages"]]


def assert_precedes(doc: dict[str, Any], earlier: str, later: str) -> None:
    """``later`` must transitively depend on ``earlier`` among the top-level stages."""
    deps = {
        str(s["id"]): [str(d) for d in (s.get("depends_on") or [])]
        for s in doc["stages"]
    }
    assert earlier in deps and later in deps, (
        f"{doc['id']}: {earlier!r}/{later!r} not top-level stages"
    )
    seen: set[str] = set()
    frontier = [later]
    while frontier:
        cur = frontier.pop()
        for d in deps.get(cur, []):
            if d not in seen:
                seen.add(d)
                frontier.append(d)
    assert earlier in seen, (
        f"{doc['id']}: {later!r} does not (transitively) depend on {earlier!r}"
    )


def mutated(doc: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(doc)


def drop_stage(doc: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Remove a top-level stage but LEAVE the depends_on edges that point at it.

    That is the mutation that matters: it models a blueprint edited to skip a mandatory
    control, and DSL-SEM-002 must catch the now-dangling dependency.
    """
    out = mutated(doc)
    before = len(out["stages"])
    out["stages"] = [s for s in out["stages"] if s.get("id") != stage_id]
    assert len(out["stages"]) == before - 1, (
        f"stage {stage_id!r} was not present to drop"
    )
    return out
